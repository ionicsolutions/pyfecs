"""A FECS sequence describes the state of different channels at different times.

In PyFECS, there are two base types of channels:

- **Hardware channels** describe physical channels directly accessible to the
  experimenter, i.e. outputs or inputs.
- **Sequence channels** describe logical channels in a sequence, which are
  turned on and off during the sequence.

Sequence channels are linked to hardware channels by their `name` attribute.
This allows for the use of the very same (logical) sequence on different
(physical) setups. The :class:`~FECSTypes.HardwareConfig.HardwareConfig`
therefore needs to contain a physical channel for each logial channel used
in the sequence.

All channels are derived from the common base class :class:`Channel`.
"""
import xml.etree.ElementTree as ET

import numpy as np

from .TimeWindow import TimeWindow
from ._object import PyFECSObject
from .exceptions import *
from .jumps import ConditionalJump, End, GoTo
from .names import getName


class Channel(PyFECSObject):
    """Base class for all channels."""
    XML_tag = ''
    XML_tag_legacy = ''
    XML_name = 'name'

    def __init__(self):
        super(Channel, self).__init__()
        self.name = ""

    @classmethod
    def fromXML(cls, xRoot):
        channel = cls()
        channel.XML = xRoot
        return channel

    def _get_XML(self):
        xRoot = ET.Element(self.XML_tag)

        xName = ET.SubElement(xRoot, self.XML_name)
        xName.text = self.name

        return xRoot

    def _set_XML(self, xRoot):
        xName = xRoot.find(self.XML_name)
        if xName is not None:
            self.name = xName.text
        else:
            self.name = getName()
            self.logger.warning("Unnamed channel. Assigning a placeholder "
                                "to prevent issues later on: '%s'.", self.name)

    XML = property(_get_XML, _set_XML)

    def verify(self, *args, **kwargs):
        """
        :return: Nothing.
        :raise InvalidSequenceException: When *name* is undefined.
        """
        if not self.name:
            raise InvalidSequenceException(msg="Unnamed.", object=self)


class HardwareChannel(Channel):
    """Base class for all hardware channels.

    All channels used in :class:`~objects.HardwareConfig.HardwareConfig`
    inherit from this class.
    """
    XML_ID = 'channelID'

    def __init__(self):
        super(HardwareChannel, self).__init__()

        self.channelID = None

    def __eq__(self, other):
        return self.channelID == other.channelID

    def __ne__(self, other):
        return not self.__eq__(other)

    def _get_XML(self):
        xRoot = super(HardwareChannel, self)._get_XML()
        if self.channelID is not None:
            xID = ET.SubElement(xRoot, self.XML_ID)
            xID.text = str(self.channelID)
        return xRoot

    def _set_XML(self, xRoot):
        super(HardwareChannel, self)._set_XML(xRoot)
        xID = xRoot.find(self.XML_ID)
        if xID is not None:
            self.channelID = int(xID.text)

    XML = property(_get_XML, _set_XML)

    def verify(self):
        """
        :return: Nothing.
        :raises InvalidSequenceException: When *channelID* is undefined or has
                                          a type other than *int*.
        """
        super(HardwareChannel, self).verify()
        if self.channelID is None:
            raise InvalidSequenceException(msg="Without channelID.",
                                           object=self)
        if not isinstance(self.channelID, int):
            raise InvalidSequenceException(msg="ChannelID must be an integer.",
                                           object=self)


class TDCChannel(HardwareChannel):
    """TDC channel, derived from :class:`HardwareChannel`.

    The channel is described by a unique *name* and a *channelID* which
    corresponds to an input channel on the Roentdek TDC cards used on the
    IonCavity experiments.

    *Example XML configuration:*

    .. code-block:: xml

       <counter>
          <name>example TDC channel</name>
          <channelID>5</channelID>
       </counter>
    """
    XML_tag = 'counter'

    def __init__(self):
        super(self.__class__, self).__init__()

    def verify(self):
        """
        :return: Nothing.
        :raise InvalidSequenceException: When the *channelID* is not available
                                         on the IonCavity TDC cards.
        """
        super(TDCChannel, self).verify()
        if self.channelID < 0 or self.channelID > 7:
            raise InvalidSequenceException(msg="ChannelID is outside of range "
                                               "of available channels: %i"
                                               % self.channelID, object=self)


class SPCChannel(HardwareChannel):
    """SequencePulseCounter channel, derived from :class:`HardwareChannel`.

    The channel is described by a unique *name* and a *channelID* which
    corresponds to the channel ID for an SPC on the PulseSequence FPGA.

    *Example XML configuration:*

    .. code-block:: xml

       <sequencePulseCounter>
          <name>example SPC channel</name>
          <channelID>0</channelID>
       </sequencePulseCounter>
    """
    XML_tag = 'sequencePulseCounter'
    XML_gate = 'gate'

    def __init__(self):
        super(self.__class__, self).__init__()

        self.gate = None

    def _get_XML(self):
        xRoot = super(SPCChannel, self)._get_XML()

        xGate = ET.SubElement(xRoot, self.XML_gate)
        if self.gate is not None:
            xGate.text = str(self.gate)

        return xRoot

    def _set_XML(self, xRoot):
        super(SPCChannel, self)._set_XML(xRoot)

        xGate = xRoot.find(self.XML_gate)
        if xGate is not None:
            self.gate = int(xGate.text)
        else:
            raise XMLDefinitionException("sequencePulseCounter requires a "
                                         "gate channel.")

    XML = property(_get_XML, _set_XML)

    def __eq__(self, other):
        return self.gate == other.gate and \
               super(SPCChannel, self).__eq__(other)

    def verify(self):
        super(SPCChannel, self).verify()
        if self.channelID < 0 or self.channelID > 1:
            raise FECSException(msg="ChannelID is outside of range "
                                    "of available channels: %i"
                                    % self.channelID, object=self)

        if self.gate is None:
            raise FECSException(msg="No gate channel.",
                                object=self)

        if not isinstance(self.gate, int):
            raise FECSException(msg="Gate channel has to be integer.")


class FPGAChannel(HardwareChannel):
    """Output channel on the FPGA, derived from :class:`HardwareChannel`.

    The channel is described by a unique *name* and three parameters:

    - *channelID*: The ID of the channel on the FPGA output bus. For the
      standard IonCavity PulseSequencer box, this is an integer between 0 and
      15.
    - *polarity*: If *True*, logical *True* corresponds to a "high" output. If
      *False*, the output is inverted, i.e. a logical *True* corresponds to a
      "low" output.
    - *idle_state*: The logical state this FPGA channel takes on when no
      sequence is run.

    *Example XML configuration:*

    .. code-block:: xml

       <output>
          <name>example channel</output>
          <channelID>4</channelID>
          <polarity>True</polarity>
          <idleState>False</idleState>
       </output>

    """
    XML_tag = 'output'
    XML_tag_legacy = 'channel'
    XML_polarity = 'polarity'
    XML_idleState = 'idleState'
    XML_idleState_legacy = 'finalState'

    def __init__(self):
        super(self.__class__, self).__init__()

        # Polarity of output logic:
        # True means positive is on
        # False means negative is on
        self.polarity = True

        # Logical state the output should be set to after the sequence
        self.idle_state = True

    def __eq__(self, other):
        hardwareMatches = super(FPGAChannel, self).__eq__(other)
        polarityMatches = self.polarity == other.polarity
        idleStateMatches = self.idle_state == other.idle_state
        return hardwareMatches and polarityMatches and idleStateMatches

    def _get_XML(self):
        xRoot = super(FPGAChannel, self)._get_XML()
        xPolarity = ET.SubElement(xRoot, self.XML_polarity)
        xPolarity.text = str(self.polarity)
        xIdleState = ET.SubElement(xRoot, self.XML_idleState)
        xIdleState.text = str(self.idle_state)
        return xRoot

    def _set_XML(self, xRoot):
        super(FPGAChannel, self)._set_XML(xRoot)

        xPolarity = xRoot.find(self.XML_polarity)
        if xPolarity is not None:
            self.polarity = (xPolarity.text.lower() == 'true') or \
                            (xPolarity.text.lower() == '1')
        else:
            self.logger.warning("Channel %s has no defined polarity. "
                                "Defaulting to %s.",
                                self.name, self.polarity)

        xIdleState = xRoot.find(self.XML_idleState)
        if xIdleState is None:
            xIdleState = xRoot.find(self.XML_idleState_legacy)
        if xIdleState is not None:
            self.idle_state = (xIdleState.text.lower() == 'true') or \
                              (xIdleState.text.lower() == '1')
        else:
            self.logger.warning("Channel %s has no defined idle_state. "
                                "Defaulting to %s.",
                                self.name, self.idle_state)

    XML = property(_get_XML, _set_XML)

    def verify(self):
        """
        :return: Nothing.
        :raise InvalidSequenceException: When the *channelID* is not available
                                         on the IonCavity PulseSequencer box.
        """
        super(FPGAChannel, self).verify()
        if self.channelID < 0 or self.channelID > 15:
            raise InvalidSequenceException(msg="ChannelID is outside of range "
                                               "of available channels: %i"
                                               % self.channelID, object=self)


class SequenceChannel(Channel):
    """Logic sequence channel, derived from :class:`Channel`.

    The default state of a :class:`SequenceChannel` is *False*.

    A :class:`SequenceChannel` instance contains an arbitrary amount of
    :class:`~objects.TimeWindow.TimeWindow` instances which determine for
    which periods of time the channel's state is *True*.

    *Example XML configuration:*

    .. code-block:: xml

       <channel>
          <name>example channel</name>
          <window>
             ...
          </window>
          <window>
             ...
          </window>
       </channel>

    """
    XML_tag = 'channel'

    def __init__(self):
        super(SequenceChannel, self).__init__()
        self._time_windows = []

    def __eq__(self, other):
        return self.name == other.name

    def __ne__(self, other):
        return self.name != other.name

    def _get_XML(self):
        xRoot = super(SequenceChannel, self)._get_XML()
        for window in self._time_windows:
            xRoot.append(window.XML)
        return xRoot

    def _set_XML(self, xRoot):
        super(SequenceChannel, self)._set_XML(xRoot)
        xWindows = xRoot.findall(TimeWindow.XML_tag)
        for xWindow in xWindows:
            self._time_windows.append(TimeWindow.fromXML(xWindow))

    XML = property(_get_XML, _set_XML)

    def verify(self, controlValues, length):
        """
        :param controlValues:
        :param length: Length of the sequence variant to be verified.
        :type controlValues: dict
        :type length: float
        :return: Nothing.
        """
        super(SequenceChannel, self).verify()
        for window in self._time_windows:
            window.verify(controlValues, length)

    def getControlVariableNames(self):
        """Return a list of the names of all
        :class:`~objects.variables.ControlVariable`\s used.

        :rtype: list
        """
        nameList = []
        for window in self._time_windows:
            nameList += window.control_variables.keys()
        # Remove duplicates
        nameList = list(set(nameList))
        return nameList

    @property
    def time_windows(self):
        """Return a dictionary with names as keys and
        :class:`~objects.TimeWindow.TimeWindow` instances as values.

        :rtype: dict
        """
        return {window.name: window for window in self._time_windows}


class OutputChannel(SequenceChannel):
    """Logic output channel, derived from :class:`SequenceChannel`.

    During compilation, the logical state is mapped to the physical state of
    the corresponding :class:`FPGAChannel` through
    :class:`~objects.HardwareConfig.HardwareConfig`.
    """
    XML_tag = 'channel'

    def __init__(self):
        super(self.__class__, self).__init__()

    def verify(self, controlValues, length):
        """

        :param controlValues:
        :param length: Length of the sequence variant to be verified.
        :type controlValues: dict
        :type length: float
        :return: Nothing.
        :raise InvalidSequenceException: When
           :class:`~objects.TimeWindow.TimeWindow`\s overlap.
        """
        super(OutputChannel, self).verify(controlValues, length)
        allWindowRanges = []
        for window in self._time_windows:
            allWindowRanges.append(window.get_times(controlValues))
        sortedWindowRanges = sorted(allWindowRanges)
        for i, windowRange in enumerate(sortedWindowRanges):
            try:
                nextWindowsRange = sortedWindowRanges[i + 1]
            except IndexError:
                break
            else:
                if windowRange[1] > nextWindowsRange[0]:
                    raise InvalidSequenceException(
                        "Overlapping TimeWindows in channel '%s'." % self.name,
                        object=self)


class CounterChannel(SequenceChannel):
    """Logic counter channel, derived from :class:`SequenceChannel`.

    A :class:`CounterChannel` is linked to a :class:`TDCChannel` by name. Its
    :class:`~objects.TimeWindow.TimeWindow`\s describe which parts of the
    TDC data will be considered during analysis.

    .. warning:: The :class:`~objects.TimeWindow.TimeWindow`\s defined for a
                 :class:`CounterChannel` are only evaluated during data
                 processing (i.e. not during compilation) and may overlap.

                 Therefore, the number of counts across all
                 :class:`~objects.TimeWindow.TimeWindow`\s may exceed the
                 total number of counts recorded.
    """
    XML_tag = 'counter'

    def __init__(self):
        super(self.__class__, self).__init__()


class ControlChannel(SequenceChannel):
    """Sequence control channel, derived from :class:`SequenceChannel`.

    A :class:`ControlChannel` is linked to a :class:`SPCChannel` by name. It
    contains :class:`~objects.TimeWindow.TimeWindow`\s which are used to
    control corresponding :class:`~objects.jumps.Jump`\s.
    """

    XML_tag = 'control'

    def __init__(self):
        super(ControlChannel, self).__init__()

        self.jumps = []

    def _get_XML(self):
        xRoot = super(ControlChannel, self)._get_XML()
        for jump in self.jumps:
            xRoot.append(jump.XML)
        return xRoot

    def _set_XML(self, xRoot):
        super(ControlChannel, self)._set_XML(xRoot)
        xJumps = xRoot.findall(ConditionalJump.XML_tag)
        for xJump in xJumps:
            self.jumps.append(ConditionalJump.fromXML(xJump))

        xEnds = xRoot.findall(End.XML_tag)
        for xEnd in xEnds:
            self.jumps.append(End.fromXML(xEnd))

        xGoTos = xRoot.findall(GoTo.XML_tag)
        for xGoTo in xGoTos:
            self.jumps.append(GoTo.fromXML(xGoTo))

    XML = property(_get_XML, _set_XML)

    @property
    def conditional_jumps(self):
        conditional_jumps = []
        for jump in self.jumps:
            if isinstance(jump, ConditionalJump):
                conditional_jumps.append(jump)
        return conditional_jumps

    @property
    def number_of_windows(self):
        # verify() guarantees that windows are of nonzero length
        return len(self._time_windows)

    def verify(self, control_values, length):
        super(ControlChannel, self).verify(control_values, length)
        for name, window in self.time_windows.iteritems():
            start_time, end_time = window.get_times(control_values)
            if end_time - start_time < 1:
                # this condition is arbitrary, but all control windows
                # need to be of nonzero length in all variants to
                # ensure that both jumping and SPC readout work
                raise InvalidSequenceException(
                    "TimeWindow '%s' is shorter than the minimal "
                    "length of 1 us." % name, object=self)
        for jump in self.conditional_jumps:
            try:
                time_window = self.time_windows[jump.window]
            except KeyError:
                raise InvalidSequenceException(
                    "TimeWindow '%s' referenced by Jump '%s' not found."
                    % (jump.window, jump.name),
                    object=self
                )
            startTime, endTime = time_window.get_times(control_values)
            if endTime > jump.get_time(control_values):
                raise InvalidSequenceException(
                    "TimeWindow '%s' referenced by Jump '%s' ends after "
                    "JumpPoint." % (jump.window, jump.name),
                    object=self)

    def verify_window_links(self, controlValues, jumpDestinations):
        """Check that there are no jump destinations between this Jump and
        its TimeWindow.
        """
        for jump in self.conditional_jumps:
            time_window = self.time_windows[jump.window]
            startTime, endTime = time_window.get_times(controlValues)
            for destinationTime in jumpDestinations:
                if destinationTime < jump.get_time(controlValues):
                    if destinationTime > startTime:
                        raise InvalidSequenceException(
                            "TimeWindow '%s' referenced by Jump '%s' is not "
                            "guaranteed to be acquired prior to jump because "
                            "there is a jump destination between the "
                            "TimeWindow and the Jump."
                            % (time_window.name, jump.name),
                            object=self)

    def verify_order(self, control_values):
        """Check that there are no other TimeWindows between a Jump and
        its TimeWindow.

        To allow for multiple TimeWindows before a Jump, the FPGA has to
        be changed accordingly. Roughly, the following needs to be done:

        - Convert the spcMemory into a proper memory, i.e. allow for storage
          of more than one value by shifting old values to higher IDs in the
          pattern described below
        - Change the SPC ID in the compiler in the following way:

          channel_id = (actual ID) + (number_of_time_windows_in_between - 1)*2

          As an example: If the sequence is MYWINDOW OTHERWINDOW JUMP and the
          actual SPC channel ID is 0, the channel ID to be sent to the IPU
          is 2 = 0 + 1*2. In other words, even IDs are for channel 0 and odd
          IDs are for channel 1. There are currently 3 bits reserved for the
          SPC ID, so this gives four windows per channel. This should be
          more than enough.

        I did not implement this yet because I first used a simple multiplexer
        as the memory as this was much easier. But the structure to do this
        is all there, one just needs to change the spcMemory module and the
        connection to the IPU (which is currently 1 bit and needs to be 3 bits
        wide).
        """
        jump_times = {jump: jump.get_time(control_values) for jump in
                      self.conditional_jumps}
        window_end_times = \
            {jump: self.time_windows[jump.window].get_times(control_values)[1]
             for jump in self.conditional_jumps}

        for jump, jump_time in jump_times.iteritems():
            differences = jump_time - np.array(window_end_times.values())
            closest = np.min(differences[differences > 0])
            if not closest == jump_time - window_end_times[jump]:
                raise InvalidSequenceException(
                    "TimeWindow '%s' is not the TimeWindow directly "
                    "preceding Jump '%s'. This is not yet supported. "
                    "See docstring of verify_order for detailed instructions.",
                object=self)