import logging
import unittest
from HardwareConfig import HardwareConfig
import os

testpath = os.path.dirname(os.path.realpath(__file__))
logging.basicConfig(level=logging.DEBUG)


class HardwareLoadingAndSaving(unittest.TestCase):
    def test_configuration_loads_from_file(self):
        h = HardwareConfig.from_file(testpath + "/test_sequences/uvc_config.xml")

    def test_empty_configuration_can_be_saved(self):
        h = HardwareConfig()
        h.name = "Auto-generated empty configuration"
        h.save_XML(testpath + "/test_sequences/empty_config.xml")


if __name__ == "__main__":
    unittest.main()
