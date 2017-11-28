"""The PyFECS compiler converts a :class:`~FECSTypes.sequence.Sequence` object
into a byte sequence which can be processed by the FECS Pulse Sequencer FPGA's
Internal Processing Unit (IPU).

The PyFECS compiler was written by Tim Ballance and improved by Kilian Kluge.

**Significant changes** in chronological order:

- *057975b1bd845e9b4b97b4c3b724be0c11a78555:* Fix for sequences where the
  initial state does not match the idle state (*fixInitialState*)
- *1c156bb5f9b29163d6cbe67bace1845250317849:* Do not add empty time windows to
  the instruction list
- *0562de24975b7a7cb8ed874f66245e9dd477c44a:* Automatic truncation of
  sequences to the end of the last window (*truncate* argument)
- *a4232d3704e56c28b3926081a2fdb1f2114e8b0a:* Fixed breaking bug: the
  *end of sequence* instruction was not added when there was a *set* instruction
  on the second-to-last time step
- *0871028d7b43059f858fc47b4069e9e8725d4232*: Fixed automatic truncation of
  time windows to the end of the sequence to ensure that the termination does
  not lie outside of the specified sequence length
"""
import logging
import numpy as np

from ..objects.exceptions import *

logger = logging.getLogger("PyFECS.compile")


def compileSequence(sequence, variant=0, fixInitialState=True, truncate=False):
    """Compile the given *sequence* for the given *variant*.

    :param sequence: The :class:`~objects.Sequence.Sequence` instance to be
                     compiled.
    :param variant: The variant to be compiled for. Irrelevant for sequences
                    without non-constant variables.
    :param fixInitialState: If *True*, the compiler ensures that
                            the initial state of the sequence is correctly
                            set even if it differs from the idle state of
                            the FPGA.
    :param truncate: Shorten the sequence to the end of the last timeWindow.
                     This allows for massive reductions in measurement time,
                     but needs to be considered during processing of counter
                     data.
    :type sequence: FECSTypes.Sequence.Sequence
    :type variant: int
    :type fixInitialState: bool
    :type truncate: bool
    :return: Compiled sequence to be sent to the FECSFPGA HWDM
    :rtype: list
    :raises CompilerErrorException: Compiler reaches an invalid state.
    :raises InvalidSequenceException: The passed sequence object is not valid.
    """

    try:
        sequence.verify()
    except InvalidSequenceException as e:
        logger.error("Invalid sequence. Aborting compilation.")
        raise e

    # Evaluate all controlVariables in the sequence for the given variant
    controlValues = sequence.get_control_values(variant)

    # ROUGH INSTRUCTION LIST
    # Pass through the sequence to generate a rough instruction list
    instructionList = []

    # This mask indicates which channels have negative polarity
    polarityMask = np.uint32()

    # Sequence length
    if truncate:
        sequenceLength = sequence.latest_time_point(variant)
        logger.info("Truncated sequence to %0.2f (Speedup of %0.1f \%)",
                    sequenceLength, 1-sequenceLength/sequence.length)
    else:
        sequenceLength = sequence.length

    # FPGA delay counter interval
    fpgaDelayUnit = sequence.HWConfig.fpga_delay_unit

    # Sequence length rounded to FPGA time
    sequenceLengthR = np.around(sequenceLength / fpgaDelayUnit)

    for name, channel in sequence.output_channels.iteritems():
        channelId = sequence.HWConfig.fpga_channels[name].channelID
        polarity = sequence.HWConfig.fpga_channels[name].polarity

        # Set the polarity mask if the polarity is negative
        if not polarity:
            logger.debug("Negative polarity for channel %d" % channelId)
            polarityMask |= 1 << channelId

        for wname, window in channel.time_windows.iteritems():
            startTime, endTime = window.get_times(controlValues)

            # Round start and end times to FPGA time
            startTimeR = np.around(startTime / fpgaDelayUnit)
            endTimeR = np.around(endTime / fpgaDelayUnit)

            # If the window has length 0, do not add it. This can happen
            # when a variable window runs from (start, start) to (start, end)
            if startTimeR - endTimeR == 0:
                logger.warning("TimeWindow %s has length 0. Skipping.",
                               window.name)
                continue

            # If the end time of the pulse doesn't fit within the sequence,
            # truncate it. The last instruction time step is
            # (sequenceLengthR-1) and is reserved for the 'end of sequence'
            # instruction
            if endTimeR >= (sequenceLengthR - 1):
                logger.info("TimeWindow %s truncated to fit within sequence.",
                            window.name)
                endTimeR = sequenceLengthR - 2

            instructionList.append((startTimeR, channelId, 1))
            instructionList.append((endTimeR, channelId, 0))

    # Get FPGA's idle state, i.e. the physical state of the outputs when
    # no sequence is run.
    idleState = sequence.HWConfig.idle_state ^ polarityMask

    # Get the initial state, i.e. the logical state of each output channel
    # at the beginning of the sequence (t=0)
    #initialState = sequence.getInitialState(controlValues)

    #if (initialState ^ polarityMask) != idleState:
    #    logger.warning("The state at the beginning of the sequence is not "
    #                   "the same as the idle state of the FPGA outputs.")
    #    logger.debug("initial: %s (physical: %s), idle: %s, polarity: %s",
    #                 bin(initialState), bin(initialState ^ polarityMask),
    #                 bin(idleState), bin(polarityMask))
    #    if fixInitialState:
    #        logger.warning("Fixing this now.")
    #        diff = (initialState ^ polarityMask) ^ idleState
    #        logger.debug("Diff: %s", bin(diff))
    #        for channel in range(16):
    #            if 1 & (diff >> channel):
    #                idleValue = 1 & ((idleState ^ polarityMask) >> channel)
    #                initialValue = 1 & (initialState >> channel)
    #                logger.debug("Channel: %i, Idle: %i, Initial: %i",
    #                             channel, idleValue, initialValue)
    #                if initialValue == 0:  # only when there is not a window
    #                                       # starting at t=0 anyway
    #                    instructionList.append((0, channel, 0))

    instructionList = np.array(instructionList, dtype=np.uint32)
    # Sort by time
    instructionList = instructionList[instructionList[:, 0].argsort()]

    # CONDENSED INSTRUCTION LIST
    condensedInstructionList = np.zeros((len(instructionList[:, 0]), 2),
                                        dtype=np.uint32)

    # Initialise the current state to be the idle state
    currentState = idleState

    i = 0
    condensedIndex = 0
    while i < len(instructionList[:, 0]):

        # First, search ahead of this instruction for other instructions with
        # the same time
        j = i + 1
        while j < len(instructionList[:, 0]) and \
                        instructionList[j, 0] == instructionList[i, 0]:
            j += 1
        j -= 1
        # Now j is the last element with the same time as i
        newState = currentState

        while i <= j:

            # Calculate the value of this bit
            # instructionList[:,2] contains the logical value

            if polarityMask & (1 << instructionList[i, 1]) != 0:
                # If the polarity is negative, flip the physical value
                physicalValue = int(instructionList[i, 2] != 1) << \
                                instructionList[i, 1]
            else:
                physicalValue = instructionList[i, 2] << instructionList[i, 1]

            # The physical value is then set in the newState
            # Clear the bit
            newState &= ~(1 << instructionList[i, 1])
            # Set the bit if needed
            newState |= physicalValue

            i += 1

        condensedInstructionList[condensedIndex, 0] = instructionList[j, 0]
        condensedInstructionList[condensedIndex, 1] = newState
        condensedIndex += 1
        currentState = newState

    # Truncate the list
    condensedInstructionList = condensedInstructionList[:condensedIndex]

    # FINAL INSTRUCTION LIST
    # Need 2 instructions per transition
    finalInstructionList = np.zeros(len(condensedInstructionList[:, 0]) * 2 + 2,
                                    dtype=np.uint32)

    currentTime = 0
    fIndex = 0
    for i in range(len(condensedInstructionList[:, 0])):

        # Work out what the set instruction should be
        setInstruction = condensedInstructionList[i, 1] | 0x80000000

        # Calculate period between the last transition and this one
        thisWaitPeriod = condensedInstructionList[i, 0] - currentTime

        if thisWaitPeriod == 0:
            # There is no need for a wait instruction
            finalInstructionList[fIndex] = setInstruction
            fIndex += 1
            currentTime += 1
        elif thisWaitPeriod > 0:
            # Wait for the right time
            finalInstructionList[fIndex] = thisWaitPeriod - 1
            finalInstructionList[fIndex + 1] = setInstruction
            fIndex += 2
            currentTime += thisWaitPeriod + 1
        else:
            raise CompilerErrorException("Negative wait period: %d"
                                         % thisWaitPeriod)

    # ADD TERMINATION
    # The 'end of sequence' instruction has to sit at (sequenceLengthR - 1)
    # Check whether we need to add a final wait to reach that time
    thisWaitPeriod = (sequenceLengthR - 1) - currentTime
    if thisWaitPeriod > 0:
        logger.debug("Adding final wait period: %d", thisWaitPeriod)
        finalInstructionList[fIndex] = thisWaitPeriod - 1
        fIndex += 1
    elif thisWaitPeriod == 0:
        logger.debug("No final wait period.")
    else:
        raise CompilerErrorException("Negative final wait period: %d"
                                     % thisWaitPeriod)

    # Now we add a termination
    finalInstructionList[fIndex] = 3 << 30 # 0x7FFFFFFF
    fIndex += 1

    # Truncate the list
    finalInstructionList = finalInstructionList[:fIndex]
    compiledLength = sequenceLengthR*fpgaDelayUnit

    return finalInstructionList, compiledLength

