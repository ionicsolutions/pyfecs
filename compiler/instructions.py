import logging
from ..objects.exceptions import *


class InstructionBits:
    def __init__(self):
        pass

    wait = 0
    set = 2
    jump = 1
    end = 3


class Instruction(object):
    TOTAL_LENGTH = (2 ** 32) - 1  # an instruction is 32 bits long
    COMMAND_LOWEST_BIT = 30  # the upper two bits contain the command
    VALUE_MASK = (2 ** COMMAND_LOWEST_BIT) - 1
    RAM_LOWEST_ADDRESS = 1  # in the IPU RAM, the addresses start at 1

    def __init__(self, time=0, value=0):
        self.logger = logging.getLogger("PyFECS.compiler.instructions")
        self.time = time
        self.command = InstructionBits.wait
        self._value = value

        self.part_of = None
        self._address = None

    @property
    def value(self):
        return self._value

    @property
    def address(self):
        if self._address is None:
            raise CompilerErrorException("Address not set.")
        else:
            return self._address + self.RAM_LOWEST_ADDRESS

    @address.setter
    def address(self, value):
        self._address = value

    @property
    def bytes(self):
        command = self.command << self.COMMAND_LOWEST_BIT

        if self.value > self.VALUE_MASK:
            raise CompilerErrorException("Value is too long.")

        instruction = command + self.value

        if instruction > self.TOTAL_LENGTH:
            raise CompilerErrorException("Instruction is too long.")

        return instruction


class WaitInstruction(Instruction):
    """
    *Instruction:*

    - [31:30]: Instruction bits
    - [29:0]: Waiting time in FPGA time units
    """

    def __init__(self, time, value):
        super(WaitInstruction, self).__init__(time, value)
        self.command = InstructionBits.wait

    @classmethod
    def duration(cls, time, duration):
        duration = int(duration)
        if duration > cls.VALUE_MASK:
            raise ValueError("Duration is too long.")
        elif duration < 1:
            raise ValueError("Duration is too short.")
        else:
            return cls(time, duration)


class SetInstruction(Instruction):
    """
    *Instruction:*

    - [31:30]: Instruction bits
    - [29:24]: Unused (can be used for more internal channels
      on the FPGA)
    - [23:0]: Output Bus Value

    """
    OUTPUT_BUS_LENGTH = 24
    OUTPUT_MASK = (2 ** OUTPUT_BUS_LENGTH) - 1

    def __init__(self, time, value):
        super(SetInstruction, self).__init__(time, value=0)
        self.command = InstructionBits.set

        self.logic_value = value
        self.mask = 0
        self.polarity_mask = 0

        self.destination_of = []

    @property
    def value(self):
        if not self.logic_value - (self.logic_value & self.mask) == 0:
            raise CompilerErrorException("SetInstruction contains unmasked "
                                         "values. Inconsistent state.")
        return self.logic_value ^ self.polarity_mask

    def inherit(self, previous, inheritance_mask):
        if not isinstance(previous, SetInstruction):
            raise ValueError("Previous instruction to inherit from must be "
                             "a SetInstruction.")
        self.logger.debug("Inheritance mask: %s",
                          format(inheritance_mask, "#026b"))
        self.logger.debug("My mask: %s",
                          format(self.mask, "#026b"))
        for channel_id in range(self.OUTPUT_BUS_LENGTH):
            if inheritance_mask & (1 << channel_id):
                if self.mask & (1 << channel_id):
                    pass
                else:
                    if previous.logic_value & (1 << channel_id) > 0:
                        self.logger.debug("Inheriting %d from channel %d.",
                                          previous.logic_value & (1 << channel_id),
                                          channel_id)
                        self.logger.debug("Current value for that bit: %d",
                                          self.logic_value & (1 << channel_id))
                    self.logic_value += previous.logic_value & (1 << channel_id)
                    self.mask |= (1 << channel_id)
        if not self.logic_value - (self.logic_value & self.mask) == 0:
            raise CompilerErrorException("SetInstruction contains unmasked "
                                         "values after inheriting.")

    @classmethod
    def single_channel(cls, time, channel, state):
        if cls.OUTPUT_BUS_LENGTH > channel >= 0:
            value = state << channel
            instruction = cls(time, value)
            instruction.mask = 1 << channel
            return instruction
        else:
            raise ValueError("Channel outside of range.")

    @classmethod
    def channels(cls, time, logic_state, mask):
        if 2 ** cls.OUTPUT_BUS_LENGTH > logic_state >= 0:
            instruction = cls(time, logic_state)
            instruction.mask = mask
            return instruction
        else:
            raise ValueError("logic_state exceeds length of output bus.")

    @classmethod
    def control_register(cls, register, time, control_id, part_of):
        gray_id = control_id ^ (control_id >> 1)
        if gray_id > 2 ** register.length - 1:
            raise CompilerErrorException("Control ID is too long.")
        instruction = cls(time, register.value_to_state(gray_id))
        instruction.mask = register.mask
        instruction.part_of = part_of
        return instruction

    @classmethod
    def combine(cls, control_mask, *args):
        """

        :param control_mask: Masks channel to be ignored when merging
                             conflicting instructions. When a SetInstruction is
                             the destination of several jumps, only a single
                             control value is written to the OutputBus.
        :param args: Arbitrary number of SetInstruction instances.
        :return: New SetInstruction object
        """
        time = args[0].time
        part_of = None
        value = 0
        mask = 0
        destination_of = []
        for instruction in args:
            if not isinstance(instruction, SetInstruction):
                raise ValueError("Arguments must be instances of"
                                 "SetInstruction.")
            if instruction.time != time:
                raise ValueError("Can only combine instructions with identical "
                                 "instruction time.")
            if instruction.part_of is not None:
                if part_of is None:
                    part_of = instruction.part_of
                else:
                    if part_of == instruction.part_of:
                        raise ValueError(
                            "Cannot combine SetInstructions within the "
                            "same block (block '%s')." % part_of)
                    else:
                        raise ValueError(
                            "Cannot combine SetInstructions from different "
                            "blocks (blocks '%s' and '%s')."
                            % (part_of, instruction.part_of))
            if instruction.mask & mask == 0:
                value |= instruction.logic_value
                mask += instruction.mask
            else:
                for channel_id in range(cls.OUTPUT_BUS_LENGTH):
                    id_value = 1 << channel_id
                    if instruction.mask & id_value:  # we want to set this value
                        if mask & id_value:  # the value is already set
                            if (value & id_value ==
                                        instruction.logic_value & id_value):
                                pass  # the value is already set correctly
                            else:
                                if control_mask & id_value:
                                    pass
                                else:
                                    raise CompilerErrorException(
                                        "Conflicting SetInstructions cannot be "
                                        "combined. Ensure that list is sorted "
                                        "and compressed prior to inheriting. "
                                        "Channel %d is %d and %d (%d)"
                                        % (channel_id, value & id_value,
                                           instruction.logic_value & id_value,
                                           len(args)))
                        else:  # the value is not set, set it and update mask
                            value |= instruction.logic_value & id_value
                            mask |= id_value
            destination_of += instruction.destination_of

        combined_instruction = cls(time, value)
        combined_instruction.mask = mask
        combined_instruction.destination_of = destination_of
        combined_instruction.part_of = part_of
        for instruction in combined_instruction.destination_of:
            instruction.destination_instruction = combined_instruction
        return combined_instruction


class JumpInstruction(Instruction):
    """

    The destination of a JumpInstruction is always a SetInstruction.

    *Instruction:*

    - [31:30]: Instruction bits
    - [29]: If *1*, always jump. If *0*, evaluate threshold condition.
    - [28:26]: SPC channel ID
    - [25:10]: Threshold
    - [9:0]: Jump destination
    """
    DESTINATION_MASK = (2 ** 10) - 1
    THRESHOLD_MASK = (2 ** 16) - 1 << 10

    def __init__(self, time, value):
        super(JumpInstruction, self).__init__(time, value)

        self.always_jump = False
        self.channel_id = 0
        self.threshold = 0
        self.destination_instruction = None

        self.command = InstructionBits.jump

    @property
    def value(self):
        value = int(self.always_jump) << 29
        value += self.channel_id << 26
        value += self.threshold << 10
        if not self in self.destination_instruction.destination_of:
            raise CompilerErrorException(
                "%s is not registered as a destination of %s."
                % (self, self.destination_instruction))
        value += self.destination_instruction.address
        return value

    @classmethod
    def goto(cls, time, destination_instruction, part_of=None):
        goto = cls(time=time, value=0)
        goto.always_jump = True
        goto.destination_instruction = destination_instruction
        goto.part_of = part_of
        return goto

    @classmethod
    def conditional(cls, time, channel_id, threshold, destination_instruction,
                    part_of=None):
        conditional = cls(time=time, value=0)
        conditional.always_jump = False
        conditional.channel_id = channel_id
        conditional.threshold = threshold
        conditional.destination_instruction = destination_instruction
        conditional.part_of = part_of
        return conditional


class EndInstruction(Instruction):
    """End of the sequence.

    *Instruction:*

    - [31:30]: Instruction bits
    - [29:0]: Unused
    """

    def __init__(self, time, value=0):
        super(EndInstruction, self).__init__(time, value)
        self.command = InstructionBits.end

    @classmethod
    def within_jump(cls, time, part_of):
        end = EndInstruction(time)
        end.part_of = part_of
        return end
