import xml.etree.ElementTree as ET
from enum import Enum

from .exceptions import *
from ._object import PyFECSObject

class ReferenceType(Enum):
    start = 'start'
    end = 'end'
    jump = 'jump'
    variable = 'variable'


class Reference(PyFECSObject):
    """A reference to a either a :class:`~objects.timePoints.TimePoint`
    or a :class:`~objects.variables.ControlVariable`.

    Allows for :class:`~objects.timePoints.TimePoint`\s which are defined
    relative to other :class:`~objects.timePoints.TimePoint`\s
    :class:`~objects.variables.ControlVariable`\s. By design, for such a
    reference to be resolved by name, the complete
    :class:`~objects.Sequence.Sequence` instance has to have been loaded.

    Therefore, all references are resolved through :meth:`resolve` (invoked by
    :meth:`~objects.Sequence.Sequence.resolve_references`) after
    the sequence is fully defined.

    To prevent recursive relations between
    :class:`~objects.timePoints.TimePoint`\s, which in practice
    are both easily created and even harder to find, a basic recursion
    detection is included in :meth:`get_time`.

    The following objects are available:

    - **start**: The :class:`~objects.timePoints.StartPoint` of a
      :class:`~objects.TimeWindow.TimeWindow`.
    - **end**: The :class:`~objects.timePoints.EndPoint` of a
      :class:`~objects.TimeWindow.TimeWindow`.

      *Example XML configuration:*

      .. code-block:: xml

        <reference type="end">timeWindowName</reference>

    - **jump**: The :class:`~objects.timePoints.JumpPoint` of a
      :class:`~objects.jumps.Jump`.

      *Example XML configuration:*

        .. code-block:: xml

          <reference type="jump">JumpToExampleNow</reference>

    - **variable**: A :class:`~objects.variables.ControlVariable`.

      *Example XML configuration:*

      .. code-block:: xml

        <reference type="variable">variableName</reference>

    """
    XML_tag = 'reference'
    XML_type = 'type'

    def __init__(self):
        super(Reference, self).__init__()
        self.value = ""
        self.type = ""

        # Once the reference is resolved, we store the
        # referenced object here
        self.object = None

        # Initialize recursion detection
        self.recursion = False

    def __eq__(self, other):
        return (self.type == other.type) and (self.value == other.value)

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def toStartPoint(cls, window):
        reference = cls()
        reference.type = ReferenceType.start
        reference.value = window
        return reference

    @classmethod
    def toEndPoint(cls, window):
        reference = cls()
        reference.type = ReferenceType.end
        reference.value = window
        return reference

    @classmethod
    def fromXML(cls, xRoot):
        reference = cls()
        reference.XML = xRoot
        return reference

    def _get_XML(self):
        xRoot = ET.Element(self.XML_tag)
        xRoot.set(self.XML_type, self.type.value)
        xRoot.text = str(self.value)
        return xRoot

    def _set_XML(self, xRoot):
        self.value = str(xRoot.text)

        xTypeString = str(xRoot.get(self.XML_type))
        try:
            self.type = ReferenceType(xTypeString)
        except ValueError:
            raise XMLDefinitionException("Invalid type for Reference: %s"
                                         % xTypeString)

    XML = property(_get_XML, _set_XML)

    def get_time(self, controlValues):
        """
        :param controlValues: Values for all control variables as returned by
                        :meth:`~objects.Sequence.Sequence.get_control_values`.
        :type controlValues: dict
        :return: The time for the given *control_values*.
        :rtype: float
        :raises RecursiveReferenceException: When the time of the reference
                                             depends on itself.
        :raises UnresolvedReferenceException: When the reference has not been
                                              resolved yet.
        :raises InvalidReferenceException: When the value for the specified
                                           variable cannot be determined from
                                           the provided *control_values*.
        :raises InvalidSequenceException: When the *type* of the reference is
                                          invalid.

        """
        if self.object is None:
            raise ReferenceUnresolvedException(
                "Need to resolve references first.",
                object=self)

        if self.recursion:
            # When someone is asking for our time while we are
            # ourselves determining our time, this means that
            # we are asking for our own time to determine
            # our own time, which is an infinite loop.
            raise ReferenceRecursiveException(
                "The start and end of TimeWindow %s "
                "depend on each other in a circular "
                "fashion." % self.object.name,
                object=self)

        self.recursion = True
        try:
            if self.type == ReferenceType.start:
                if self.object.start.detect_recursion():
                    raise ReferenceRecursiveException(
                        "Start of TimeWindow %s depends "
                        "on itself." % self.object.name,
                        object=self)
                time = self.object.start.get_time(controlValues)
            elif self.type == ReferenceType.end:
                if self.object.end.detect_recursion():
                    raise ReferenceRecursiveException(
                        "End of TimeWindow %s depends on itself."
                        % self.object.name, object=self)
                time = self.object.end.get_time(controlValues)
            elif self.type == ReferenceType.jump:
                if self.object.time.detect_recursion():
                    raise ReferenceRecursiveException(
                        "Time of Jump %s depends on itself."
                        % self.object.name, object=self)
                time = self.object.time.get_time(controlValues)
            elif self.type == ReferenceType.variable:
                try:
                    time = controlValues[self.value]
                except KeyError:
                    raise ReferenceInvalidException(
                            "Cannot find value for controlVariable '%s'."
                            % self.value, object=self)
            else:
                raise InvalidSequenceException("Invalid type for Reference.",
                                               object=self)
        except Exception as e:
            raise e
        finally:
            self.recursion = False  # otherwise all future tests fail
        return time

    def resolve(self, sequence):
        """

        :param sequence: The sequence object
        :type sequence: FECSTypes.Sequence.Sequence
        :return: Nothing.
        :raises InvalidReferenceException: The reference cannot be resolved.
        """
        self.logger.debug("Resolving reference %s.", self)
        if self.type == ReferenceType.variable:
            if self.value not in sequence.get_control_variables(all=True):
                raise ReferenceInvalidException(
                    "Could not resolve reference to ControlVariable '%s'."
                    % self.value, object=self)
            self.object = self.value
        elif self.type == ReferenceType.start or self.type == ReferenceType.end:
            try:
                self.object = sequence.time_windows[self.value]
            except KeyError:
                raise ReferenceInvalidException(
                    "Could not resolve reference to TimeWindow '%s'."
                    % self.value, object=self)
        elif self.type == ReferenceType.jump:
            try:
                self.object = sequence.jumps[self.value]
            except KeyError:
                raise ReferenceInvalidException(
                    "Could not resolve reference to Jump '%s'."
                    % self.value, object=self)
        else:
            raise InvalidSequenceException(msg="Invalid type for Reference.",
                                           object=self)

    @property
    def control_variables(self):
        if self.type == ReferenceType.variable:
            return [self.value]
        else:
            if self.object is None:
                return []
            else:
                return self.object.control_variables

    def verify(self):
        """
        :return: Nothing
        :raises UnresolvedReferenceException: The reference has not been
                                              resolved yet.
        :raises InvalidSequenceException: The *type* of the reference is
                                          invalid.
        """
        if self.object is None:
            raise ReferenceUnresolvedException(
                msg="Unresolved reference to '%s'." % self.value,
                object=self)

        if self.type not in ReferenceType:
            raise InvalidSequenceException(
                msg="Invalid type for Reference: %s" % self.type,
                object=self)

    def detect_recursion(self):
        return self.recursion


class OffsetType(Enum):
    absolute = 'absolute'
    variable = 'variable'


class Offset(PyFECSObject):
    """A time offset, used in combination with :class:`Reference` to
    construct :class:`~objects.timePoints.TimePoint`\s whose
    value is defined relative to that of another
    :class:`~objects.timePoints.TimePoint`.

    The following objects are available:

    - **absolute**: A constant value, which can be positive or negative.

      *Example XML configuration:*

      .. code-block:: xml

         <offset type="absolute">-33.0</offset>

    - **variable**: A :class:`~objects.variables.ControlVariable`.

      *Example XML configuration:*

      .. code-block:: xml

        <offset type="variable">variableName</offset>

    """
    XML_tag = 'offset'
    XML_type = 'type'

    def __init__(self):
        super(Offset, self).__init__()
        self.type = ""
        self.value = 0

    @classmethod
    def absolute(cls, value):
        offset = cls()
        offset.type = OffsetType.absolute
        offset.value = value
        return offset

    @classmethod
    def fromXML(cls, xRoot):
        offset = cls()
        offset.XML = xRoot
        return offset

    @property
    def XML(self):
        xRoot = ET.Element(self.XML_tag)
        xRoot.set(self.XML_type, self.type.value)
        xRoot.text = str(self.value)
        return xRoot

    @XML.setter
    def XML(self, xRoot):
        xTypeString = str(xRoot.get(self.XML_type))

        try:
            self.type = OffsetType(xTypeString)
        except ValueError:
            raise XMLDefinitionException("No or invalid type for Offset: %s",
                                         xTypeString)
        if self.type == OffsetType.absolute:
            try:
                self.value = float(str(xRoot.text))
            except ValueError:
                raise XMLDefinitionException("Value of 'absolute' Offset "
                                             "must be float compatible.")
        elif self.type == OffsetType.variable:
            self.value = str(xRoot.text)
        else:
            raise XMLDefinitionException("No or invalid type for Offset.")

    def get_offset(self, control_values):
        """Determine the time offset.

        :param control_values: Values for all control variables as returned by
                        :meth:`~objects.Sequence.Sequence.get_control_values`.
        :type control_values: dict
        :return: The offset's value given the *control_values*.
        :rtype: float
        :raises ControlVariableUnresolvedException: When the reference to the
                                                    ControlVariable cannot be
                                                    resolved.
        :raises InvalidSequenceException: When the *type* is invalid.
        """
        if self.type == OffsetType.absolute:
            return self.value
        elif self.type == OffsetType.variable:
            try:
                return control_values[self.value]
            except KeyError:
                raise ControlVariableUnresolvedException(self.value,
                                                         object=self)
        else:
            raise InvalidSequenceException(msg="Invalid type for Offset.",
                                           object=self)

    def verify(self):
        pass

    @property
    def control_variables(self):
        if self.type == OffsetType.variable:
            return [self.value]
        else:
            return []


class TimePointType(Enum):
    absolute = "absolute"
    relative = "relative"
    variable = "variable"


class TimePoint(PyFECSObject):
    """A single time value in microseconds.

    A *TimePoint* can only be defined as a member of a
    :class:`~objects.TimeWindow.TimeWindow`, which has to contain a single
    :class:`~objects.timePoints.StartPoint` and a single
    :class:`~objects.timePoints.EndPoint`. *TimePoints* can be shared across
    :class:`~objects.TimeWindow.TimeWindow`\s through
    :class:`~objects.timePoints.Reference`\s.

    The verification through :meth:`objects.Sequence.Sequence.verify`
    ensures that all *TimePoints* lie within the
    :class:`~objects.Sequence.Sequence`.

    The following objects are available:

    - **absolute**: A constant time.

      *Example XML configuration*:

      .. code-block:: xml

         <timePoint type="absolute">22.0</timePoint>

    - **variable**: A :class:`~objects.variables.ControlVariable`.

      *Example XML configuration*:

      .. code-block:: xml

         <timePoint type="variable">variableName</timePoint>

    - **relative**: The time of the *TimePoint* is defined relative to a
      different *TimePoint* instance or
      :class:`~objects.variables.ControlVariable`.

      This creates a :class:`Reference` and an :class:`Offset`
      object which are evaluated when :meth:`get_time` is called.

      *Example XML configuration*:

      .. code-block:: xml

        <timePoint type="relative">
           <reference type="start">timeWindowName</reference>
           <offset type="absolute">-10.0</offset>
        </timePoint>
    """
    XML_tag = 'timePoint'
    XML_type = 'type'

    def __init__(self):
        super(TimePoint, self).__init__()

        self._type = TimePointType.absolute
        self.value = 0
        self.offset = None
        self.reference = None

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, value):
        try:
            self._type = TimePointType(value)
        except ValueError:
            raise ValueError("Type has to be a TimePointType.")

    @classmethod
    def absolute(cls, value):
        timePoint = cls()
        timePoint.type = TimePointType.absolute
        timePoint.value = value
        return timePoint

    @classmethod
    def relative(cls, reference, offset):
        timePoint = cls()
        timePoint.type = TimePointType.relative
        timePoint.reference = reference
        timePoint.offset = offset
        return timePoint

    @classmethod
    def fromXML(cls, xRoot):
        timePoint = cls()
        timePoint.XML = xRoot
        return timePoint

    @property
    def XML(self):
        xRoot = ET.Element(self.XML_tag)
        xRoot.set(self.XML_type, self.type.value)
        if self.type == TimePointType.relative:
            xRoot.append(self.reference.XML)
            xRoot.append(self.offset.XML)
        else:
            xRoot.text = str(self.value)
        return xRoot

    @XML.setter
    def XML(self, xRoot):
        try:
            xTypeString = str(xRoot.get(self.XML_type))
        except ValueError:
            raise XMLDefinitionException("Type for TimePoint must be "
                                         "compatible to str.")
        try:
            self.type = TimePointType(xTypeString)
        except ValueError:
            raise XMLDefinitionException("Invalid type for TimePoint: %s"
                                         % xTypeString)

        if self.type == TimePointType.absolute:
            try:
                self.value = float(str(xRoot.text))
            except ValueError:
                raise XMLDefinitionException("Value for 'absolute' TimePoint "
                                             "needs to be compatible to float.")
        elif self.type == TimePointType.relative:
            xReference = xRoot.find(Reference.XML_tag)
            if xReference is not None:
                self.reference = Reference.fromXML(xReference)
            else:
                raise XMLDefinitionException("Definition of a 'relative' "
                                             "TimePoint must contain a "
                                             "reference to another TimePoint "
                                             "or ControlVariable.")
            xOffset = xRoot.find(Offset.XML_tag)
            if xOffset is not None:
                self.offset = Offset.fromXML(xOffset)
            else:
                raise XMLDefinitionException(
                    "Definition of a 'relative' TimePoint "
                    "must contain an offset.")
        elif self.type == TimePointType.variable:
            self.value = str(xRoot.text)
        else:
            raise XMLDefinitionException("Bad TimePoint type: %s" % self.type)

    def get_time(self, control_values):
        """
        :param control_values: Values for all control variables as returned by
                        :meth:`~objects.Sequence.Sequence.get_control_values`.
        :type control_values: dict
        :return: The time given the *control_values*.
        :rtype: float
        :raise ControlVariableUnresolvedException: When the reference to the
                                                   ControlVariable cannot be
                                                   resolved.
        :raise InvalidSequenceException: When the *type* is invalid.
        """

        if self.type == TimePointType.absolute:
            return self.value
        elif self.type == TimePointType.relative:
            offset = self.offset.get_offset(control_values)
            return self.reference.get_time(control_values) + offset
        elif self.type == TimePointType.variable:
            try:
                return control_values[self.value]
            except KeyError:
                raise ControlVariableUnresolvedException(name=self.value,
                                                         object=self)
        else:
            raise InvalidSequenceException(msg="Invalid type for TimePoint.",
                                           object=self)

    @property
    def control_variables(self):
        if self.type == TimePointType.variable:
            return [self.value]
        elif self.type == TimePointType.relative:
            return (self.offset.control_variables
                    + self.reference.control_variables)
        else:
            return []

    def verify(self, control_values, length):
        """

        :param control_values: Values for all control variables as returned by
                        :meth:`~objects.Sequence.Sequence.get_control_values`.
        :param length:
        :type control_values: dict
        :type length: float
        :return: Nothing
        :raise InvalidSequenceException: When the time is outside of the
                                         sequence or the *type* is invalid.
        """
        if self.type not in TimePointType:
            raise InvalidSequenceException(msg="Type is invalid.",
                                           object=self)
        if self.type == TimePointType.relative:
            self.reference.verify()
            self.offset.verify()
        time = self.get_time(control_values)
        if time < 0 or time > length:
            raise InvalidSequenceException(
                msg="Time %0.2f is outside of sequence." % time,
                object=self)

    def resolve(self, sequence):
        """When *type* is *relative*, resolve the
         :class:`~objects.timePoints.Reference` if necessary.

        :return: Nothing.
        """
        if self.type == TimePointType.relative:
            self.reference.resolve(sequence)

    def detect_recursion(self):
        """When *type* is *relative*, check for recursion.

        See :meth:`objects.timePoints.Reference.get_time` for details.

        :return: Nothing.
        """
        if self.type == TimePointType.relative:
            return self.reference.detect_recursion()
        else:
            return False


class StartPoint(TimePoint):
    """The start time of a :class:`~objects.TimeWindow.TimeWindow`.

    See documentation for :class:`~objects.timePoints.TimePoint`."""
    XML_tag = 'start'
    XML_tag_legacy = 'tStart'

    def __init__(self):
        super(self.__class__, self).__init__()


class EndPoint(TimePoint):
    """The end time of a :class:`~objects.TimeWindow.TimeWindow`.

    See documentation for :class:`~objects.timePoints.TimePoint`."""
    XML_tag = "end"
    XML_tag_legacy = 'tEnd'

    def __init__(self):
        super(self.__class__, self).__init__()


class JumpPoint(TimePoint):
    """The timestamp of a :class:`~objects.jumps.Jump`.

    See documentation for :class:`~objects.timePoints.TimePoint`."""
    XML_tag = "time"

    def __init__(self):
        super(self.__class__, self).__init__()
