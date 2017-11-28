import logging
logging.basicConfig()

import unittest
import xml.etree.ElementTree as ET

import ControlRegister
from .exceptions import XMLDefinitionException, InvalidSequenceException


class TestBit(unittest.TestCase):
    def test_initialization_from_XML(self):
        xRoot = ET.fromstring("<bit input='4' output='5'>0</bit>")
        bit = ControlRegister.Bit.fromXML(xRoot)

        self.assertEqual(bit.input, 4)
        self.assertEqual(bit.output, 5)
        self.assertEqual(bit.value, 0)

    def test_XML_must_be_complete(self):
        wrong_XML = ["<bit />",
                     "<bit>0</bit>",
                     "<bit input='4' />",
                     "<bit output='8' />",
                     "<bit input='2' output='7' />",
                     "<bit input='0'>4</bit>",
                     "<bit output='6'>3</bit>"]
        for example in wrong_XML:
            xRoot = ET.fromstring(example)
            with self.assertRaises(XMLDefinitionException):
                bit = ControlRegister.Bit.fromXML(xRoot)

    def test_XML_must_be_of_correct_type(self):
        wrong_XML = ["<bit input='1' output='two'>3</bit>",
                     "<bit input='four' output='5'>6</bit>",
                     "<bit input='7' output='8'>nine</bit>"]
        for example in wrong_XML:
            xRoot = ET.fromstring(example)
            with self.assertRaises(XMLDefinitionException):
                bit = ControlRegister.Bit.fromXML(xRoot)

    def test_XML_export_consistency(self):
        xRoot = ET.fromstring("<bit input='2' output='4'>0</bit>")
        bit = ControlRegister.Bit.fromXML(xRoot)
        xRoot2 = bit.XML
        bit2 = ControlRegister.Bit.fromXML(xRoot2)
        self.assertEqual(bit, bit2)

    def test_verification_fails_when_incomplete(self):
        configurations = [(None, 1, 2), (3, None, 4), (5, 6, None),
                          (None, None, 7), (None, 8, None), (9, None, None),
                          (None, None, None)]
        for config in configurations:
            bit = ControlRegister.Bit()
            bit.input, bit.output, bit.value = config
            with self.assertRaises(InvalidSequenceException):
                bit.verify()

    def test_verification_succeeds_when_valid(self):
        bit = ControlRegister.Bit()
        bit.input, bit.output, bit.value = (0, 4, 4)
        bit.verify()


class TestControlRegisterXML(unittest.TestCase):
    def test_initialization_from_XML(self):
        xRoot = ET.fromstring('''<control_register>
          <length>5</length>
          <bit output="1" input="3">0</bit>
          <bit output="2" input="4">1</bit>
          <bit output="3" input="6">2</bit>
          <bit output="4" input="7">3</bit>
          <bit output="5" input="5">4</bit>
        </control_register>''')
        controlRegister = ControlRegister.ControlRegister.fromXML(xRoot)

        self.assertEqual(controlRegister.length, 5)
        self.assertEqual(len(controlRegister.bits), controlRegister.length)

    def test_XML_must_be_complete(self):
        wrong_XML = ['<control_register />',
                     '''<control_register>
                       <length>5</length>
                     </control_register>''',
                     '''<control_register>
                               <bit output="1" input="3">0</bit>
                               <bit output="2" input="4">1</bit>
                    </control_register>''',
                     '''<control_register>
                               <length>3</length>
                               <bit output="1" input="3">0</bit>
                               <bit output="2" input="4">1</bit>
                               <bit output="3" input="6">2</bit>
                               <bit output="4" input="7">3</bit>
                               <bit output="5" input="5">4</bit>
                             </control_register>''',
                     '''<control_register>
                               <length>8</length>
                               <bit output="1" input="3">0</bit>
                               <bit output="2" input="4">1</bit>
                               <bit output="3" input="6">2</bit>
                               <bit output="4" input="7">3</bit>
                               <bit output="5" input="5">4</bit>
                             </control_register>'''
                     ]
        for example in wrong_XML:
            xRoot = ET.fromstring(example)
            with self.assertRaises(XMLDefinitionException):
                bit = ControlRegister.ControlRegister.fromXML(xRoot)

        def test_XML_export_consistency(self):
            xRoot = ET.fromstring('''<control_register>
                      <length>5</length>
                      <bit output="1" input="3">0</bit>
                      <bit output="2" input="4">1</bit>
                      <bit output="3" input="6">2</bit>
                      <bit output="4" input="7">3</bit>
                      <bit output="5" input="5">4</bit>
                    </control_register>''')
            controlRegister = ControlRegister.ControlRegister.fromXML(xRoot)
            xRoot2 = controlRegister.XML
            controlRegister2 = ControlRegister.ControlRegister.fromXML(xRoot2)
            self.assertEqual(controlRegister, controlRegister2)


class TestControlRegister(unittest.TestCase):
    def setUp(self):
        self.cR = ControlRegister.ControlRegister()
        self.cR.length = 4

        bit_configurations = [(0, 1, 0), (1, 2, 1), (2, 3, 2), (3, 4, 3)]
        for config in bit_configurations:
            bit = ControlRegister.Bit()
            bit.input, bit.output, bit.value = config
            self.cR.bits[bit.value] = bit

    def test_comparison(self):
        self.assertEqual(self.cR, self.cR)

        cR2 = ControlRegister.ControlRegister()
        cR2.length = 4

        bit_configurations = [(0, 1, 1), (1, 2, 1), (2, 3, 2), (3, 4, 3)]
        for config in bit_configurations:
            bit = ControlRegister.Bit()
            bit.input, bit.output, bit.value = config
            cR2.bits[bit.value] = bit

        self.assertNotEqual(self.cR, cR2)

    def test_mask_is_correct(self):
        self.assertEqual(self.cR.mask, 0b11110)

    def test_negative_mask_is_consistent(self):
        expected = (2**24 - 1) - self.cR.mask
        print("")
        print format(self.cR.mask, "#026b")
        print format(expected, "#026b")
        self.assertEqual(self.cR.negative_mask, expected)

    def test_mapValueToState_raises_exception_when_output_too_long(self):
        with self.assertRaises(ValueError):
            self.cR.value_to_state(10000)

    def test_mapValueToState_computes_correctly(self):
        inputs = range(self.cR.length)
        for value in inputs:
            self.assertEqual(self.cR.value_to_state(value), value << 1)

    def test_valid_register_verifies(self):
        self.cR.verify()

    def test_length_mismatch_fails_verification(self):
        del (self.cR.bits[0])
        with self.assertRaises(InvalidSequenceException):
            self.cR.verify()

    def test_non_unique_bit_values_fail_verification(self):
        del (self.cR.bits[0])
        bit = ControlRegister.Bit()
        bit.input, bit.output, bit.value = (5, 5, 1)
        self.cR.bits[1] = bit
        with self.assertRaises(InvalidSequenceException):
            self.cR.verify()

    def test_not_rangelike_bit_values_fail_verification(self):
        del (self.cR.bits[0])
        bit = ControlRegister.Bit()
        bit.input, bit.output, bit.value = (5, 5, 8)
        self.cR.bits[8] = bit
        with self.assertRaises(InvalidSequenceException):
            self.cR.verify()

    def test_non_integer_bit_values_fail_verification(self):
        del (self.cR.bits[2])
        bit = ControlRegister.Bit()
        bit.input, bit.output, bit.value = (5, 5, 8)
        self.cR.bits[2.5] = bit
        with self.assertRaises(InvalidSequenceException):
            self.cR.verify()

    def test_inconsistent_bit_values_fail_verification(self):
        self.cR.bits[3].value = 4
        with self.assertRaises(InvalidSequenceException):
            self.cR.verify()

    def test_non_unique_output_channels_fail_verification(self):
        self.cR.bits[0].output = 2
        with self.assertRaises(InvalidSequenceException):
            self.cR.verify()

    def test_non_unique_input_channels_fail_verification(self):
        self.cR.bits[0].input = 1
        with self.assertRaises(InvalidSequenceException):
            self.cR.verify()

    def tearDown(self):
        del self.cR


if __name__ == "__main__":
    unittest.main()
