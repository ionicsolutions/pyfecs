"""Through the use of variables, *PyFECS* sequence can be made dynamic to
perform more sophisticated measurements.

Currently, *PyFECS* implements only a single type of variable: A
:class:`ControlVariable` can take on a different value per variant of the
sequence, which can depend on both the index of the variant and the total
number of variants in the measurement. Its value is determined during
compilation of the sequence and stays constants across all shots taken.

In the future, a second type of variable could be implemented: A
:class:`SequenceVariable` can take on a different value per shot, e.g. the
output of an :class:`~FECSTypes.channels.SPCChannel`.
"""
import logging
import xml.etree.ElementTree as ET

import numpy as np
from enum import Enum

from ._object import PyFECSObject
from .exceptions import *


class ControlVariableType(Enum):
    constant = 'constant'
    linear = 'linear'
    expression = 'expression'


class ControlVariable(PyFECSObject):
    """A control variable can take on a different value for each variant.

    It can be shared by several :class:`~objects.timePoints.TimePoint`\s,
    allowing for complex sequences.

    .. note:: The value of a *ControlVariable* is not restricted to lie
              within a sequence, as the value of a
              :class:`~objects.timePoints.TimePoint` can be determined
              from a variable through an :class:`~objects.timePoints.Offset`.

              Through :meth:`objects.Sequence.Sequence.verify` it is ensured
              that all :class:`~objects.timePoints.TimePoint`\s lie within the
              sequence length and that all
              :class:`~objects.TimeWindow.TimeWindow`\s have a positive length
              prior to compilation.

    The following objects are available:

    - **constant**: a constant *value*

      *Example XML configuration:*

      .. code-block:: xml

         <controlVariable type="constant">
             <name>example variable</name>
             <value>130.0</value>
         </controlVariable>

    - **linear**: creates linearly spaced steps given by the *start* and *stop*
      tags

      *Example XML configuration:*

      .. code-block:: xml

         <controlVariable type="linear">
             <name>example variable</name>
             <start>0.0</start>
             <stop>100.0</stop>
         </controlVariable>
    - **expression**: a function of a single variable *x* as Python syntax,
      supports :mod:`numpy` methods. If *x* is used, the
      range of *x* has to be specified with *from* and *to* tags.

      *Example XML configuration:*

      .. code-block:: xml

         <controlVariable type="expression">
             <name>example variable</name>
             <expression>5*np.sin(x)</expression>
             <from>0</from>
             <to>6.5</to>
         </controlVariable>
    """
    XML_tag = 'controlVariable'
    XML_type = 'type'
    XML_name = 'name'

    XML_const_value = 'value'

    XML_lin_min = 'min'
    XML_lin_max = 'max'

    XML_lin_start = 'start'
    XML_lin_stop = 'stop'

    XML_exp_expression = 'expression'
    XML_exp_from = 'from'
    XML_exp_to = 'to'

    def __init__(self):
        super(ControlVariable, self).__init__()

        self.name = ""
        self.type = None

        self.const_value = None
        self.lin_start = None
        self.lin_stop = None
        self.exp_from = None
        self.exp_to = None
        self.exp_str = ""

    @classmethod
    def fromXML(cls, xRoot):
        controlVariable = cls()
        controlVariable.XML = xRoot
        return controlVariable

    @property
    def XML(self):
        xRoot = ET.Element(self.XML_tag)

        xName = ET.SubElement(xRoot, self.XML_name)
        xName.text = self.name

        xRoot.set(self.XML_type, self.type.value)
        if self.type is ControlVariableType.constant:
            xValue = ET.SubElement(xRoot, self.XML_const_value)
            xValue.text = str(self.const_value)
        elif self.type is ControlVariableType.linear:
            xStart = ET.SubElement(xRoot, self.XML_lin_start)
            xStart.text = str(self.lin_start)
            xStop = ET.SubElement(xRoot, self.XML_lin_stop)
            xStop.text = str(self.lin_stop)
        elif self.type is ControlVariableType.expression:
            xExpression = ET.SubElement(xRoot, self.XML_exp_expression)
            xExpression.text = str(self.exp_str)
            xFrom = ET.SubElement(xRoot, self.XML_exp_from)
            xFrom.text = str(self.exp_from)
            xTo = ET.SubElement(xRoot, self.XML_exp_to)
            xTo.text = str(self.exp_to)
        return xRoot

    @XML.setter
    def XML(self, xRoot):
        xName = xRoot.find(self.XML_name)
        if xName is not None:
            try:
                self.name = str(xName.text)
            except ValueError:
                raise XMLDefinitionException("Name for ControlVariable has "
                                             "to be compatible to str.")
        else:
            raise XMLDefinitionException("Missing name for ControlVariable.")

        xType = xRoot.get(self.XML_type)
        if xType is not None:
            try:
                self.type = ControlVariableType(str(xType))
            except ValueError:
                raise XMLDefinitionException(
                    "Type for ControlVariable '%s' is not compatible to str."
                    % self.name)
        else:
            # legacy fallback
            xType = xRoot.find(self.XML_type)
            if xType is not None:
                self.logger.warning("Outdated type definition for variable '%s'.",
                                    self.name)
                try:
                    self.type = ControlVariableType(str(xType))
                except ValueError:
                    self.type = ControlVariableType("linear")
            else:
                raise XMLDefinitionException(
                    "Missing type for ControlVariable '%s'."
                    % self.name)

        if self.type == ControlVariableType.constant:
            xValue = xRoot.find(self.XML_const_value)
            self.const_value = float(xValue.text)
        elif self.type == ControlVariableType.linear:
            # the use of min and max is deprecated
            xStart = xRoot.find(self.XML_lin_start)
            if xStart is None:
                xMin = xRoot.find(self.XML_lin_min)
                self.lin_start = float(xMin.text)
            else:
                self.lin_start = float(xStart.text)
            xStop = xRoot.find(self.XML_lin_stop)
            if xStop is None:
                xMax = xRoot.find(self.XML_lin_max)
                self.lin_stop = float(xMax.text)
            else:
                self.lin_stop = float(xStop.text)
        elif self.type == ControlVariableType.expression:
            xExpression = xRoot.find(self.XML_exp_expression)
            self.exp_str = str(xExpression.text)
            xFrom = xRoot.find(self.XML_exp_from)
            if xFrom is not None:
                self.exp_from = float(xFrom.text)
            else:
                self.exp_from = None
            xTo = xRoot.find(self.XML_exp_to)
            if xTo is not None:
                self.exp_to = float(xTo.text)
            else:
                self.exp_to = None

    def getValue(self, variant, numberOfVariants):
        """Return the value of the ControlVariable for the given variant.

        :param variant:
        :param numberOfVariants:
        :type variant: int
        :type numberOfVariants: int
        :return: Value of the ControlVariable
        :rtype: float

        .. note:: The idea of evaluating ControlVariables this way stems from
                  Tim Ballance who also used this approach in the original
                  Matlab version and started to port it to Python as well. In
                  principle, this is computationally expensive as this method
                  needs to be called for each new variant and evaluate all
                  values each time, instead of preparing a list beforehand.

                  However, it is much easier this way and greatly helps to
                  ensure sequence validity for each variant.
        """
        if self.type == ControlVariableType.constant:
            value = self.const_value
        elif self.type == ControlVariableType.linear:
            value = np.linspace(self.lin_start, self.lin_stop,
                                num=numberOfVariants)[variant]
        elif self.type == ControlVariableType.expression:
            if (self.exp_from is not None) and (self.exp_to is not None):
                x = np.linspace(self.exp_from, self.exp_to,
                                num=numberOfVariants)[variant]
            try:
                value = eval(self.exp_str)
            except Exception as e:
                raise ControlVariableInvalidException(
                    msg="Invalid expression string: %s" % e,
                    object=self)
        else:
            raise ControlVariableUndefinedException(name=self.name,
                                                    object=self)
        return value

    def verify(self):
        """

        :return: Nothing.
        :raises ControlVariableInvalidException: When the definition is invalid.
        """
        if not self.name:
            raise ControlVariableInvalidException(msg="No name.",
                                                  object=self)
        if self.type == ControlVariableType.constant:
            if self.const_value is None:
                raise ControlVariableInvalidException(msg="Type constant, but "
                                                          "const_value empty.",
                                                      object=self)
        elif self.type == ControlVariableType.linear:
            if (self.lin_start is None) or (self.lin_stop is None):
                raise ControlVariableInvalidException(msg="Type linear, but "
                                                          "lin_start/stop is "
                                                          "not set.",
                                                      object=self)
        elif self.type == ControlVariableType.expression:
            if (self.exp_from is None) or (self.exp_to is None):
                raise ControlVariableInvalidException(msg="Type expression, "
                                                          "but exp_from/to is "
                                                          "not set.",
                                                      object=self)
            if (self.exp_str is None):
                raise ControlVariableInvalidException(msg="Type expression, "
                                                          "but no expression "
                                                          "defined.",
                                                      object=self)
            x = self.exp_from  # note that this is not a complete test, as only
                               # one variant is verified. At this point, we are
                               # mostly concerned about syntax errors etc.
            try:
                value = eval(self.exp_str)
            except Exception as e:
                raise ControlVariableInvalidException(msg="Invalid expression "
                                                          "string: %s" % e,
                                                      object=self)

        else:
            raise ControlVariableInvalidException(msg="Invalid type.",
                                                  object=self)

