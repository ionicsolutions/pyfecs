import logging

logging.basicConfig()

import unittest

from instructions import JumpInstruction, WaitInstruction, \
    EndInstruction, SetInstruction, InstructionBits
from objects.exceptions import *


class TestWaitInstruction(unittest.TestCase):
    def test_duration_from_zero(self):
        for duration in [1, 10, 999, 1000, 10000]:
            instruction = WaitInstruction.duration(time=0, duration=duration)
            self.assertEqual(instruction.value, duration)

    def test_length_restriction(self):
        with self.assertRaises(ValueError):
            instruction = WaitInstruction.duration(time=0, duration=2 ** 30)

    def test_positive_duration(self):
        with self.assertRaises(ValueError):
            instruction = WaitInstruction.duration(time=0, duration=0)


class TestEndInstruction(unittest.TestCase):
    def test_instruction_bits(self):
        instruction = EndInstruction(time=0)
        self.assertEqual(instruction.bytes >> instruction.COMMAND_LOWEST_BIT,
                         InstructionBits.end)


class TestSetInstruction(unittest.TestCase):
    def test_instruction_bits(self):
        instruction = SetInstruction(time=0, value=0)
        self.assertEqual(instruction.bytes >> instruction.COMMAND_LOWEST_BIT,
                         InstructionBits.set)

    def test_single_channel_raises_exception_when_channel_invalid(self):
        with self.assertRaises(ValueError):
            instruction = SetInstruction.single_channel(time=0, channel=1000,
                                                        state=0)

        with self.assertRaises(ValueError):
            instruction = SetInstruction.single_channel(time=0, channel=-1,
                                                        state=0)

    def test_control_register_raises_error_when_id_is_too_long(self):
        with self.assertRaises(CompilerErrorException):
            instruction = SetInstruction.control_register(time=0,
                                                          control_id=200000,
                                                          register=None)

    def test_control_register_computes_id_correctly(self):
        mapping = {0: 0, 2: 0b11, 7: 0b100, 13: 0b1011}
        for binary, gray in mapping.iteritems():
            instruction = SetInstruction.control_register(time=0,
                                                          control_id=binary,
                                                          register=None)
            gray_value = instruction.logic_value >> 5
            self.assertEqual(gray_value, gray)

    def test_combine_raises_exception_when_inequal_times(self):
        instruction1 = SetInstruction(time=5, value=0)
        instruction2 = SetInstruction(time=10, value=0)
        with self.assertRaises(ValueError):
            instruction3 = SetInstruction.combine(instruction1, instruction2)

    def test_combine_single_channels(self):
        instruction1 = SetInstruction.single_channel(time=100, channel=3,
                                                     state=1)
        instruction2 = SetInstruction.single_channel(time=100, channel=4,
                                                     state=1)
        instruction3 = SetInstruction.combine(instruction1, instruction2)
        self.assertEqual(instruction3.logic_value, 2 ** 3 + 2 ** 4)

    def test_combine_multiple_instructions(self):
        instructions = []
        for i in range(16):
            instructions.append(SetInstruction.single_channel(time=100,
                                                              channel=i,
                                                              state=1))
        instruction2 = SetInstruction.combine(*instructions)
        self.assertEqual(instruction2.logic_value, 2 ** 16 - 1)

    def test_combine_equal_overlapping_instructions(self):
        instruction1 = SetInstruction.single_channel(time=180, channel=8,
                                                     state=1)
        instruction2 = SetInstruction.single_channel(time=180, channel=8,
                                                     state=1)
        instruction3 = SetInstruction.combine(instruction1, instruction2)
        self.assertEqual(instruction1.logic_value, instruction3.logic_value)

    def test_combine_conflicting_overlapping_instructions(self):
        instruction1 = SetInstruction.single_channel(time=180, channel=4,
                                                     state=0)
        instruction2 = SetInstruction.single_channel(time=180, channel=4,
                                                     state=1)
        with self.assertRaises(CompilerErrorException):
            instruction3 = SetInstruction.combine(instruction1, instruction2)

    def test_inherit_distinct_instructions(self):
        instruction1 = SetInstruction.single_channel(time=80, channel=3,
                                                     state=1)
        instruction2 = SetInstruction.single_channel(time=100, channel=4,
                                                     state=1)
        instruction2.inherit(instruction1, 2**24-1)


class TestJumpInstruction(unittest.TestCase):
    def test_get_fails_when_no_address_is_set(self):
        instruction = JumpInstruction(time=0, value=0)
        with self.assertRaises(AttributeError):
            value = instruction.value


if __name__ == "__main__":
    unittest.main()
