import logging
import xml.etree.ElementTree as ET

from ._object import PyFECSObject
from .exceptions import *
from .names import getName
from .timePoints import StartPoint, EndPoint, Reference, Offset


class TimeWindow(PyFECSObject):
    """A time-period during which a sequence channel is activated.

    A TimeWindow has to contain exactly one
    :class:`~objects.timePoints.StartPoint` and exactly one
    :class:`~objects.timePoints.EndPoint`.

    *Example XML configuration:*

    .. code-block:: xml

       <window>
          <name>example window</name>
          <start type="absolute">4.0</start>
          <end type="absolute">10.4</end>
       </window>

    """
    XML_tag = 'window'
    XML_name = 'name'
    XML_length = 'length'

    def __init__(self):
        super(TimeWindow, self).__init__()

        self.name = ""
        self.start = None
        self.end = None

    @classmethod
    def fromXML(cls, xRoot):
        timeWindow = cls()
        timeWindow.XML = xRoot
        return timeWindow

    @classmethod
    def absolute(cls, name, start=None, end=None, length=None):
        timeWindow = cls()
        timeWindow.name = name
        if [start, end, length].count(None) > 1:
            raise ValueError("Either start/end, start/length, or end/length "
                             "need to be given.")
        if length is None:
            timeWindow.start = StartPoint.absolute(start)
            timeWindow.end = EndPoint.absolute(end)
        else:
            if start is not None and end is None:
                timeWindow.start = StartPoint.absolute(start)
                reference = Reference.toStartPoint(name)
                offset = Offset.absolute(length)
                timeWindow.end = EndPoint.relative(reference, offset)
            elif start is None and end is not None:
                timeWindow.end = EndPoint.absolute(end)
                reference = Reference.toEndPoint(name)
                offset = Offset.absolute(-length)
                timeWindow.start = StartPoint.relative(reference, offset)
        return timeWindow

    @property
    def XML(self):
        xRoot = ET.Element(self.XML_tag)
        xName = ET.SubElement(xRoot, self.XML_name)
        xName.text = self.name
        if self.start is not None:
            xRoot.append(self.start.XML)
        if self.end is not None:
            xRoot.append(self.end.XML)
        return xRoot

    @XML.setter
    def XML(self, xRoot):
        xName = xRoot.find(self.XML_name)
        if xName is not None:
            self.name = xName.text
        else:
            self.name = getName()
            self.logger.warning("Unnamed time window. Assigning a placeholder "
                                "to prevent issues later on: '%s'.", self.name)

        xStart = xRoot.find(StartPoint.XML_tag)
        if xStart is None:
            xStart = xRoot.find(StartPoint.XML_tag_legacy)
        if xStart is not None:
            self.start = StartPoint.fromXML(xStart)

        xEnd = xRoot.find(EndPoint.XML_tag)
        if xEnd is None:
            xEnd = xRoot.find(EndPoint.XML_tag_legacy)
        if xEnd is not None:
            self.end = EndPoint.fromXML(xEnd)

        xLength = xRoot.find(self.XML_length)
        if xLength is not None:
            length = float(xLength.text)
            if xStart is not None and xEnd is None:
                reference = Reference.toStartPoint(self.name)
                offset = Offset.absolute(length)
                self.end = EndPoint.relative(reference, offset)
            elif xStart is None and xEnd is not None:
                reference = Reference.toEndPoint(self.name)
                offset = Offset.absolute(-length)
                self.start = StartPoint.relative(reference, offset)
            elif xStart is None and xEnd is None:
                raise XMLDefinitionException(
                    "Length defined for TimeWindow %s, but no StartPoint "
                    "or EndPoint is given." % self.name)
            else:
                self.logger.warning("Length for TimeWindow %s given in XML, "
                                    "but both TimePoints are defined as well. "
                                    "Ignoring length.", self.name)
        else:
            if xStart is None:
                raise XMLDefinitionException(
                    "Definition for TimeWindow %s "
                    "contains no StartPoint." % self.name)
            if xEnd is None:
                raise XMLDefinitionException(
                    "Definition for TimeWindow %s contains "
                    "no EndPoint." % self.name)

    @property
    def control_variables(self):
        return self.start.control_variables + self.end.control_variables

    def get_times(self, control_values):
        """Determine the start and end time."""
        return (self.start.get_time(control_values),
                self.end.get_time(control_values))

    def verify(self, control_values, length):
        if not self.name:
            raise InvalidSequenceException(msg="No name.",
                                           object=self)
        if self.start is None:
            raise InvalidSequenceException(msg="No starting TimePoint",
                                           object=self)
        if self.end is None:
            raise InvalidSequenceException(msg="No ending TimePoint.",
                                           object=self)
        self.start.verify(control_values, length)
        self.end.verify(control_values, length)
        if (self.start.get_time(control_values)
                > self.end.get_time(control_values)):
            raise InvalidSequenceException(msg="Negative length.",
                                           object=self)

    def resolve_references(self, sequence):
        self.start.resolve(sequence)
        self.end.resolve(sequence)
