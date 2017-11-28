import logging


class PyFECSObject(object):
    """PyFECS objects describe a measurement sequence.

    In order to be picklable, an object cannot contain references
    to file handlers etc. outside its own scope. Therefore, we
    need to remove the logger before pickling and add it back when
    unpickling. This guarantees that no matter the user's logging
    configuration, all objects can be pickled and integrate back
    into any logging configuration when unpickled.

    For more information, see `the documentation \
    <https://docs.python.org/3/library/pickle.html#pickle-state>`_.
    """
    def __init__(self):
        self.logger = logging.getLogger("PyFECS.objects")

    def __getstate__(self):
        state = self.__dict__.copy()
        del state["logger"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.logger = logging.getLogger("PyFECS.objects")