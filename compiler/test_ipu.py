import unittest
import logging

logging.basicConfig()

import ipu
import compiler
from objects.Sequence import Sequence


class TestIPU(unittest.TestCase):

    def test_bare_sequence(self):
        s = Sequence()
        c = compiler.Compiler()
        c.TRUNCATE = False
        c.load(s)
        compiled_sequence = c.compile(variant=0)
        print(c.instruction_list.human)
        #compiler.prettyprint(compiled_sequence)
        i = ipu.IPU()
        i.showBuffer = False
        i._RAM = compiled_sequence
        s.shots = 2
        i.nRepeats = s.shots
        i.idleState = s.hardware.idle_state ^ s.hardware.polarity_mask
        i.run()

    def test_minimal_sequence(self):
        s = Sequence.from_file("./compiler/test_sequences/minimal_sequence.xml")
        c = compiler.Compiler()
        c.TRUNCATE = False
        c.load(s)
        compiled_sequence = c.compile(variant=0)
        print(c.instruction_list.human)
        i = ipu.IPU()
        i.showBuffer = False
        i._RAM = compiled_sequence
        i.nRepeats = 10
        i._spcMemoryRange[0] = (8000, 12000)
        i.idleState = s.HWConfig.idle_state ^ s.HWConfig.polarity_mask
        i.run()

if __name__ == "__main__":
    unittest.main()
