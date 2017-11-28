"""PyFECS-specific exceptions.

PyFECS makes heavy use of exceptions for flow control, as is customary for
Python. All exceptions are derived from :class:`FECSException`.
"""


class FECSException(Exception):
    """Base exception for all FECS exceptions."""

    def __init__(self, msg, *args, **kwargs):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class XMLParseException(FECSException):
    """Sequence XML file could not be parsed correctly.

    Raised when the XML is invalid."""
    pass


class XMLDefinitionException(FECSException):
    """Sequence definition in XML file is invalid.

    Raised when the XML is valid, but cannot be transformed
    into a sequence object."""
    pass


class IncompleteSequenceException(FECSException):
    """Sequence does not contain all necessary information."""
    pass


class InvalidSequenceException(FECSException):
    """Invalid or inconsistent sequence.

    Raised when :meth:`objects.sequence.Sequence.verify` fails."""

    def __init__(self, msg, object, *args, **kwargs):
        super(InvalidSequenceException, self).__init__(msg, object, *args,
                                                       **kwargs)
        self.object = object

    def __str__(self):
        try:
            msg = "Detected invalid definition in %s %s (%s): "\
                  % (self.object.__class__, self.object.name, self.object)
        except AttributeError:
            msg = "Detected invalid definition in %s (%s): "\
                  % (self.object.__class__, self.object)
        return msg + repr(self.msg)


class ControlVariableInvalidException(InvalidSequenceException):
    """Base exception for ControlVariables."""


class ControlVariableUndefinedException(ControlVariableInvalidException):
    """The value for the ControlVariable cannot be determined.

    Raised when :meth:`objects.ControlVariable.ControlVariable.getValue`
    fails due to insufficient or inconsistent configuration."""

    def __init__(self, name, object):
        msg = "Value of ControlVariable '%s' is undefined." % name
        super(ControlVariableUndefinedException, self).__init__(msg, object)


class ControlVariableUnresolvedException(ControlVariableInvalidException):
    """The ControlVariable cannot be found, most likely it is not defined.

    Raised when :meth:`objects.TimePoint.TimePoint.get_time` fails because
    the referenced variable cannot be found.
    """

    def __init__(self, name, object):
        msg = "Cannot find ControlVariable '%s'" % name
        super(ControlVariableUnresolvedException, self).__init__(msg, object)


class ReferenceInvalidException(InvalidSequenceException):
    """A reference which is invalid.

    Base exception for all Reference exceptions.
    """


class ReferenceRecursiveException(ReferenceInvalidException):
    """A reference depends on itself."""


class ReferenceUnresolvedException(ReferenceInvalidException):
    """A :class:`~objects.timePoints.Reference` has not been resolved yet.

    .. note:: This does not mean that the :class:`Reference` cannot be resolved,
              but that :meth:`objects.Sequence.Sequence.resolve_references`
              has not been called after the :class:`Reference` definition has
              been changed.
    """


class JumpInvalidException(InvalidSequenceException):
    """A Jump which is invalid."""


class CompilerErrorException(FECSException):
    """The compiler reached an inconsistent or invalid internal state.

    This points to an error either in verification of the
    :class:`~objects.Sequence.Sequence` object or in the compiler
    code itself. The appearance of this exceptions warrants a close
    examination of recent changes to the code.

    Raised by :meth:`compile.compileSequence`.
    """


class FECSNotImplementedException(FECSException):
    def __init__(self, feature):
        msg = 'Feature not implemened: %s' % \
              (str(feature))
        super(self.__class__, self).__init__(msg)


class IonLostException(FECSException):
    """The ion was lost during a measurement."""

    def __init__(self):
        msg = "The ion has been lost."
        super(self.__class__, self).__init__(msg)


class IonReloadFailedException(FECSException):
    """The automatic reload failed."""

    def __init__(self):
        msg = "Reloading of the ion has failed."
        super(self.__class__, self).__init__(msg)
