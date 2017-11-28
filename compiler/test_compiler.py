import logging
logging.basicConfig()
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("Test")
import unittest

import compiler
from objects.Sequence import Sequence
from objects.exceptions import *


class TestCompiler(unittest.TestCase):

    def setUp(self):
        self.compiler = compiler.Compiler()

    def test_load_value(self):
        with self.assertRaises(ValueError):
            self.compiler.load("Not_a_Sequence_instance.xml")

    def test_load_invalid_sequence(self):
        invalidSequence = Sequence()
        invalidSequence.length = -10
        with self.assertRaises(InvalidSequenceException):
            self.compiler.load(invalidSequence)

    def test_load_valid_sequence(self):
        validSequence = Sequence()
        self.compiler.load(validSequence)

    def test_compile_valid_sequence(self):
        validSequence = Sequence()
        self.compiler.load(validSequence)
        compiled = self.compiler.compile(0)
        logger.info(compiled)

    def test_load_minimal_sequence(self):
        s = Sequence.from_file("./compiler/test_sequences/minimal_sequence.xml")
        self.compiler.load(s)

    def test_compile_minimal_sequence(self):
        s = Sequence.from_file("./compiler/test_sequences/minimal_sequence.xml")
        self.compiler.load(s)
        self.compiler.compile(0)

    def test_compile_sequence_with_one_time_window(self):
        s = Sequence.from_file(
            "./compiler/test_sequences/sequence_with_one_time_window.xml")
        self.compiler.load(s)
        self.compiler.compile(0)

if __name__ == "__main__":
    unittest.main()