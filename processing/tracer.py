import copy
import logging

import numpy as np
from ..compiler.instructions import InstructionBits, Instruction, \
    SetInstruction, JumpInstruction
from ..objects.Sequence import Sequence

from ..data.channel import ChannelData
from ..data.raw import RawData
from ..data.shot import ShotData


class TracerException(Exception):
    # base exception
    pass


class ControlValueNotFoundException(TracerException):
    pass


class ControlValueOffException(TracerException):
    pass


class NextBranchTipNotFoundException(TracerException):
    pass


class TreeException(TracerException):
    pass


class Chopper(object):
    """Process sequence data without jumps."""
    def __init__(self, sequence, compiler_report):
        self.logger = logging.getLogger("Chopper")

        self.sequence = sequence
        self.report = compiler_report

        # initialize processing variables, overwritten by process()
        self.data = RawData()
        self.shots = []
        self._time_offset = 0
        self.channels = {}

    def process(self, raw_data):
        # compute length in TDC steps
        length = self.report.length * self.report.fpga_delay_unit # in us
        self.logger.debug("Length in us: %0.4f", length)
        length /= 1000.0
        length /= 1000.0
        length /= raw_data.TDC_RESOLUTION  # in TDC time
        self.logger.debug("Length in TDC units: %0.0f", length)

        channels = {}
        for channel, data in raw_data.channels:
            channel_data = ChannelData()

            shot_index = np.floor_divide(data, length)
            # convert to microseconds
            shot_data = np.remainder(data, length)\
                        * (raw_data.TDC_RESOLUTION * 1000.0 * 1000.0)

            i = 0
            for shot_number in xrange(self.sequence.shots):
                shot = ShotData()
                if shot_number in shot_index:  # this is probably not very efficient
                    shot.data = {0.0 : [shot_data[shot_index == shot_number].tolist()]}
                    i += 1
                else:
                    shot.data = {0.0 : [[]]}
                channel_data.add_shot(shot)

            self.logger.debug("Total counts in data: %d", len(shot_data))
            self.logger.debug("Shots with data: %d", i)

            channel_name = self.sequence.hardware.get_tdc_channel_name_by_id(channel)
            channels[channel_name] = channel_data

        return channels


class Tracer(object):
    """Process sequence data with jumps."""
    def __init__(self, sequence, compiler_report):
        self.logger = logging.getLogger("Tracer")

        self.sequence = sequence
        self.hardware_config = self.sequence.hardware
        self.control_register = self.sequence.hardware.control_register
        self.compiler_report = compiler_report
        self.fpga_delay_unit = compiler_report.fpga_delay_unit

        self.logger.info("Building SequenceControlTree.")
        tree = SequenceControlTree(compiler_report.compiled,
                                   self.control_register)
        self.control_times = tree.control_times
        self.logger.info("Building SequenceControlGraph.")
        self.graph = SequenceControlGraph(tree).graph

        # initialize processing variables, overwritten by process()
        self.data = RawData()
        self.shots = []
        self._time_offset = 0
        self.channels = {}

    def _sequence_time(self, fpga_time):
        """Convert *fpga_time* to a sequence time."""
        return fpga_time * self.fpga_delay_unit / Sequence.TIME_UNIT

    def process(self, data):
        """Convert the raw data from the TDC into ChannelData instances.

        :param data: Recorded TDC data.
        :type data: RawData
        :return: Dictionary of ChannelData instances, with the channel name
                 as keys.
        """

        self.shots = []
        self.channels = {}

        self.logger.info("Tracing control values...")

        self._time_offset = 0.0
        for i in xrange(self.sequence.shots):
            shot_data, shot_duration = self._process_shot()
            self.shots.append((self._time_offset, shot_data))
            self._time_offset += shot_duration + 1

        self.logger.info("Finished tracing. Process TDC data.")
        for channel in self.sequence.counter_channels:
            self.logger.info("Processing channel '%s'.", channel)
            tdc_channel = self.hardware_config.tdc_channels[channel]
            tdc_data = self.data.get_channel(tdc_channel)
            channel_data = self._process_channel_data(tdc_data)
            self.channels[channel] = channel_data
        self.logger.info("Finished processing of TDC data.")

        return self.channels

    def _process_shot(self):
        shot = {}
        in_shot_time = 0

        start = self._find_control_pulse(fpga_time=in_shot_time)
        if start != 1:
            raise ControlValueOffException

        # initialize search
        control_value = start
        shot[in_shot_time] = control_value

        searching = True
        while searching:
            for next_distance, next_values in self.graph[control_value]:
                if "END" in next_values:
                    next_start = self._find_control_pulse(in_shot_time + next_distance + 1)
                    if next_start == 1:
                        searching = False
                        in_shot_time += next_distance
                        break

                value_ = self._find_control_pulse(in_shot_time + next_distance)
                if value_ in next_values:
                    in_shot_time += next_distance
                    control_value = value_

                    # record the found point
                    shot[in_shot_time] = control_value
                    break
            else:
                raise ControlValueNotFoundException

        return shot, in_shot_time

    def _process_channel_data(self, tdc_data):
        channel_data = ChannelData()
        start = 0
        i = 0
        for time_offset, shot in self.shots:
            shot_data = ShotData()

            for timestamp in sorted(shot.keys()):
                sequence_time = self._sequence_time(self.control_times[shot[timestamp]])


                tdc_timestamp =
                while tdc_data[i] < tdc_timestamp:
                    i += 1
                rep_offset = self.data.tdc_time(fpga_time=timestamp)
                rep_data = [self.data.sequence_time(t - rep_offset)
                            for t in tdc_data[start:i]]
                rep_start = self._sequence_time(
                    self.control_times[shot[timestamp]])
                try:
                    shot_data.data[rep_start].append(rep_data)
                except KeyError:
                    shot_data.data[rep_start] = [rep_data]
            channel_data.add_shot(shot_data)
        return channel_data

    def _cut_and_shift(self, data, starting_time,):

    def _find_control_pulse(self, fpga_time):
        state = self.data.state(self._sequence_time(fpga_time))
        print format(state, "#010b")
        gray_value = self.control_register.control_pulse_to_value(state)
        control_value = gray_to_binary(gray_value)
        return control_value

    @staticmethod
    def _control_range(control_value):
        return (control_value - 1, control_value, control_value + 1)


def gray_to_binary(gray_value):
    """Convert a Gray-code value to binary.

    :param gray_value: Gray-code value
    :type gray_value: int
    :returns: Value in regular encoding.
    :rtype: int
    """
    mask = gray_value >> 1
    while mask != 0:
        gray_value = gray_value ^ mask
        mask = mask >> 1
    return int(gray_value)


class SequenceControlGraph(object):
    """Sequence graph for :class:`Tracer`.

    The graph is a dictionary where the keys are the control
    register values as integers. The values are dictionaries
    with the distance (in time) between the control-register
    value and the next:

    .. code-block:: python

        control_graph = {
        1 : { 200 : [4, 2], 250 : [6], ...},
        ...
        }

    The graph is built from a :class:`SequenceControlTree`.
    """
    def __init__(self, tree):
        self.logger = logging.getLogger("SequenceControlGraph")
        self.tree = tree
        self.graph = {}
        self.build()

    def build(self):
        self.graph = {}
        for control_entry in self.tree.control_pulses:
            self.graph[control_entry[1]] = self._process_entry(control_entry)

    def _process_entry(self, control_entry):
        this_time, this_value = control_entry
        self.logger.debug("Processing %s, %s", this_time, this_value)

        next_nodes = {}

        branch = self.tree.get_branch_for(control_entry)
        possible_next_values = branch.keys()

        for next_time, next_value in possible_next_values:
            self.logger.debug("Next value: %d, %s", next_time, next_value)
            distance = next_time - this_time
            if isinstance(next_value, int):
                next_nodes[distance] = [next_value]
            elif next_value == "END":
                next_nodes[distance] = [next_value]
            elif next_value == "JUMP":
                self.logger.debug("Jump in %d steps", distance)
                sub_nodes = self._process_entry((next_time, next_value))
                for node_distance, node_values in sub_nodes.iteritems():
                    total_distance = distance + 1
                    for node_value in node_values:
                        if isinstance(node_value, int):
                            self.logger.debug("Control value %d in %d steps",
                                              node_value, total_distance)
                        elif node_value == "END":
                            self.logger.debug("END in %d steps", total_distance)
                        else:
                            raise TracerException("Jump was not resolved.")

                        try:
                            next_nodes[total_distance].append(node_value)
                        except KeyError:
                            next_nodes[total_distance] = [node_value]
            else:
                raise TracerException("Went down too far on a branch.")

        return next_nodes


class SequenceControlTree(object):
    """Sequence structure for :class:`SequenceControlGraph`.

    The control tree is created from the compiled sequence,
    without any knowledge of the :class:`~objects.Sequence.Sequence`
    except the output channels used for the
    :class:`~objects.ControlRegister.ControlRegister`.
    """

    def __init__(self, compiled_sequence, control_register):
        self.logger = logging.getLogger("SequenceControlTree")

        self.compiled_sequence = compiled_sequence

        self._value = control_register.state_to_value

        self.instruction_times = {}
        self.control_points = {}
        self.jump_points = {}
        self.end_points = []

        self._tree = {}
        self.build()

    @property
    def tree(self):
        tree = self._combine(self._tree)
        return tree

    @property
    def control_times(self):
        control_times = {control_value: self.instruction_times[address]
                         for address, control_value in self.control_points.iteritems()}
        return control_times

    @property
    def control_pulses(self):
        control_entries = []
        for address, control_value in self.control_points.iteritems():
            control_entries.append((self.instruction_times[address],
                                   control_value))
        return control_entries

    def _combine(self, branch):
        combined = {}
        for ram_address, sub_branch in branch.iteritems():
            if ram_address in self.control_points:
                entry = (self.instruction_times[ram_address],
                         self.control_points[ram_address])
                combined[entry] = self._combine(sub_branch)
            elif ram_address in self.end_points:
                entry = (self.instruction_times[ram_address], "END")
                combined[entry] = None
            elif ram_address in self.jump_points:
                entry = (self.instruction_times[ram_address], "JUMP")
                if isinstance(sub_branch, dict):
                    combined[entry] = self._combine(sub_branch)
                else:
                    combined[entry] = ("LOOP", self.jump_points[ram_address])
        return combined

    def get_branch_for(self, control_entry):
        """Get the branch starting with *control_entry*.

        Search for all occurences of *control_entry* entries in the
        tree (see :meth:`._find_in_branch` for details which entries
        will be found) and return the branch which starts at the
        highest level.
        """
        places = self._find_in_branch(control_entry, self.tree, 0)
        if places:
            return sorted(places)[0][1]  # lowest level
        else:
            raise TreeException("Did not find control entry %s, %s in tree."
                                % control_entry)

    def _find_in_branch(self, control_entry, branch, level):
        findings = []
        for entry, sub_branch in branch.iteritems():
            if entry == control_entry:
                findings.append((level, sub_branch))
            else:
                if isinstance(sub_branch, dict):
                    findings.extend(self._find_in_branch(control_entry,
                                                         branch=sub_branch,
                                                         level=level + 1))
        return findings

    def build(self):
        self._tree = {}
        self._find_points_of_interest()
        self._tree[Instruction.RAM_LOWEST_ADDRESS] = \
            self._branch(Instruction.RAM_LOWEST_ADDRESS, [])

    def _find_points_of_interest(self):
        absolute_time = 0
        for i, line in enumerate(self.compiled_sequence):
            ram_address = i + Instruction.RAM_LOWEST_ADDRESS
            instruction = line >> Instruction.COMMAND_LOWEST_BIT
            if instruction == InstructionBits.wait:
                delay = line & Instruction.VALUE_MASK
                self.logger.debug("%d: Delay of %d steps", ram_address, delay)
                absolute_time += delay
            elif instruction == InstructionBits.jump:
                destination = line & JumpInstruction.DESTINATION_MASK
                self.logger.debug("%d: Jump to %d", ram_address, destination)
                self.instruction_times[ram_address] = absolute_time
                self.jump_points[ram_address] = destination
            elif instruction == InstructionBits.set:
                gray_value = self._value(line & SetInstruction.OUTPUT_MASK)
                control_value = gray_to_binary(gray_value)
                self.logger.debug("%d: Set instruction, control register %d",
                                  ram_address, control_value)
                if control_value:
                    self.instruction_times[ram_address] = absolute_time
                    self.control_points[ram_address] = control_value
            elif instruction == InstructionBits.end:
                self.logger.debug("%d: End", ram_address)
                self.instruction_times[ram_address] = absolute_time
                self.end_points.append(ram_address)
            else:
                raise TreeException(
                    "Unrecognized instruction %d (%s) in compiled sequence."
                    % (instruction, format(instruction, '#06b')))
            absolute_time += 1

    def _branch(self, ram_address, origins):
        self.logger.debug("Branch for %d, from %s", ram_address, origins)
        branch = {}
        for instruction_address in sorted(self.instruction_times.keys()):
            if instruction_address > ram_address:
                origins.append(instruction_address)
                if instruction_address in self.end_points:
                    branch[instruction_address] = "END"
                elif instruction_address in self.control_points:
                    branch[instruction_address] = \
                        self._branch(instruction_address, origins)
                elif instruction_address in self.jump_points:
                    destination_address = self.jump_points[instruction_address]
                    if destination_address in origins:
                        branch[instruction_address] = \
                            self.jump_points[instruction_address]
                    else:
                        pass_origins = copy.deepcopy(origins)
                        branch[instruction_address] = \
                            self._branch(instruction_address, pass_origins)

                        jump_origins = copy.deepcopy(origins)
                        jump_origins.append(destination_address)
                        jump_branch = {destination_address:
                                           self._branch(destination_address,
                                                        jump_origins)}

                        if isinstance(branch[instruction_address], dict):
                            branch[instruction_address].update(jump_branch)
                        else:
                            raise ValueError(branch[instruction_address])

                else:
                    raise TreeException("Invalid RAM address: %d."
                                        % ram_address)
                break
        return branch


def prettyprint(tree):
    def pretty(branch, level):
        msg = ""
        for key, sub_branch in branch.iteritems():
            if isinstance(sub_branch, dict):
                msg += "   ." * level + str(key).rjust(4) + "\n"
                msg += pretty(sub_branch, level + 1)
            else:
                msg += ". .." * level + str(key).rjust(4) + "\n"
        return msg

    return pretty(tree._tree, 0)
