import pickle


class CompilerReport(object):
    def __init__(self):

        self.TRUNCATE = False
        self.CONTROL_REGISTER_HIGH_TIME = 1
        self.constants = {}

        self.control_values = {}
        self.variant = 0
        self.fpga_delay_unit = 10.0 * 10 ** -9
        self.length = 0.0

        self.compiled = []
        self.contains_jumps = False

    @classmethod
    def from_compiler_instance(cls, compiler, compiled):
        report = cls()
        # copy flags
        report.TRUNCATE = compiler.TRUNCATE
        report.CONTROL_REGISTER_HIGH_TIME = \
            compiler.CONTROL_REGISTER_HIGH_TIME
        # copy constants
        report.constants = compiler.constants
        # copy sequence info
        report.control_values = compiler.control_values
        report.variant = compiler.variant
        report.fpga_delay_unit = compiler.fpga_delay_unit
        report.length = compiler.length
        report.contains_jumps = [] != compiler.sequence.jumps
        # compiled
        report.compiled = compiled
        return report

    @classmethod
    def from_file(cls, filename):
        with open(filename, "r") as pickled_report:
            report = pickle.load(pickled_report)
        if isinstance(report, cls):
            return report
        else:
            raise ValueError("Loaded object is not an instance of %s."
                             % cls.__class__)

    def to_file(self, filename):
        with open(filename, "w") as pickle_file:
            pickle.dump(self, pickle_file)
