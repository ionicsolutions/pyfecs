"""

.. warning:: While *PyFECS* ensures that a :class:`~FECSTypes.Sequence.Sequence`
   is finite in the sense that it *can* reach its end, it is easy to construct
   a sequence which through :class:`Jump`\s is infinite because in practice the
   :class:`Condition`\s required to reach the end are never fulfilled.
"""
import logging
import xml.etree.ElementTree as ET
from enum import Enum
from collections import OrderedDict, Counter

from .timePoints import Reference, JumpPoint, ReferenceType
from .exceptions import *
from ._object import PyFECSObject

class Destination(Reference):
    """The target of a :class:`~objects.jumps.Jump`.

    Given as a :class:`~objects.timePoints.Reference` to a
    :class:`~objects.timePoints.TimePoint`.

    See documentation for :class:`objects.timePoints.Reference`.
    """

    XML_tag = "destination"

    def __init__(self):
        super(Destination, self).__init__()

    def verify(self):
        super(Destination, self).verify()

        if self.type == ReferenceType.jump:
            if isinstance(self.object, ConditionalJump):
                raise InvalidSequenceException("The Destination of any Jump "
                                               "cannot be a ConditionalJump. "
                                               "Jump to the start of the "
                                               "TimeWindow linked to the "
                                               "ConditionalJump instead.",
                                               object=self)


class ReferenceLike(PyFECSObject):
    XML_tag = "pseudo_reference"

    def __init__(self):
        super(ReferenceLike, self).__init__()

        self.type = self.XML_tag
        self.object = self

    @classmethod
    def fromXML(cls, xRoot):
        reference = cls()
        reference.XML = xRoot
        return reference

    @property
    def XML(self):
        xRoot = ET.Element(self.XML_tag)
        return xRoot

    @XML.setter
    def XML(self, xRoot):
        self.type = self.XML_tag

    def resolve(self, sequence):
        pass


class Terminator(ReferenceLike):
    XML_tag = "terminate"

    def __init__(self):
        super(Terminator, self).__init__()
        self.name = "_Terminator"


class Pass(ReferenceLike):
    XML_tag = "pass"

    def __init__(self):
        super(Pass, self).__init__()


class ConditionType(Enum):
    value = "value"
    threshold = "threshold"
    range = "range"
    else_ = "else"


class Condition(PyFECSObject):
    """The condition under which to perform a :class:`~objects.jumps.Jump`.

    When the Condition is met and a
    :class:`~objects.jumps.Destination` is given, jump to this destination.
    If no destination is specified, continue with the sequence.

    The following objects are available:

    - **value**: A specific number of counts

      *Example XML configuration:*

      .. code-block:: xml

         <condition type="value">
            <value>1</value>
            <destination type="start">Cooling</destination>
         </condition>

    - **range**: A count range where *from* is the lowest count value for which
      the Condition evaluates to *True* and *to* is the lowest value greater
      than *from* for which the Condition evaluates to *False*.

      *Example XML configuration:*

      .. code-block:: xml

         <condition type="range">
            <from>10</from>
            <to>18000</to>
            <destination type="end">Repumper</destination>
         </condition>

    - **threshold**: The Condition evaluates to *True* when the threshold is
      reached or exceeded.

      *Example XML configuration:*

      .. code-block:: xml

         <condition type="threshold">
            <threshold>5000</threshold>
            <destination type="jump">A Second Criterion</destination>
         </condition>


    """

    XML_tag = "condition"
    XML_type = "type"

    XML_value = "value"
    XML_threshold = "threshold"
    XML_from = "from"
    XML_to = "to"

    def __init__(self):
        super(Condition, self).__init__()

        self.type = ConditionType.else_

        self._value = 0
        self._threshold = 0
        self._range = (0, 0)

        self.destination = None

    @classmethod
    def fromXML(cls, xRoot):
        condition = cls()
        condition.XML = xRoot
        return condition

    @property
    def XML(self):
        xRoot = ET.Element(self.XML_tag)

        xRoot.set(self.XML_type, self.type.value)

        if self.type == ConditionType.value:
            xValue = ET.SubElement(xRoot, self.XML_value)
            xValue.text = str(self._value)
        elif self.type == ConditionType.threshold:
            xThreshold = ET.SubElement(xRoot, self.XML_threshold)
            xThreshold.text = str(self._threshold)
        elif self.type == ConditionType.range:
            xFrom = ET.SubElement(xRoot, self.XML_from)
            xFrom.text = str(self._range[0])
            xTo = ET.SubElement(xRoot, self.XML_to)
            xTo.text = str(self._range[1])
        elif self.type == ConditionType.else_:
            pass
        else:
            raise InvalidSequenceException("No or invalid type for Condition.",
                                           object=self)

        xRoot.append(self.destination.XML)

        return xRoot

    @XML.setter
    def XML(self, xRoot):
        xTypeString = str(xRoot.get(self.XML_type))

        try:
            self.type = ConditionType(xTypeString)
        except ValueError:
            raise XMLDefinitionException("No or invalid type for Condition: %s"
                                         % xTypeString)

        if self.type == ConditionType.value:
            xValue = xRoot.find(self.XML_value)
            if xValue is not None:
                self._value = int(xValue.text)
        elif self.type == ConditionType.threshold:
            xThreshold = xRoot.find(self.XML_threshold)
            if xThreshold is not None:
                self._threshold = int(xThreshold.text)
        elif self.type == ConditionType.range:
            xFrom = xRoot.find(self.XML_from)
            xTo = xRoot.find(self.XML_to)
            if xFrom is not None and xTo is not None:
                self._range = (int(xFrom.text), int(xTo.text))
        elif self.type == ConditionType.else_:
            pass
        else:
            raise XMLDefinitionException("No or invalid type for Condition.")

        xDestination = xRoot.find(Destination.XML_tag)
        xTerminator = xRoot.find(Terminator.XML_tag)
        xPass = xRoot.find(Pass.XML_tag)
        if xDestination is not None:
            self.destination = Destination.fromXML(xDestination)
        elif xTerminator is not None:
            self.destination = Terminator.fromXML(xTerminator)
        elif xPass is not None:
            self.destination = Pass.fromXML(xPass)
        else:
            self.destination = Pass()

    def resolve_references(self, sequence):
        self.destination.resolve(sequence)

    @property
    def range(self):
        """Return the count range for which the Condition is *True*.

        Given as [lower,upper), i.e. the lower value is the smallest value for
        which the Condition is *True*, and the upper value is the lowest value
        (greater than the lower value) for which the Condition is *False*.
        """
        if self.type == ConditionType.value:
            return self._value, self._value + 1
        elif self.type == ConditionType.threshold:
            return self._threshold, 2 ** 16
        elif self.type == ConditionType.range:
            return self._range[0], self._range[1]
        elif self.type == ConditionType.else_:
            return 0, 2**16
        else:
            raise InvalidSequenceException("No or invalid type for Condition.",
                                           object=self)

    def verify(self):
        if self.type == ConditionType.range:
            if self._range[1] < self._range[0]:
                raise InvalidSequenceException("Upper bound of range has to be "
                                               "strictly larger than lower "
                                               "bound.", object=self)


class Jump(PyFECSObject):
    """

    Bare Jumps cannot be declared in the XML and should not be added to the
    Sequence. Instead, the subclasses :class:`ConditionalJump`,
    :class:`GoTo`, and :class:`End` should be used.

    .. note:: As the evaluation of a Condition takes at least one IPU step,
       Jumps with many Conditions can require a considerable amount of time
       to evaluate. It is guaranteed by the compiler that the actual jump
       happens at the specified time *at the latest*, but the jump might in
       fact happen several IPU steps earlier.

    A warning will be given when no *else* Condition is declared
    and the Jump defaults to a passing *else* Condition.

    .. note:: A Jump without any conditions (or just a passing *else*)
              always passes and will not appear in the compiled sequence.

    """

    XML_tag = 'jump'
    XML_name = 'name'

    def __init__(self):
        super(Jump, self).__init__()

        self.name = ""
        self.time = JumpPoint()
        self.conditions = []

    @classmethod
    def fromXML(cls, xRoot):
        jump = cls()
        jump.XML = xRoot
        return jump

    def _get_XML(self):
        xRoot = ET.Element(self.XML_tag)

        xName = ET.SubElement(xRoot, self.XML_name)
        xName.text = self.name

        xRoot.append(self.time.XML)
        return xRoot

    def _set_XML(self, xmlConfiguration):
        xRoot = xmlConfiguration

        xName = xRoot.find(self.XML_name)
        if xName is not None:
            self.name = xName.text
        else:
            raise XMLDefinitionException("Jump without name.")

        xTime = xRoot.find(JumpPoint.XML_tag)
        if xTime is not None:
            self.time = JumpPoint.fromXML(xTime)
        else:
            raise XMLDefinitionException("Jump without time.")

    XML = property(_get_XML, _set_XML)

    @property
    def threshold_conditions(self):
        """Convert all conditions into threshold conditions.

        The IPU can only perform a conditional threshold jump, i.e. the
        *JUMP* instruction jumps to a different point in the sequence when
        the counter value is above a certain threshold and continues otherwise.

        This method converts all conditions into threshold conditions which can
        then be converted into a sequence of *JUMP*\s by the compiler.

        .. note:: The compiler checks whether the value of the count window is
           relevant to determine the destination of the JUMP. If the JUMP only
           has one destination, the IPU will not retrieve and check the value,
           and the JUMP won't be added at all if it is always passing.
        """
        defined_ranges = {}
        else_ = None
        self._enforce_else()
        for condition in self.conditions:
            if condition.type == ConditionType.else_:
                else_ = condition
            else:
                defined_ranges[condition.range] = condition
        if else_ is None:
            raise FECSException("'else' Condition not found, even though it "
                                "should be added automatically when missing.")
        ordered_ranges = sorted(defined_ranges.keys(), reverse=True)
        current_threshold = 2**16
        threshold_conditions = OrderedDict()
        for lower, upper in ordered_ranges:
            if upper < current_threshold:
                threshold_conditions[upper] = else_
                threshold_conditions[lower] = defined_ranges[(lower, upper)]
                current_threshold = lower
            elif upper == current_threshold:
                threshold_conditions[lower] = defined_ranges[(lower, upper)]
                current_threshold = lower
            else:
                raise InvalidSequenceException("Overlap in count ranges for "
                                               "Conditions.", object=self)
        if current_threshold > 0:
            threshold_conditions[0] = else_

        return threshold_conditions

    @property
    def compressed_conditions(self):
        compressed_conditions = {}
        threshold_conditions = self.threshold_conditions
        current_threshold = 0
        for threshold, condition in threshold_conditions.iteritems():
            currentDestination = threshold_conditions[current_threshold].destination
            if condition.destination == currentDestination:
                pass
            else:
                compressed_conditions[current_threshold] = currentDestination
                current_threshold = threshold
        else:
            if current_threshold not in compressed_conditions:
                compressed_conditions[current_threshold] = condition.destination
        return compressed_conditions

    def resolve_references(self, sequence):
        self.time.resolve(sequence)
        self._enforce_else()
        for condition in self.conditions:
            condition.resolve_references(sequence)

    def get_time(self, control_values):
        return self.time.get_time(control_values)

    def get_destinations(self, control_values, passing):
        self._enforce_else()
        destinations = []
        for condition in self.conditions:
            if isinstance(condition.destination, Destination):
                destinations.append(
                    condition.destination.get_time(control_values))
            elif isinstance(condition.destination, Terminator):
                pass
            elif isinstance(condition.destination, Pass):
                if passing:
                    destinations.append(self.time.get_time(control_values))
            else:
                raise FECSException("Invalid type for destination.")
        return destinations

    def _enforce_else(self):
        condition_types = [condition.type for condition in self.conditions]
        if ConditionType.else_ not in condition_types:
            self.logger.warning("No defined 'else' condition for Jump %s: %s. "
                                "Default to empty (passing) condition.",
                                self.name, condition_types)
            passing_condition = Condition()
            passing_condition.destination = Pass()
            self.conditions.append(passing_condition)

    def verify(self, control_values):
        self._enforce_else()

        if [c.type for c in self.conditions].count(ConditionType.else_) > 1:
            raise InvalidSequenceException("Multiple 'else' conditions.",
                                           object=self)
        # check for overlap in count ranges
        threshold_conditions = self.threshold_conditions


class ConditionalJump(Jump):
    """A ConditionalJump necessarily includes the reference to a window, which
    has to belong to the same controlChannel.

    .. note:: Should the end of the *window* coincide with the JumpPoint,
              it will be truncated to end prior to the first JUMP instruction
              of the ConditionalJump during compilation. See documentation for
              :class:`Jump` for more information on this.

    A ConditionalJump can contain an arbitrary amount of Conditions, but only
    one condition may evaluate to *True* for any given number of counts.

    An *else* Condition is optional, but the user is encouraged to explicitly
    declare it.

    .. note:: When the destination is the next time step, i.e.
       the Jump is effectively passing, the compiler will give a warning and
       no JUMP will be added to the compiled sequence. (It is however not
       allowed to define a ConditionalJump without any Destinations.)

    *Example XML configuration:*

    .. code-block:: xml

       <jump>
       <name>Bell State</name>
       <window>Check State</window>
       <condition type="value">
          ...
       </condition>
       <condition type="range">
         ...
       </condition>
       ...
       <condition type="else" />
       </jump>
    """

    XML_tag = 'jump'
    XML_window = 'window'

    def __init__(self):
        super(ConditionalJump, self).__init__()
        self.window = ""

    def _get_XML(self):
        xRoot = super(ConditionalJump, self)._get_XML()

        xWindow = ET.SubElement(xRoot, self.XML_window)
        xWindow.text = self.window

        for condition in self.conditions:
            xRoot.append(condition.XML)

        return xRoot

    def _set_XML(self, xRoot):
        super(ConditionalJump, self)._set_XML(xRoot)

        xWindow = xRoot.find(self.XML_window)
        if xWindow is not None:
            self.window = xWindow.text
        else:
            raise XMLDefinitionException("ConditionalJump '%s' without "
                                         "TimeWindow." % self.name)

        xConditions = xRoot.findall(Condition.XML_tag)
        for xCondition in xConditions:
            self.conditions.append(Condition.fromXML(xCondition))

    XML = property(_get_XML, _set_XML)

    def verify(self, control_values):
        super(ConditionalJump, self).verify(control_values)

        typeCount = Counter([c.type for c in self.conditions])

        if typeCount[ConditionType.value] + \
                typeCount[ConditionType.range] + \
                typeCount[ConditionType.threshold] == 0:
            self.logger.warning("ConditionalJump '%s' does not use its "
                                "TimeWindow '%s'. Consider switching to "
                                "GoTo instead." % (self.name, self.window))

        # Check that the Jump is in fact conditional. This ensures that there
        # are at least some variants for which the jump actually does something.
        destinationClasses = [c.destination.__class__ for c in self.conditions]
        destinationClassCount = Counter(destinationClasses)
        if destinationClassCount[Destination] == 0:
            if destinationClassCount[type(None)] == 0:
                if destinationClassCount[Terminator] == 0:
                    raise FECSException("Invalid object registered as "
                                        "destination for ConditionalJump "
                                        "'%s'." % self.name)
                else:
                    raise InvalidSequenceException("Always terminates the "
                                                   "sequence.", object=self)
            else:
                if destinationClassCount[Terminator] == 0:
                    raise InvalidSequenceException("Always passes.",
                                                   object=self)
                else:
                    raise FECSException("Invalid object registered as "
                                        "destination for ConditionalJump "
                                        "'%s'." % self.name)


class GoTo(Jump):
    """Go to a different point in the sequence.

    *Example XML configuration:*

    .. code-block:: xml

       <goto>
          <name>Skip to Readout</name>
          <time type="absolute">510.3</time>
          <destination type="start">Readout</destination>
       </goto>

    GoTo is implemented as a :class:`Jump` which always jumps, i.e. the
    corresponding configuration of a Jump is

    .. code-block:: xml

      <jump>
         <name>Skip to Readout</name>
         <window>NeverEvaluatedAnyway</window>
         <time type="absolute">510.3</time>
         <condition type="else">
            <destination type="start">Readout</destination>
         </condition>
      </jump>

    .. note:: When the destination is the next timestep after the GoTo, i.e.
       the Jump is passing, the compiler will give a warning and no JUMP will
       be added to the compiled sequence. Since this might happen for some
       sequence variants but not others, passing GoTos are allowed in PyFECS.
       (It is however not allowed to define a GoTo without a *destination*.)
    """

    XML_tag = 'goto'

    def __init__(self):
        super(GoTo, self).__init__()

        if self.conditions:
            self.logger.warning("Found conditions in GoTo. "
                                "These are without effect.")

        gotoCondition = Condition()
        gotoCondition.type = ConditionType.else_
        self.conditions = [gotoCondition]

    def _get_XML(self):
        xRoot = super(GoTo, self)._get_XML()
        xRoot.append(self.conditions[0].destination.XML)
        return xRoot

    def _set_XML(self, xRoot):
        super(GoTo, self)._set_XML(xRoot)
        xDestination = xRoot.find(Destination.XML_tag)
        if xDestination is not None:
            self.conditions[0].destination = Destination.fromXML(xDestination)

    XML = property(_get_XML, _set_XML)

    def verify(self, control_values):
        super(GoTo, self).verify(control_values)

        if len(self.conditions) > 1:
            raise InvalidSequenceException("Multiple Conditions in GoTo.",
                                           object=self)

        if self.conditions[0].type != ConditionType.else_:
            raise InvalidSequenceException("Condition of type other than "
                                           "'else' in GoTo.", object=self)

        if self.conditions[0].destination == None:
            raise InvalidSequenceException("No Destination in GoTo.",
                                           object=self)

        if isinstance(self.conditions[0].destination, Terminator):
            raise InvalidSequenceException("Destination of a GoTo cannot be "
                                           "a Terminator. Use End instead.",
                                           object=self)


class End(Jump):
    """Exit the sequence.

    *Example XML configuration:*

    .. code-block:: xml

       <end>
          <name>End after Readout</name>
          <time type="absolute">510.3</time>
       </end>

    End is implemented as a :class:`Jump` which always terminates, i.e. the
    corresponding configuration of a Jump is

    .. code-block:: xml

      <jump>
         <name>End after Readout</name>
         <window>NeverEvaluatedAnyway</window>
         <time type="absolute">510.3</time>
         <condition type="else">
            <terminate />
         </condition>
      </jump>

    .. note:: An End at the end of the sequence has no effect and will be
       ignored by the compiler. A warning will be given.

    .. note:: Parts of the sequence which lie behind an End and can never
       be reached through Jumps are ignored by the compiler. A warning will
       be given and the compiled sequence will be shortened.
    """

    XML_tag = 'end'

    def __init__(self):
        super(End, self).__init__()

        endingCondition = Condition()
        endingCondition.type = ConditionType.else_
        endingCondition.destination = Terminator()

        self.conditions = [endingCondition]

    def verify(self, control_values):
        super(End, self).verify(control_values)

        if len(self.conditions) > 1:
            raise InvalidSequenceException("Multiple Conditions in End.",
                                           object=self)

        if self.conditions[0].type != ConditionType.else_:
            raise InvalidSequenceException("Condition of type other than "
                                           "'else' in End.", object=self)

        if not isinstance(self.conditions[0].destination, Terminator):
            raise InvalidSequenceException("Non-terminating End.",
                                           object=self)















