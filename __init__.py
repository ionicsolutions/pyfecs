# -*- coding: utf-8 -*-
#
#   (c) 2014-2017 Ionic Solutions
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
"""
**PyFECS** is the Python interface to the *Fast Experimental Control System*
(*FECS*) initially developed by Tim Ballance during his PhD on the IonCavity
UVC experiment.

A description of the general structure and functionality can be found in his PhD
thesis, section 5.4. We quote only the most relevant part:

    [T]he tools required for compiling the FPGA configuration have a large
    amount of overhead and can take a significant amount of time to produce
    the result. Furthermore, when directly programming the sequence a high
    degree of knowledge about the hardware configuration of system is required,
    and debugging problems can be very time consuming. To avoid these problems,
    we have developed firmware for the FPGA which implements a small home-made
    instruction parsing unit (IPU). The IPU executes a sequence of 32 bit
    instructions held in internal RAM. A sequence of instructions is loaded into
    RAM over the USB connection, then the sequence execution is triggered by
    software. The IPU has a small set of instructions: *set*, *wait*, *end of
    sequence*, *gate counter*, and *conditional jump*.

    The first three instructions allow for deterministic pulse sequence
    generation by configuring the logic state of the output bus with set
    commands, and delaying between successive sets with the wait command.
    The IPU is clocked with a 100 MHz signal derived from our atomic clock,
    providing a timing resolution of 10 ns.

*PyFECS* is one of the interfaces which can be used to load sequences into the
IPU. The original interface was written in Matlab and retired in the fall of
2016 when our license ran out and the demands for speed, automatization, and
ease-of-use in our Python-dominated environment grew.

*FECS* was designed and developed by Tim Ballance, who also designed the heavily
object-oriented structure of *PyFECS* and wrote the first Python compiler.
Beginning in the fall of 2016, Kilian Kluge took over development and
implemented variables, relative definition of time points, and jumps. For the
latter, a completely new Python compiler was written.

This documentation provides a fairly exhaustive description of *PyFECS* and
thereby covers a significant portion of *FECS* as well. For an introduction
to the use of *PyFECS* as an experimental tool, see the documentation for the
:class:`~tools.controller.Controller` class.

**List of contributors:**

- Tim Ballance (TB)
- Kilian Kluge (KK)
- You?


Third-party dependencies
------------------------
- *PyFECS* uses `Apache CouchDB <http://couchdb.apache.org/>`_ for data
  storage and management. CouchDB is licensed under the
  `Apache License Version 2.0 \
  <http://docs.couchdb.org/en/latest/about.html#license>`.

"""
__author__ = "Kilian Kluge and Tim Ballance"
__copyright__ = "2014-2017, Ionic Solutions"
__credits__ = ["Tim Ballance", "Kilian Kluge"]

__maintainer__ = "Kilian Kluge"
__email__ = "kluge@physik.uni-bonn.de"

