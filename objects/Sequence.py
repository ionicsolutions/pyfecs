"""Instruction sequence for the FECS Pulse Sequencer FPGA.

An instruction sequence is a schedule which for each point in time
in the sequence unambiguously describes the state of each physical
output channel of the Pulse Sequencer FPGA. Typically, such a
sequence is run back-to-back several thousand times. The sequence
also describes which time windows should be read from which counter
channel.

In PyFECS, a sequence is an instance of the :class:`.Sequence` class.
It can be imported from and exported to an XML file for convenient
storage, but also constructed on-the-fly.

When an instruction sequence is to be run, the :class:`Sequence` instance is
compiled to instructions for the FPGA using :class:`compiler.Compiler.
"""
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString

import _Sequence_operations
import _Sequence_verification

from .HardwareConfig import HardwareConfig
from ._object import PyFECSObject
from .channels import OutputChannel, CounterChannel, ControlChannel
from .exceptions import *
from .jumps import End
from .variables import ControlVariable


class Sequence(PyFECSObject):
    """

    :param name: Name of the sequence
    :param shots: Number of shots (samples) taken per variant.
    :param variants: Number of variants the sequence should be run.
    :param length: Total length of the sequence.
    :type name: str
    :type shots: int
    :type variants: int
    :type length: int or float

    *Example XML configuration:*

    .. code-block:: xml

       <sequence>
          <name>example sequence</name>
          <length>200.0</length>
          <shots>1000</shots>
          <variants>30</variants>
          <hardwareConfig>
             ...
          </hardwareConfig>
          <channel>
             ...
          </channel>
          ...
          <counter>
             ...
          </counter>
          ...
       </sequence>
    """
    XML_tag = 'sequence'
    XML_length = 'length'
    XML_name = 'name'
    XML_shots = 'shots'
    XML_shots_legacy = 'nRepeats'
    XML_variants = 'variants'
    XML_variants_legacy = 'nSamples'

    TIME_UNIT = 10**-6 # seconds

    def __init__(self, name="unnamed",
                 shots=1, variants=1, length=10):
        super(Sequence, self).__init__()

        # Name of sequence
        self.name = name

        # Number of times each variant is repeated to gather statistics
        self.shots = int(shots)

        # Number of different variants of the run-unit that are to be made
        # (samples)
        self.variants = int(variants)

        # Sequence length in us
        self.length = float(length)

        # Output and counter channels contain the SequenceChannels,
        # i.e. the logical channels with time windows etc.
        self._output_channels = []
        self._counter_channels = []
        self._control_channels = []

        # Control variables
        self.control_variables = []

        # Hardware configuration
        self.hardware = HardwareConfig()

    @classmethod
    def from_file(cls, xmlFile):
        sequence = cls()
        sequence.load_XML(xmlFile)
        return sequence

    @classmethod
    def from_XML(cls, xRoot):
        sequence = cls()
        sequence.XML = xRoot
        return sequence

    @property
    def static(self):
        if self.jumps:
            return False
        else:
            return True

    @property
    def XML(self):
        xRoot = ET.Element(self.XML_tag)

        xName = ET.SubElement(xRoot, self.XML_name)
        xName.text = str(self.name)

        xLength = ET.SubElement(xRoot, self.XML_length)
        xLength.text = str(self.length)

        xNShots = ET.SubElement(xRoot, self.XML_shots)
        xNShots.text = str(self.shots)

        xNVariants = ET.SubElement(xRoot, self.XML_variants)
        xNVariants.text = str(self.variants)

        xRoot.append(self.hardware.XML)

        for element in self.control_variables:
            xRoot.append(element.XML)

        for channel in self._output_channels:
            xRoot.append(channel.XML)

        for channel in self._counter_channels:
            xRoot.append(channel.XML)

        for channel in self._control_channels:
            xRoot.append(channel.XML)

        return xRoot

    @XML.setter
    def XML(self, xRoot):
        """Load sequence from XML element tree."""

        if xRoot.tag != self.XML_tag:
            raise XMLParseException("Bad tag for %s" % str(self.__class__))

        xName = xRoot.find(self.XML_name)
        if xName is not None:
            self.name = str(xName.text)
        else:
            self.logger.warning("Loaded sequence has no name.")

        xLength = xRoot.find(self.XML_length)
        if xLength is not None:
            self.length = float(xLength.text)
        else:
            self.logger.warning("Loaded sequence '%s' has no specified length.",
                                self.name)

        xOutputChannels = xRoot.findall(OutputChannel.XML_tag)
        if xOutputChannels is not None:
            for xChannel in xOutputChannels:
                self._output_channels.append(OutputChannel.fromXML(xChannel))
        else:
            self.logger.warning("Loaded sequence '%s' has no output channels.",
                                self.name)

        xCounterChannels = xRoot.findall(CounterChannel.XML_tag)
        if xOutputChannels is not None:
            for xChannel in xCounterChannels:
                self._counter_channels.append(CounterChannel.fromXML(xChannel))
        else:
            self.logger.warning("Loaded sequence '%s' has no counter channels.",
                                self.name)

        xControlChannels = xRoot.findall(ControlChannel.XML_tag)
        for xChannel in xControlChannels:
            self._control_channels.append(ControlChannel.fromXML(xChannel))

        xHWConfig = xRoot.find(HardwareConfig.XML_tag)
        # FUTURE: Allow for multiple hardware configurations
        if xHWConfig is None:
            self.logger.warning("Loaded sequence '%s' has no hardware "
                                "configuration.", self.name)
            self.hardware = HardwareConfig()
        else:
            self.hardware = HardwareConfig.from_XML(xHWConfig)

        xVariants = xRoot.find(self.XML_variants)
        if xVariants is None:
            xVariants = xRoot.find(self.XML_variants_legacy)
        if xVariants is not None:
            try:
                self.variants = int(xVariants.text)
            except ValueError:
                raise XMLDefinitionException("Value for tag %s has to be "
                                             "compatible to integer."
                                             % self.XML_variants)
        else:
            self.logger.warning("Loaded sequence '%s' has no defined number"
                                "of variants. Default to %d.",
                                self.name, self.variants)

        xShots = xRoot.find(self.XML_shots)
        if xShots is None:
            xShots = xRoot.find(self.XML_shots_legacy)
        if xShots is not None:
            try:
                self.shots = int(xShots.text)
            except ValueError:
                raise XMLDefinitionException("Value for tag %s has to be "
                                             "compatible to integer."
                                             % self.XML_shots)
        else:
            self.logger.warning("Loaded sequence '%s' has no defined number"
                                "of shots. Default to %d.",
                                self.name, self.shots)

        xOutputChannels = xRoot.findall(ControlVariable.XML_tag)
        for xChannel in xOutputChannels:
            self.control_variables.append(ControlVariable.fromXML(xChannel))

        try:
            self.verify()
        except InvalidSequenceException as e:
            self.logger.warning("Loaded a sequence which is invalid and "
                                "will not compile: %s", e)

    def load_XML(self, xmlFile):
        xTree = ET.parse(xmlFile)
        xRoot = xTree.getroot()
        self.XML = xRoot

    def get_XML(self):
        xTree = ET.ElementTree()
        xTree._setroot(self.XML)

        # Format XML output
        dataString = ET.tostring(self.XML)
        dataString = dataString.replace('\n', '')
        dataString = dataString.replace('\t', '')
        xmlOutput = parseString(dataString).toprettyxml(encoding="utf-8")
        return xmlOutput

    def save_XML(self, xml_file):
        with open(xml_file, 'w') as f:
            f.write(self.get_XML())

    @property
    def sequence_channels(self):
        return (self._output_channels + self._counter_channels
                + self._control_channels)

    @property
    def compiler_channels(self):
        return self._output_channels + self._control_channels

    @property
    def output_channels(self):
        return {channel.name: channel for channel in self._output_channels}

    @property
    def counter_channels(self):
        return {channel.name: channel for channel in self._counter_channels}

    @property
    def control_channels(self):
        return {channel.name: channel for channel in self._control_channels}

    @property
    def time_windows(self):
        """All TimeWindows in the sequence."""
        time_windows = {}
        for channel in self._output_channels + self._counter_channels \
                + self._control_channels:
            for name, window in channel.time_windows.iteritems():
                if name in time_windows:
                    raise InvalidSequenceException(
                        msg="TimeWindow names are not unique.",
                        object=self)
                time_windows[name] = window
        return time_windows

    @property
    def jumps(self):
        """All Jumps in the sequence."""
        jumps = {}
        for channel in self._control_channels:
            for jump in channel.jumps:
                if jump.name in jumps:
                    raise InvalidSequenceException(
                        msg="Jump names are not unique.",
                        object=self)
                else:
                    jumps[jump.name] = jump
        return jumps

    @property
    def ends(self):
        """All Ends in the sequence."""
        ends = {}
        for name, jump in self.jumps.iteritems():
            if isinstance(jump, End):
                ends[name] = jump
        return ends

    def get_control_variables(self, all=False):
        """Return the names of all
        :class:`~objects.variables.ControlVariable`\s used in the sequence.

        .. warning:: All :class:`~objects.timePoints.Reference`\s need to
                     be resolved, otherwise variables used only in references
                     will not be returned unless *all* is *True*.

        :param all: If *False*, only return the names of variables used in
                    the sequence.
        :type all: bool
        :return:
        :rtype: list
        """
        if all:
            return [cVar.name for cVar in self.control_variables]
        control_variables = []
        for channel in self.sequence_channels:
            control_variables += channel.control_variables
        # Remove duplicates
        control_variables = list(set(control_variables))
        return control_variables

    def verify(self):
        """Determine whether the sequence is consistent and can be compiled.

        .. note:: All variants are checked individually, which necessarily
                  makes the raised exceptions ambiguous, as e.g. time windows
                  might only overlap for certain variants, but
                  :meth:`objects.TimeWindow.verify` does not know for
                  which variant it was called. To assist in debugging these
                  kinds of problems, a *DEBUG* level log message indicating
                  the currently checked variant is emitted.

        :return: Nothing.
        :raises objects.exceptions.InvalidSequenceException: When the sequence
                                                               cannot be
                                                               compiled/run.
        """
        self.hardware.verify()
        if self.length < 1 or self.length is None:
            # This length requirement is somewhat arbitrary, in principle a
            # sequence length can be as short as twice the FPGADelayUnit
            raise InvalidSequenceException(msg="Length has to be at least 1.",
                                           object=self)
        if self.variants < 1 or self.variants is None:
            raise InvalidSequenceException(
                msg="Number of variants cannot be less than 1.",
                object=self)
        if self.shots < 1 or self.shots is None:
            raise InvalidSequenceException(
                msg="Number of shots cannot be less than 1.",
                object=self)
        for controlVariable in self.control_variables:
            controlVariable.verify()
        for time_window in self.time_windows:
            if time_window[0] == "_":
                raise InvalidSequenceException(
                    msg="TimeWindow names are not allowed to start with "
                        "leading underscore ('%s' invalid)." % time_window,
                    object=self
                )
        if len(self.time_windows.keys() + self.jumps.keys()) \
           != len(set(self.time_windows.keys() + self.jumps.keys())):
            raise InvalidSequenceException(
                msg="TimeWindows and Jumps cannot share names.",
                object=self)
        self.resolve_references()
        for variant in range(self.variants):
            self.logger.debug("Verifying variant %i of %i.",
                              variant, self.variants)
            self._verify_variant(variant, self.length)

    def _verify_variant(self, variant, length):
        control_values = self.get_control_values(variant)
        for channel in self.sequence_channels:
            channel.verify(control_values, length)

        jump_destinations = self.get_jump_destinations(variant, passing=False)
        for channel in self._control_channels:
            channel.verify_window_links(control_values, jump_destinations)
            channel.verify_order(control_values)

        jump_times = [jump.time.get_time(control_values) for jump in
                      self.jumps.itervalues()]
        if len(jump_times) != len(set(jump_times)):
            # Note: It might be that the jumps are scheduled for the same
            # FPGA time even though the times here are different, but in this
            # case it is still clear which jump is supposed to happen first.
            raise InvalidSequenceException(msg="Jumps with identical time in "
                                               "variant %i." % variant,
                                           object=self)

        start_times = [window.get_times(control_values)[0]
                       for window in self.time_windows.values()]
        end_times = [window.get_times(control_values)[1]
                     for window in self.time_windows.values()]
        window_times = start_times + end_times
        if len(set(window_times)) + len(jump_times)\
                != len(set(window_times + jump_times)):
            raise InvalidSequenceException(
                msg="At least one StartPoint/EndPoint with the same "
                    "time as a JumpPoint in variant %i." % variant,
                object=self)

        tree = _Sequence_verification.Tree(self, control_values)
        tree.build()
        try:
            tree.check()
        except InvalidSequenceException as e:
            tree.visualize()
            raise e

    def resolve_references(self):
        """Resolve all :class:`~objects.timePoints.Reference`\s in the
        sequence.

        Calls :meth:`~objects.timePoints.Reference.resolve` for each
        :class:`~objects.timePoints.Reference`. If there is a
        :class:`Reference` which cannot be resolved,
        :class:`~objects.exceptions.InvalidReferenceException` will be raised
        by the :class:`Reference`\s :meth:`verify` method.
        """
        for timeWindow in self.time_windows.values():
            timeWindow.resolve_references(sequence=self)
        for controlChannel in self._control_channels:
            for jump in controlChannel.jumps:
                jump.resolve_references(sequence=self)

    def get_count_windows(self, variant=0):
        """Return the count windows for the given variant.

        :param variant:
        :type variant: int
        :return:
        :rtype: dict
        """
        control_values = self.get_control_values(variant)
        count_windows = {}
        for name, channel in self.counter_channels.iteritems():
            channel_windows = {window.name : window.get_times(control_values)
                               for window in channel.time_windows.itervalues()}

            count_windows[name] = channel_windows
        return count_windows

    def get_jump_destinations(self, variant=0, passing=False):
        """Return a list with timestamps of all destinations of Jumps.

        :param variant:
        :param passing: Consider the JumpPoint of a Jump which has a Condition
                        without a Destination to be a jump destination.
        :type variant: int
        :type passing: bool
        :rtype: list
        """
        jump_destinations = []
        control_values = self.get_control_values(variant)
        for controlChannel in self._control_channels:
            for jump in controlChannel.jumps:
                jump_destinations += jump.get_destinations(control_values,
                                                           passing)
        return jump_destinations

    def get_control_values(self, variant=0):
        """Return the values of all
        :class:`~objects.variables.ControlVariable`\s for the given *variant*.

        :param variant: The variant the values are to be computed for.
        :type variant: int
        :return: Dictionary with the variable names as keys.
        :rtype: dict
        :raise FECSException: When the *variant* exceeds the configured number
                              of variants.
        """
        if variant >= self.variants:
            raise FECSException("Variant (%d) cannot exceed number of"
                                " variants (%d)." % (variant, self.variants))
        control_values = {}
        for c in self.control_variables:
            control_values[c.name] = c.getValue(variant, self.variants)
        self.logger.debug("control_values: %s", control_values)
        return control_values

    def latest_time_point(self, variant=0):
        """Find the latest :class:`~objects.timePoints.TimePoint`
        in the sequence for the given *variant*.

        This corresponds to the latest end of a
        :class:`~objects.TimeWindow.TimeWindow` or the latest time of a
        :class:`~objects.jumps.Jump`, whichever is later.

        Used by :meth:`compile.compileSequence` for sequence
        truncation.

        :param variant:
        :type variant: int
        :return: End time of the latest time window in the sequence.
        :rtype: float
        :raise FECSException: When a sequence truncated to the end of the latest
                              :class:`~objects.TimeWindow.TimeWindow` is not
                              valid. This can only happen when there is an even
                              later :class:`~objects.timePoints.TimePoint`
                              which was not found by the algorithm.
        """
        control_values = self.get_control_values(variant)
        latest = 0
        for timeWindow in self.time_windows.values():
            latest = max(latest, timeWindow.end.get_time(control_values))
        try:
            self._verify_variant(variant, length=latest)
        except InvalidSequenceException as e:
            # If this happens, this is a programming error in PyFECS
            raise FECSException("Truncated sequence is no longer valid: %s"
                                % e)
        else:
            if latest:
                return latest
            else:
                self.logger.warning("There are no TimePoints in the sequence.")
                return self.length

    def __add__(self, other):
        """Combine two sequence objects into a new, longer sequence.

        Allows the user to conveniently combine several loaded sequence
        objects and use the new sequence directly and/or save it to a file:

            initialize = sequence("initialize.xml")
            rabi = sequence("rabi_200us.xml")
            delay = sequence(name="delay", sLength=50)
            measurement = initialize + rabi + delay
            measurement.exportXML("measurement.xml")

        The number of shots (*nShots*) and variants (*nVariants*) is taken from
        the first sequence. The hardware configuration will be generated from
        the channel data to ensure that everything is covered. Names of time
        windows will be assigned their original sequence's name as a prefix.

        Variables will not be shared between the different partial
        sequences, but prefixed. This allows for convenient editing of the
        XML file should the user wish to combine some of these variables.
        """
        if isinstance(other, Sequence):
            return _Sequence_operations.add(self, other)
        else:
            raise ValueError("Can only add Sequence instances.")

    def __mul__(self, other):
        """Combine *other* instances of the sequence to a single sequence.

        :param other:
        :type other: int
        :return: Combined sequence instance.
        :raise ValueError: When *other* is not int or compatible.
        """
        if isinstance(other, int):
            newSequence = self
            for i in range(other - 1):
                newSequence += self
            return newSequence
        else:
            raise ValueError("Can only multiply by integer-compatible values. "
                             "Received type %s instead.", type(other))

    def __div__(self, other):
        """Split the sequence object into two new, shorter sequence objects.

            init, readout = long_sequence / 120

        :param other:
        :type other: float
        :return: 2-tupel of split sequences
        """
        try:
            splitTime = float(other)
        except ValueError:
            raise ValueError("Division point needs to be compatible to float.")

        if not 0.0 < splitTime < self.length:
            raise ValueError("Division point needs to be positive and has to "
                             "lie within the sequence.")

        return _Sequence_operations.split(self, other)

