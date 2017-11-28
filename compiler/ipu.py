"""Python IPU for testing, debugging, and educational purposes."""
import random


class IPUException(Exception):
    pass


class IPU(object):
    """Python implementation of the PulseSequencer IPU, including the
    full instruction set (WAIT, JUMP, SET, END) introduced in 2017.

    Relevant input/output wires are modeled as properties. Properties
    with a leading underscore have no counterpart in the actual IPU.

    The SPC counter channels produce random values, the range from
    which these values are drawn needs to be set according to the
    sequence.

    .. warning: This IPU is for testing only and is not guaranteed
                to always behave the same way as the actual
                PulseSequencer IPU.
    """
    MAX_JUMPS = 100  # maximum number of jumps without reaching the end

    def __init__(self):
        self._RAM = []
        self.programCounter = 1
        self.outputBus = 0
        self.nRepeats = 1
        self._spcMemoryRange = [(0, 0), (0, 0)]
        self.idleState = 0

        self.showBuffer = True

    @property
    def RAM(self):
        return [0] + self._RAM  # IPU RAM addresses start at 1

    @RAM.setter
    def RAM(self, value):
        self._RAM = value

    @property
    def _instructionType(self):  # DEBUGGING
        """The upper two bits denote the instruction type:

        - 00: WAIT (enter delay mode)
        - 01: JUMP
        - 10: SET (write new output buffer)
        - 11: END

        For more details, see *compiler.instructions*.
        """
        return (self.instructionRamData & (3 << 30)) >> 30

    @property
    def instructionRamData(self):  # input [31:0] instructionRamData
        """The current instruction."""
        return self.RAM[self.instructionRamAddress]

    @property
    def _jumpThreshold(self):  # DEBUGGING
        """The threshold of a conditional JUMP."""
        return (self.instructionRamData >> 10) & (2 ** 16 - 1)

    @property
    def instructionRamAddress(self):  # output [9:0] instructionRamAddress
        return self.programCounter

    @property
    def spcValue(self): # input [15:0] spcValue
        return random.randint(*self._spcMemoryRange[self.spcId])

    @property
    def spcId(self):  # output spcId
        return self.instructionRamData & (26 << 1)

    def run(self):
        outputBusBuffer = self.idleState

        self.programCounter = 1
        delayCounter = 0
        running = True
        cycleCounter = 1

        _jumpCounter = 0
        _time = 0
        if self.showBuffer:
            print("Idle %s" % format(outputBusBuffer, "#034b"))
        while running:
            # DEBUGGING
            if self.showBuffer:  # show the current instruction we are processing
                print(format(self.instructionRamAddress, "#04"),)
            # /DEBUGGING
            if delayCounter == 0:  # NOT IN DELAY MODE
                if self._instructionType == 0:  # WAIT
                    delayCounter = self.instructionRamData & (2 ** 30) - 1
                    self.programCounter += 1
                elif self._instructionType == 1:  # JUMP
                    if _jumpCounter > self.MAX_JUMPS:
                        raise IPUException

                    if self.instructionRamData & (1 << 29):  # ALWAYS JUMP
                        _jumpCounter += 1
                        self.programCounter = self._jumpDestination
                    else:  # JUMP WHEN ABOVE THRESHOLD
                        if self.spcValue >= self._jumpThreshold:
                            _jumpCounter += 1
                            self.programCounter = self.instructionRamData & ((2 ** 10) - 1)
                        else:  # PASS
                            self.programCounter += 1
                elif self._instructionType == 2:  # SET
                    outputBusBuffer = self.instructionRamData & (2 ** 24) - 1
                    self.programCounter += 1
                elif self._instructionType == 3:  # END
                    _jumpCounter = 0
                    self.programCounter = 1
                    if cycleCounter == self.nRepeats:  # TOOK ALL SHOTS
                        running = False
                        cycleCounter = 1
                        outputBusBuffer = self.idleState
                    else:
                        cycleCounter += 1  # TAKE NEXT SHOT
                # DEBUGGING
                else:
                    # we do not recognize the instruction
                    raise IPUException

                if self.showBuffer:
                    print(format(outputBusBuffer, "#034b"))
                # /DEBUGGING
            else:  # IN DELAY MODE
                delayCounter -= 1
            self.outputBus = outputBusBuffer  # UPDATE THE OUTPUT
            _time += 1
        print("Took %d steps to execute sequence. %d" %
              (_time, cycleCounter))
