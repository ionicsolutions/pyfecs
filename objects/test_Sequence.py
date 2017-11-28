import logging
import unittest

logging.basicConfig(level=logging.INFO)
from Sequence import Sequence
import _Sequence_verification
from .exceptions import InvalidSequenceException
import os

testpath = os.path.dirname(os.path.realpath(__file__))


class SequenceLoadingAndSaving(unittest.TestCase):
    def test_minimal_sequence_loads(self):
        s = Sequence.from_file(testpath + "/test_sequences/minimal_sequence.xml")

    def test_minimal_sequence_exports(self):
        s = Sequence.from_file(testpath + "/test_sequences/minimal_sequence.xml")
        XML = s.XML

    def test_minimal_sequence_export_imports_again(self):
        s = Sequence.from_file(testpath + "/test_sequences/minimal_sequence.xml")
        t = Sequence.from_XML(s.XML)

    def test_minimal_sequence_writes_to_file(self):
        s = Sequence.from_file(testpath + "/test_sequences/minimal_sequence.xml")
        s.save_XML(testpath + "test_sequences/minimal_sequence_saved.xml")

    def test_minimal_sequence_written_file_loads(self):
        s = Sequence.from_file(testpath + "/test_sequences/minimal_sequence.xml")
        s.save_XML(testpath + "/test_sequences/minimal_sequence_saved.xml")
        t = Sequence.from_file(testpath + "/test_sequences/minimal_sequence_saved.xml")


class SequenceVerificationFunctions(unittest.TestCase):
    def test_minimal_sequence_tree(self):
        s = Sequence.from_file(testpath + "/test_sequences/minimal_sequence.xml")
        s.resolve_references()
        tree = _Sequence_verification.Tree(sequence=s, control_values={})

    def test_minimal_sequence_build_tree(self):
        s = Sequence.from_file(testpath + "/test_sequences/minimal_sequence.xml")
        s.resolve_references()
        tree = _Sequence_verification.Tree(sequence=s, control_values={})
        tree.build()

    def test_minimal_sequence_check_tree(self):
        s = Sequence.from_file(testpath + "/test_sequences/minimal_sequence.xml")
        s.resolve_references()
        tree = _Sequence_verification.Tree(sequence=s, control_values={})
        tree.build()
        tree.check()

    def test_minimal_sequence_visualize_tree(self):
        s = Sequence.from_file(testpath + "/test_sequences/minimal_sequence.xml")
        s.resolve_references()
        tree = _Sequence_verification.Tree(sequence=s, control_values={})
        tree.build()
        tree.visualize()

    def test_detect_when_sequence_never_terminates_at_all(self):
        s = Sequence.from_file(
            testpath + "/test_sequences/minimal_sequence_with_loop.xml")
        s.resolve_references()
        tree = _Sequence_verification.Tree(sequence=s, control_values={})
        tree.build()
        tree.visualize()
        with self.assertRaises(InvalidSequenceException):
            tree.check()

    def test_detect_when_sequence_has_infinite_subloop(self):
        s = Sequence.from_file(
            testpath + "/test_sequences/minimal_sequence_with_subloop.xml")
        s.resolve_references()
        tree = _Sequence_verification.Tree(sequence=s, control_values={})
        with self.assertRaises(InvalidSequenceException):
            tree.build()
        tree.visualize()


if __name__ == "__main__":
    unittest.main()
