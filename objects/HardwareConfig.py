import logging
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString

from .ControlRegister import ControlRegister
from ._object import PyFECSObject
from .channels import FPGAChannel, TDCChannel, SPCChannel
from .exceptions import *


class HardwareConfig(PyFECSObject):
    """Description of the physical configuration of the experiment.

    A :class:`HardwareConfig` is described by its *name* and needs to
    specify a value for the *FPGADelayUnit*, which is the time delay of the
    PulseSequence FPGA internal processing unit's (IPU's) delay counter. As all
    time values in PyFECS, it is given in microseconds.

    A :class:`HardwareConfig` contains an arbitrary number of
    :class:`~objects.channels.HardwareChannel`\s of different kinds. They
    are linked to :class:`~objects.channels.SequenceChannel`\s by name. For
    a sequence to be compiled, run, and analyzed correctly, the used
    :class:`HardwareConfig` needs to contain a channel for each name used in
    the sequence.

    *Example XML configuration:*

    .. code-block:: xml

       <hardwareConfig>
          <name>example setup</name>
          <FPGADelayUnit>0.01</FPGADelayUnit>
          <output>
             ...
          </output>
          ...
          <counter>
             ...
          </counter>
          ...
       </hardwareConfig>
    """
    XML_tag = 'hardwareConfig'
    XML_name = 'name'
    XML_FPGADelayUnit = 'FPGADelayUnit'

    def __init__(self):
        super(HardwareConfig, self).__init__()

        self.name = ""
        self._fpga_channels = []
        self._tdc_channels = []
        self._spc_channels = []
        self.control_register = ControlRegister()

        # Delay unit of FPGA in us
        self.fpga_delay_unit = 0.01

    def __eq__(self, other):
        """Two configurations match when they define the same channels.

        If this is the case, they can be interchanged and a sequence which
        can run on one configuration can also run on the other.
        """
        registers_match = self.control_register == other.control_register
        outputs_match = self.fpga_channels.keys() == other.fpga_channels.keys()
        counters_match = self.tdc_channels.keys() == other.tdc_channels.keys()
        spcs_match = self.spc_channels.keys() == other.spc_channels.keys()
        delays_match = self.fpga_delay_unit == other.fpgaDelayUnit
        return outputs_match and counters_match and spcs_match\
               and delays_match and registers_match

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def from_file(cls, xmlFile):
        xTree = ET.parse(xmlFile)
        xRoot = xTree.getroot()
        hardwareConfig = cls()
        hardwareConfig.XML = xRoot
        return hardwareConfig

    @classmethod
    def from_XML(cls, xRoot):
        hardwareConfig = cls()
        hardwareConfig.XML = xRoot
        return hardwareConfig

    @property
    def XML(self):
        xRoot = ET.Element(self.XML_tag)

        xName = ET.SubElement(xRoot, self.XML_name)
        xName.text = self.name

        xDelayUnit = ET.SubElement(xRoot, self.XML_FPGADelayUnit)
        xDelayUnit.text = str(self.fpga_delay_unit)

        xRoot.append(self.control_register.XML)

        for channel in self.channels:
            xRoot.append(channel.XML)

        return xRoot

    @XML.setter
    def XML(self, xRoot):
        self.name = xRoot.find(self.XML_name).text

        xDelayUnit = xRoot.find(self.XML_FPGADelayUnit)
        try:
            self.fpga_delay_unit = float(xDelayUnit.text)
        except (ValueError, TypeError):
            raise XMLDefinitionException("No or invalid FPGA Delay Unit.")

        xControlRegister = xRoot.find(ControlRegister.XML_tag)
        if xControlRegister is not None:
            self.control_register = ControlRegister.fromXML(xControlRegister)

        xFPGAChannels = xRoot.findall(FPGAChannel.XML_tag)\
                        + xRoot.findall(FPGAChannel.XML_tag_legacy)
        for xFPGAChannel in xFPGAChannels:
            self._fpga_channels.append(FPGAChannel.fromXML(xFPGAChannel))

        xTDCChannels = xRoot.findall(TDCChannel.XML_tag)
        for xTDCChannel in xTDCChannels:
            self._tdc_channels.append(TDCChannel.fromXML(xTDCChannel))

        xSPCChannels = xRoot.findall(SPCChannel.XML_tag)
        for xSPCChannel in xSPCChannels:
            self._spc_channels.append(SPCChannel.fromXML(xSPCChannel))

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
    def channels(self):
        return self._tdc_channels + self._fpga_channels + self._spc_channels

    @property
    def fpga_channels(self):
        return {channel.name: channel for channel in self._fpga_channels}

    @property
    def spc_channels(self):
        return {channel.name: channel for channel in self._spc_channels}

    @property
    def tdc_channels(self):
        return {channel.name: channel for channel in self._tdc_channels}

    @property
    def idle_state(self):
        """The logical idle value of the FPGA output bus."""
        idle_state = 0
        for channel in self._fpga_channels:
            if channel.idle_state:
                idle_state += 1 << channel.channelID
        return idle_state

    @property
    def polarity_mask(self):
        """Mask which encodes the output polarity."""
        polarity_mask = 0
        for channel in self._fpga_channels:
            if not channel.polarity:
                polarity_mask += 1 << channel.channelID
        return polarity_mask

    def get_tdc_channel_name_by_id(self, id):
        for channel in self._tdc_channels:
            if channel.channelID == id:
                return channel.name

    def verify(self):
        self.control_register.verify()

        for channel in self.channels:
            channel.verify()

        fpga_channel_ids = [channel.channelID for channel in self._fpga_channels]
        if len(fpga_channel_ids) != len(set(fpga_channel_ids)):
            raise FECSException("Output channel IDs must be unique.")
        for channel_id in self.control_register.output_channels:
            if channel_id in fpga_channel_ids:
                raise FECSException("The ControlRegister's output channel %i "
                                    "is also defined as a regular output "
                                    "channel." % channel_id)
        for channel in self._spc_channels:
            if channel.gate in fpga_channel_ids:
                raise FECSException("SPC gate %i is also defined as a regular "
                                    "output channel." % channel.gate)
        for channel_id in self.control_register.output_channels:
            for channel in self._spc_channels:
                if channel_id == channel.gate:
                    raise FECSException("SPC gate %i is also defined as a "
                                        "ControlRegister output."
                                        % channel.gate)

        tdc_channel_ids = [channel.channelID for channel in self._tdc_channels]
        if len(tdc_channel_ids) != len(set(tdc_channel_ids)):
            raise FECSException("Input channel IDs must be unique.")
        for channel_id in self.control_register.input_channels:
            if channel_id in tdc_channel_ids:
                raise FECSException("The ControlRegister's input channel %i "
                                    "is also defined as a regular counter "
                                    "channel." % channel_id)

        spc_channel_ids = [channel.channelID for channel in self._spc_channels]
        if len(spc_channel_ids) != len(set(spc_channel_ids)):
            raise FECSException("Sequence counter channel IDs must be unique.")

        names = [channel.name for channel in self.channels]
        if len(names) != len(set(names)):
            raise FECSException("Channel names must be unique.")
