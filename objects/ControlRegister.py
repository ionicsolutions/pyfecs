import xml.etree.ElementTree as ET

from .exceptions import *
from ..compiler.instructions import SetInstruction
from ._object import PyFECSObject

class Bit(PyFECSObject):
    """A single control bit of a :class:`.ControlRegister`\."""
    XML_tag = "bit"
    XML_output = "output"
    XML_input = "input"

    def __init__(self):
        super(Bit, self).__init__()
        self.value = None
        self.input = None
        self.output = None

    @classmethod
    def fromXML(cls, xRoot):
        control_register = cls()
        control_register.XML = xRoot
        return control_register

    @property
    def XML(self):
        xRoot = ET.Element(self.XML_tag)
        if self.value is not None:
            xRoot.text = str(self.value)
        if self.input is not None:
            xRoot.set(self.XML_input, str(self.input))
        if self.output is not None:
            xRoot.set(self.XML_output, str(self.output))
        return xRoot

    @XML.setter
    def XML(self, xRoot):
        try:
            self.value = int(xRoot.text)
        except (ValueError, AttributeError, TypeError):
            raise XMLDefinitionException("Bit value has to be given "
                                         "and an integer.")

        xOutput = xRoot.get(self.XML_output)
        try:
            self.output = int(xOutput)
        except (ValueError, TypeError):
            raise XMLDefinitionException("Bit output channel needs to be "
                                         "given and an integer.")
        xInput = xRoot.get(self.XML_input)
        try:
            self.input = int(xInput)
        except (ValueError, TypeError):
            raise XMLDefinitionException("Bit input channel needs to be "
                                         "given and an integer.")

    def __eq__(self, other):
        return self.value == other.value \
               and self.input == other.input \
               and self.output == other.output

    def verify(self):
        if self.input is None:
            raise InvalidSequenceException("No input channel.", object=self)
        if self.output is None:
            raise InvalidSequenceException("No output channel.", object=self)
        if self.value is None:
            raise InvalidSequenceException("No bit value.", object=self)


class ControlRegister(PyFECSObject):
    """A variable-length bus between the FPGA and the TDC.

    To be able to analyze data for a sequence which contains
    :class:`~objects.jumps.Jump`\s, control pulses have to
    be written into the TDC data. This is achieved by connecting
    FPGA channels directly to the TDC, which are then used as
    a bus.

    The *ControlRegister* describes said bus by linking an
    FPGA *output* channel to a TDC *input* channel and
    assigning a bit position. This information is then used
    by the :class:`~compiler.Compiler` to signal and the
    :class:`~analysis.tracer.Tracer` to extract the order
    the sequence was run in.

    *Example XML configuration:*

    .. code-block:: xml

       <controlRegister>
          <length>5</length>
          <bit output="1" input="3">0</bit>
          <bit output="2" input="4">1</bit>
          <bit output="3" input="6">2</bit>
          <bit output="4" input="2">3</bit>
          <bit output="5" input="5">4</bit>
        </controlRegister>
    """

    XML_tag = "controlRegister"
    XML_length = "length"

    def __init__(self):
        super(ControlRegister, self).__init__()

        self.length = 0
        self.bits = {}

    @classmethod
    def fromXML(cls, xRoot):
        controlRegister = cls()
        controlRegister.XML = xRoot
        return controlRegister

    @property
    def XML(self):
        xRoot = ET.Element(self.XML_tag)
        xLength = ET.SubElement(xRoot, self.XML_length)
        xLength.text = str(self.length)
        for bit in self.bits.itervalues():
            xRoot.append(bit.XML)
        return xRoot

    @XML.setter
    def XML(self, xRoot):
        xLength = xRoot.find(self.XML_length)
        try:
            self.length = int(xLength.text)
        except (ValueError, AttributeError, TypeError):
            raise XMLDefinitionException("Length has to be given and an "
                                         "integer.")

        for xBit in xRoot.findall(Bit.XML_tag):
            try:
                self.bits[int(xBit.text)] = Bit.fromXML(xBit)
            except (ValueError, AttributeError):
                raise XMLDefinitionException("Bit value has to be an integer.")

        if len(self.bits) != self.length:
            raise XMLDefinitionException("Number of defined bits has to be "
                                         "equal to defined length.")

    def __eq__(self, other):
        return self.length == other.length

    def __gt__(self, other):
        return self.length > other.length

    def __lt__(self, other):
        return self.length < other.length

    @property
    def output_channels(self):
        return [b.output for b in self.bits.itervalues()]

    @property
    def input_channels(self):
        return [b.input for b in self.bits.itervalues()]

    def verify(self):
        if len(self.bits) != self.length:
            raise InvalidSequenceException("Number of defined bits has to be "
                                           "equal to defined length.",
                                           object=self)

        if len(self.bits.keys()) != len(set(self.bits.keys())):
            raise InvalidSequenceException("Defined bit values need to be "
                                           "unique.", object=self)

        if sorted(self.bits.keys()) != range(self.length):
            raise InvalidSequenceException("All bits from 0 to length-1 need "
                                           "to be defined.", object=self)

        for value, bit in self.bits.iteritems():
            if bit.value != value:
                raise InvalidSequenceException("Register value does not "
                                               "equal bit value.",
                                               object=self)
            bit.verify()

        if len(self.output_channels) != len(set(self.output_channels)):
            raise InvalidSequenceException("Output channels are not unique.",
                                           object=self)

        if len(self.input_channels) != len(set(self.input_channels)):
            raise InvalidSequenceException("Input channels are not unique.",
                                           object=self)

    def value_to_state(self, value):
        """Convert an integer to the corresponding output-bus state."""
        if value > 2**self.length - 1:
            raise ValueError("Value exceeds register length.")
        state = 0
        for bit, config in self.bits.iteritems():
            bit_value = (value >> bit) & 1
            state += bit_value << config.output
        return state

    def state_to_value(self, state):
        """Convert an output-bus state to the corresponding integer."""
        value = 0
        for bit, config in self.bits.iteritems():
            bit_mask = 1 << config.output
            bit_value = (state & bit_mask) >> config.output
            value += bit_value << bit
        return value

    def control_pulse_to_value(self, tdc_state):
        """Convert a TDC input state to the corresponding integer."""
        value = 0
        for bit, config in self.bits.iteritems():
            bit_mask = 1 << config.input
            bit_value = (tdc_state & bit_mask) >> config.input
            value += bit_value << bit
        return value

    @property
    def input_mask(self):
        mask = 0
        for config in self.bits.itervalues():
            mask += 1 << config.input
        return mask

    @property
    def mask(self):
        mask = 0
        for config in self.bits.itervalues():
            mask += 1 << config.output
        return mask

    @property
    def negative_mask(self):
        mask = (2**SetInstruction.OUTPUT_BUS_LENGTH)-1
        for config in self.bits.itervalues():
            mask -= 1 << config.output
        return mask
