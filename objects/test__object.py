import pickle
from PyFECS.objects.Sequence import Sequence
import logging
import unittest

logging.basicConfig(level=logging.DEBUG)


class SequencePickling(unittest.TestCase):
    def test_pickle_empty_sequence(self):
        a = pickle.dumps(Sequence())
        b = pickle.loads(a)


if __name__ == "__main__":
    unittest.main()
