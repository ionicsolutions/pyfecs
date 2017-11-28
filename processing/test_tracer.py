import unittest

import tracer
from PyFECS.compiler.compiler import Compiler
from PyFECS.objects.Sequence import Sequence

import logging

logging.basicConfig(level=logging.INFO)


class TestGrayToBinary(unittest.TestCase):
    def test_general(self):
        self.assertEqual(0, tracer.gray_to_binary(0))

    def test_numbers(self):
        for number in range(1000):
            gray_value = number ^ (number >> 1)
            self.assertEqual(number, tracer.gray_to_binary(gray_value))


class TestTree(unittest.TestCase):
    def setUp(self):
        self.s = Sequence.from_file("./compiler/test_sequences/minimal_sequence.xml")
        c = Compiler()
        c.TRUNCATE = False
        c.load(self.s)
        self.compiled_sequence, report = c.compile(variant=0)

    def test_build(self):
        tree = tracer.SequenceControlTree(self.compiled_sequence,
                                          self.s.hardware.control_register)
        tree.build()
        print(tree.tree)

    def test_graph(self):
        tree = tracer.SequenceControlTree(self.compiled_sequence,
                                          self.s.hardware.control_register)
        tree.build()
        g = tracer.SequenceControlGraph(tree)
        print(g.graph)


if __name__ == "__main__":
    unittest.main()
