# -*- coding: utf-8 -*-
#
#   (c) 2014-2017 Ionic Solutions
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
"""Python compiler for FECS sequences.

The compiler takes a :class:`objects.Sequence` instance and converts it
into a sequence of 32-bit instructions for the FECS IPU.

.. warning:: While the compiler guarantees that the order of instructions is
             preserved across variants (i.e. instructions which are ordered
             the same way in the Sequence instance across variants will be
             ordered the same in the compiled sequence), it is not
             guaranteed that their time difference will be the same even
             when it is the same in the Sequence instance.

"""
import logging
import numpy as np

from ..objects.Sequence import Sequence
from ..objects.channels import OutputChannel, ControlChannel
from ..objects.exceptions import CompilerErrorException, InvalidSequenceException
from ..objects.jumps import Terminator, Destination, Pass
from .instruction_list import InstructionList
from .instructions import SetInstruction, WaitInstruction, JumpInstruction, \
    EndInstruction, InstructionBits
from .report import CompilerReport


class Compiler(object):
    # Compiler flags (user-accessible)
    TRUNCATE = False  # shorten sequence to last TimePoint
    CONTROL_REGISTER_HIGH_TIME = 350  # length of ControlRegister pulse

    # Compiler constants
    # to restrict the length of an instruction block to a
    # reasonable value, we limit the maximum number of
    # conditions per jump
    _MAX_JUMP_CONDITIONS = 10

    def __init__(self):
        self.logger = logging.getLogger("Compiler")

        self.sequence = Sequence()
        self.variant = 0
        self.control_values = self.sequence.get_control_values(self.variant)
        self.control_register = self.sequence.hardware.control_register
        self.fpga_delay_unit = self.sequence.hardware.fpga_delay_unit

        self.instruction_list = InstructionList()
        self.time_windows = []

        self._destination_id = 0
        self._jump_times = {}

    @property
    def constants(self):
        return {"_MAX_JUMP_CONDITIONS": self._MAX_JUMP_CONDITIONS}

    @property
    def destination_id(self):
        self._destination_id += 1
        self.logger.debug("Raising destination_id to %d", self._destination_id)
        if self._destination_id < 2 ** self.control_register.length:
            return self._destination_id
        else:
            raise CompilerErrorException(
                "Destination ID exceeds control register length %d : %d"
                % (self.control_register.length, self._destination_id))

    def load(self, sequence):
        if not isinstance(sequence, Sequence):
            raise ValueError("Sequence must be a PyFECS Sequence instance.")
        try:
            sequence.verify()
        except InvalidSequenceException as e:
            self.logger.error("Invalid sequence.")
            raise e
        else:
            self.sequence = sequence
            self.control_register = self.sequence.hardware.control_register
            self.fpga_delay_unit = self.sequence.hardware.fpga_delay_unit

    def compile(self, variant):
        self.variant = variant
        self.control_values = self.sequence.get_control_values(self.variant)
        self._compute_sequence_length()

        self._populate_instruction_list()
        self._complete_instruction_list()

        polarity_mask = self.sequence.hardware.polarity_mask
        self.instruction_list.add_polarity_mask(polarity_mask)
        self.instruction_list.assign_addresses()
        compiled = [instruction.bytes for instruction in
                    self.instruction_list.instructions]
        #print("Compiled Sequence: %s" % self.sequence.name)
        #prettyprint(compiled)
        report = CompilerReport.from_compiler_instance(self, compiled)
        return compiled, report

    def _fpga_time(self, sequence_time):
        return int(np.around([sequence_time / self.fpga_delay_unit])[0])

    def _compute_sequence_length(self):
        if self.TRUNCATE:
            sequence_length = self.sequence.latest_time_point(self.variant)
            self.logger.info("Truncated sequence to %0.2f.", sequence_length)
        else:
            sequence_length = self.sequence.length
        self.length = self._fpga_time(sequence_length)

    def _populate_instruction_list(self):
        self._set_up_instruction_list()
        self._add_time_windows()
        self.logger.debug(
            "Length of InstructionList after adding all TimeWindows: %d",
            self.instruction_list.length)
        self.instruction_list.compress(self.control_register.mask)
        self.logger.debug(
            "Length of InstructionList after first compression: %d",
            self.instruction_list.length)
        self._add_jumps()
        self.logger.debug(
            "Length of InstructionList after adding all Jumps: %d",
            self.instruction_list.length)
        self.instruction_list.compress(self.control_register.mask)
        self.logger.debug(
            "Length of InstructionList after second compression: %d",
            self.instruction_list.length)
        self.instruction_list.sort()

    def _set_up_instruction_list(self):
        self.instruction_list = InstructionList()
        self._destination_id = 0  # reset destination_id
        self._jump_times = {}  # reset jump_times

        if self.sequence.jumps:
            # Write a "1" to the ControlRegister outputs
            self.global_start, global_start_reset = self._write_control_value(
                time=0, value=self.destination_id, block="_START")
            self.instruction_list.add(self.global_start, global_start_reset)
        else:
            self.logger.warning(
                "No jumps in sequence, not using ControlRegister.")

        # Place the final terminator
        self.global_terminator = EndInstruction(time=self.length - 1)
        self.global_terminator.part_of = "_END"
        self.instruction_list.add(self.global_terminator)

    def _write_control_value(self, time, value, block):
        """Generate instructions to output *value* on the ControlRegister.

        A ControlRegister write requires two set instructions: One to set
        the outputs to *high*, and one to return them to *low*. The length
        of the pulse is controlled through the compiler flag
        `CONTROL_REGISTER_HIGH_TIME`.
        """
        set_instruction = SetInstruction.control_register(
            time=time, control_id=value,
            register=self.control_register,
            part_of=block)
        reset_instruction = SetInstruction.control_register(
            time=time + self.CONTROL_REGISTER_HIGH_TIME, control_id=0,
            register=self.control_register,
            part_of=block)
        return set_instruction, reset_instruction

    def _add_time_windows(self):
        """Add all FPGA output channel TimeWindows to the InstructionList."""
        for channel in self.sequence.compiler_channels:
            if isinstance(channel, OutputChannel):
                channel_id = self.sequence.hardware.fpga_channels[
                    channel.name].channelID
            elif isinstance(channel, ControlChannel):
                channel_id = self.sequence.hardware.spc_channels[
                    channel.name].gate
            else:
                raise CompilerErrorException("Unknown Channel Type")

            for window in channel._time_windows:
                start_time, end_time = window.get_times(self.control_values)
                start = self._fpga_time(start_time)
                end = self._fpga_time(end_time)

                if end >= self.global_terminator.time:
                    end = self.global_terminator.time - 1
                    self.logger.warning("Truncated window %s to fit within "
                                        "sequence.", window.name)

                if start == end:
                    self.logger.warning("Window %s has length 0. Skipping.",
                                        window.name)
                    continue

                start_instruction = SetInstruction.single_channel(
                    time=start, channel=channel_id, state=1)
                end_instruction = SetInstruction.single_channel(
                    time=end, channel=channel_id, state=0)
                self.instruction_list.add(start_instruction, end_instruction)
                self.time_windows.append((start, end, channel_id))

    def _get_state(self, fpga_time):
        """Return the logical state of the output bus at *fpga_time*."""
        state = 0
        for start, end, channel_id in self.time_windows:
            if start <= fpga_time <= end:
                state += (1 << channel_id)
        return state

    def _add_jumps(self):
        for name, channel in self.sequence.control_channels.iteritems():
            channel_id = self.sequence.hardware.spc_channels[name].channelID
            for jump in channel.jumps:
                jump_time = self._fpga_time(jump.get_time(self.control_values))
                if jump_time in self._jump_times:
                    # There are two jumps scheduled for the same FPGA time.
                    # Since we do not allow for jumps to be defined at the same
                    # sequence time to make the sequence unambiguous
                    # (cf. Sequence._verify_variant), we have can determine
                    # which of the jumps is supposed to happen first.
                    other_jump, other_id = self._jump_times[jump_time]
                    self._order_jump(jump, channel_id, other_jump, other_id)
                else:
                    self._jump_times[jump_time] = (jump, channel_id)

        for jump_time, value in self._jump_times.iteritems():
            jump, channel_id = value
            self._process_jump(jump, jump_time, channel_id)

    def _order_jump(self, jump, jump_id, other_jump, other_id):
        fpga_time = self._fpga_time(jump.get_time(self.control_values))
        if (jump.get_time(self.control_values)
                > other_jump.get_time(self.control_values)):
            shift_back = other_jump
            shift_id = other_id
            keep = jump
            keep_id = jump_id
        elif (jump.get_time(self.control_values)
                < other_jump.get_time(self.control_values)):
            shift_back = jump
            shift_id = jump_id
            keep = other_jump
            keep_id = other_id
        else:
            raise CompilerErrorException(
                "Sequence contains two jumps ('%s' and '%s') which are "
                "scheduled at the same sequence time %0.4f. This should be "
                "caught during Sequence verification.")

        self._jump_times[fpga_time] = (keep, keep_id)
        if (fpga_time - 1) in self._jump_times:
            self._order_jump(
                jump=shift_back, jump_id=shift_id,
                other_jump=self._jump_times[(fpga_time - 1)][0],
                other_id=self._jump_times[(fpga_time - 1)][1])
        else:
            self.logger.warning(
                "Shifting jump '%s' to ensure it happens prior to '%s'."
                % (shift_back.name, keep.name)
            )
            self._jump_times[(fpga_time - 1)] = (shift_back, shift_id)

    def _process_jump(self, jump, jump_time, channel_id):
        jump_destinations = jump.compressed_conditions
        number_of_conditions = len(jump_destinations.keys())

        if number_of_conditions == 1:
            try:
                destination = jump_destinations[0]
            except IndexError:
                raise CompilerErrorException(
                    "Invalid compressedConditions for jump %s: "
                    "No destination for threshold 0.",
                    jump.name)
            if isinstance(destination, Pass):
                self.logger.warning("Jump %s is always passing. Skipping.",
                                    jump.name)
            else:
                self._add_goto(sequence_time=jump.get_time(self.control_values),
                               destination=destination)
        elif self._MAX_JUMP_CONDITIONS >= number_of_conditions > 1:
            ascending_thresholds = sorted(jump_destinations.keys())
            assert ascending_thresholds[0] == 0  # left here as a reminder
            passing_destination = self.global_terminator  # set as fallback

            for destination in jump_destinations.values():
                if isinstance(destination, Pass):
                    # as soon as one of the JUMP commands is passing,
                    # we need to add a ControlRegister write after the jump
                    passing_destination, passing_destination_reset = \
                        self._write_control_value(time=jump_time + 1,
                                                  value=self.destination_id,
                                                  block=jump.name)
                    self.instruction_list.add(passing_destination,
                                              passing_destination_reset)
                    break

            if isinstance(jump_destinations[0], Pass):
                # When the last step is passing, we do not need to add a
                # JUMP, the second-to-last JUMP will take care of that
                ascending_thresholds.remove(0)

            jump_sequence = []
            for i, threshold in enumerate(ascending_thresholds):
                if isinstance(jump_destinations[threshold], Pass):
                    jump_sequence.append(self._goto_instruction(
                        time=jump_time - i,
                        destination_instruction=passing_destination,
                        block=jump.name))
                elif isinstance(jump_destinations[threshold], Terminator):
                    jump_sequence.append(EndInstruction.within_jump(
                        time=jump_time - i, part_of=jump.name))
                elif isinstance(jump_destinations[threshold], Destination):
                    if threshold == 0:
                        # When the last step is not passing, it is always
                        # a goto. Note that this allows us to have the IPU
                        # check for counts > (threshold - 1) by changing
                        # the 32 bit instruction for the ConditionalJump
                        # instruction without running into the problem
                        # that (0-1) is 2**16-1, should this be necessary.
                        instructions = self._goto_destination(
                            time=jump_time - i,
                            destination=jump_destinations[threshold],
                            block=jump.name
                        )
                    else:
                        instructions = self._conditional_destination(
                            time=jump_time - i,
                            destination=jump_destinations[threshold],
                            threshold=threshold,
                            channel_id=channel_id,
                            block=jump.name
                        )
                    jump_sequence.extend(instructions)
                else:
                    raise CompilerErrorException(
                        "Unknown destination for Jump %s: %s"
                        % (jump.name, jump_destinations[threshold]))

            self.instruction_list.add(*jump_sequence)
        elif number_of_conditions > self._MAX_JUMP_CONDITIONS:
            # cf. notes in ControlChannel.verify regarding the minimum
            # distance between the end of the time window and the first
            # JUMP instruction
            raise CompilerErrorException(
                "Jump '%s' contains %i conditions, which is more than the "
                "maximum of %i conditions set through _MAX_JUMP_CONDITIONS. "
                "This value can be overridden by the user, but might lead to "
                "invalid IPU instructions."
                % (jump.name, number_of_conditions, self._MAX_JUMP_CONDITIONS)
            )
        else:
            raise CompilerErrorException("Jump '%s' without any condition.",
                                         jump.name)

    @staticmethod
    def _goto_instruction(time, destination_instruction, block):
        """Create a JUMP which always jumps to *destination_instruction*."""
        goto_instruction = JumpInstruction.goto(
            time=time, destination_instruction=destination_instruction,
            part_of=block)
        destination_instruction.destination_of.append(goto_instruction)
        return goto_instruction

    @staticmethod
    def _conditional_instruction(time, destination_instruction,
                                 threshold, channel_id, block):
        """Create a JUMP which jumps to *destination_instruction* when
        the counts in the last time window of SPC channel *channel_id* are
        above *threshold*.
        """
        conditional_instruction = JumpInstruction.conditional(
            time=time,
            threshold=threshold,
            channel_id=channel_id,
            destination_instruction=destination_instruction,
            part_of=block
        )
        destination_instruction.destination_of.append(conditional_instruction)
        return conditional_instruction

    def _goto_destination(self, time, destination, block):
        """Create a Jump which always jumps to *destination* and create the
        necessary *destination_instruction*."""
        destination_instruction, reset_instruction, state_instruction = \
            self._destination_instructions(destination)
        goto_instruction = self._goto_instruction(time, destination_instruction,
                                                  block=block)
        return (destination_instruction, reset_instruction, state_instruction,
                goto_instruction)

    def _conditional_destination(self, time, destination,
                                 threshold, channel_id, block):
        """Create a Jump which jumps to *destination* when the threshold
        condition is fulfilled."""
        destination_instruction, reset_instruction, state_instruction = \
            self._destination_instructions(destination)
        conditional_instruction = self._conditional_instruction(
            time, destination_instruction, threshold, channel_id, block=block)
        return (destination_instruction, reset_instruction, state_instruction,
                conditional_instruction)

    def _destination_instructions(self, destination):
        destination_time = self._fpga_time(
            destination.get_time(self.control_values))
        destination_instruction, reset_instruction = self._write_control_value(
            time=destination_time, value=self.destination_id, block=None)
        destination_state = self._get_state(destination_time)
        mask = self.sequence.hardware.control_register.negative_mask
        state_instruction = SetInstruction.channels(
            time=destination_time, logic_state=destination_state, mask=mask)
        return destination_instruction, reset_instruction, state_instruction

    def _add_goto(self, sequence_time, destination):
        if isinstance(destination, Destination):
            destination_instruction, reset_instruction, state_instruction = \
                self._destination_instructions(destination)
            self.instruction_list.add(destination_instruction,
                                      reset_instruction,
                                      state_instruction)
        elif isinstance(destination, Terminator):
            destination_instruction = self.global_terminator
        else:
            raise CompilerErrorException(
                "Unknown destination for goto instruction.")

        goto_time = self._fpga_time(sequence_time)
        goto_instruction = self._goto_instruction(
            time=goto_time, destination_instruction=destination_instruction,
            block=None)
        self.instruction_list.add(goto_instruction)

    def _complete_instruction_list(self):
        self._add_initial_state()
        self.instruction_list.compress(self.control_register.mask)
        self._inherit_output_values()
        self.instruction_list.compress(self.control_register.mask)
        self.instruction_list.make_times_unique(self.CONTROL_REGISTER_HIGH_TIME)
        self.instruction_list.sort()
        self._add_wait_instructions()

        self.instruction_list.sort()
        final_length = self.instruction_list.length
        self.instruction_list.compress(self.control_register.mask)
        if final_length != self.instruction_list.length:
            raise CompilerErrorException(
                "Was able to compress list after adding WaitInstructions.")

    def _add_initial_state(self):
        initial_state = self._get_state(0)
        mask = self.control_register.negative_mask
        initial_instruction = SetInstruction.channels(time=0,
                                                      logic_state=initial_state,
                                                      mask=mask)
        self.instruction_list.add(initial_instruction)

    def _inherit_output_values(self):
        last_set_instruction = None
        for time, type_, instruction in self.instruction_list.list:
            if type_ == InstructionBits.set:
                if last_set_instruction is None:
                    if time != 0:
                        raise CompilerErrorException("No SetInstruction at 0.")
                    else:
                        last_set_instruction = instruction
                else:
                    inheritance_mask = self.control_register.negative_mask
                    instruction.inherit(last_set_instruction, inheritance_mask)
                    last_set_instruction = instruction

    def _add_wait_instructions(self):
        wait_instructions = []
        last_time = -1
        for time, type_, instruction in self.instruction_list.list:
            if time < last_time:
                raise CompilerErrorException("InstructionList is not sorted.")
            elif time == last_time:
                raise CompilerErrorException(
                    "InstructionList contains non-unique timestamps: %d, %s"
                    % (time, self.instruction_list.list))
            else:
                delta = time - last_time - 1  # one step necessary for WAIT
                if delta:
                    wait_instructions.append(
                        WaitInstruction.duration(last_time + 1, delta - 1))
            last_time = time
        self.instruction_list.add(*wait_instructions)


def prettyprint(compiled):
    for address, instruction in enumerate(compiled):
        command = instruction >> 30
        if command == InstructionBits.wait:
            left = " WAIT "
            right = "%s" % (instruction & (2 ** 30) - 1)
        elif command == InstructionBits.set:
            left = " SET  "
            right = "%s" % (instruction & (2 ** 24) - 1)
        elif command == InstructionBits.end:
            left = " END  "
            right = ""
        elif command == InstructionBits.jump:
            left = " JUMP "
            right = "%s" % (instruction & (2 ** 10) - 1)
        else:
            raise CompilerErrorException("Unknown Command")
        print(format(address + 1, '#04') + left + format(instruction,
                                                         "#034b") + " " + right)
