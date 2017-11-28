"""The :mod:`controller` module provides script-level access to PyFECS.

The :class:`Controller` can be directly integrated into measurement scripts and
gives the experimenter convenient high-level access to all *FECS* components.
While the goal of the :mod:`controller` module is to make the use of *PyFECS*
as easy and straightforward as possible, the developers can only stress again
and again how important it is for the user to deeply understand what is going on
behind the scenes. Not only to be able to find the source of errors, but more
importantly to make sense of the recorded data and to be certain that its
interpretation is valid and reliable.
"""
import PyHWI
import couchdb
import hashlib
import io
import json
import logging
import numpy as np
import os
import pickle
import random
import time
import xmlrpclib
from shutil import copyfile

from ..compiler.compiler import Compiler
from ..objects.Sequence import Sequence
from ..objects.exceptions import *

opj = os.path.join


class Controller(object):
    def __init__(self, FPGA, TDC=None, EFrame=None, check=False):
        self.logger = logging.getLogger("PyFECS.Controller")

        self.logger.info("Connecting to FPGA.")
        self.FPGA = PyHWI.DCC(FPGA, nff=True)

        if TDC is not None:
            self.logger.info("Connecting to TDC.")
            self.TDC = PyHWI.DCC(TDC, nff=True)
            self.TDC.stop()
            self.useTDC = True
        else:
            self.useTDC = False

        if EFrame is not None:
            self.logger.info("Connecting to EFrame %s." % EFrame)
            server = PyHWI.lookup.resolve(EFrame)
            self.s = xmlrpclib.ServerProxy("http://%s:%d" % server)
            self.check = check
            self.useRC = True
        else:
            self.check = False
            self.useRC = False

        self.logger.info("Connecting to CouchDB.")
        self.couch = couchdb.Server()
        self.db = self.couch["fecs"]
        self.id = self.couch.uuids(1)[0]
        self.measurement_variants = -1

        self.spc_channels = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def repeat_measurement(self, measurement_id):
        measurement = self.db[measurement_id]
        sequence = Sequence.from_file(self.db.get_attachment(measurement,
                                                             "sequence.xml"))
        return self.run_measurement(sequence,
                                    randomize=measurement["randomized"])

    def resume_measurement(self, measurement_id):
        measurement = self.db[measurement_id]

        measurement_variants = range(measurement["number_of_variants"])
        taken_variants = map(int, measurement["variants"].keys())
        remaining_variants = [variant for variant in measurement_variants
                              if variant not in taken_variants]

        if not remaining_variants:
            self.logger.warning("All %d variants have already been taken!",
                                measurement["number_of_variants"])
            return measurement_id

        sequence = Sequence.from_file(self.db.get_attachment(measurement,
                                                             "sequence.xml"))

        return self.run_measurement(sequence,
                                    randomize=measurement["randomized"],
                                    measurement_id=measurement_id,
                                    measurement_variants=remaining_variants)

    def run_measurement(self, sequence, variants=-1,
                        randomize=False, truncate=False,
                        measurement_id=None,
                        measurement_variants=None,
                        file_name=None):

        if measurement_id is None:
            self.id = self.couch.uuids(1)[0]
        else:
            self.id = measurement_id

        if self.id in self.db:
            measurement = self.db[self.id]
            # reload sequence for consistency
            sequence = Sequence.from_file(
                self.db.get_attachment(measurement, "sequence.xml"))
            variants = sequence.variants
        else:
            if variants > 0:
                sequence.variants = variants
            else:
                variants = sequence.variants

            measurement = {
                "type": "measurement",
                "timestamp": time.time(),
                "name": sequence.name,
                "randomized": randomize,
                "number_of_variants": variants,
                "variants": {}
            }

            self.db[self.id] = measurement
            self.db.put_attachment(measurement, sequence.get_XML(),
                                   "sequence.xml")

        if self.useRC:
            self.logger.info("Claiming hardware resources.")
            self.s.resources.remoteClaim()
            while not self.s.resources.remoteClaimRequestHandled():
                self.logger.debug("Waiting for remote request to be handled.")
                time.sleep(0.5)
            while self.s.resources.isClaiming():
                self.logger.debug("Waiting for EFrame to claim resources.")
                time.sleep(0.5)
            if not self.s.resources.areClaimed():
                self.logger.error("Failed to claim hardware resources.")
                return self.id, False
            measurement["status"] = json.loads(self.s.getStatus())

        if measurement_variants is None:
            measurement_variants = range(variants)

        if randomize:
            random.shuffle(measurement_variants)

        if self.useTDC:
            self.logger.info("Starting TDC.")
            self.TDC.start()
            time.sleep(0.1)

        self.measurement_variants = variants
        scanDirName = time.strftime('PFC-%Y%m%d-%H%M%S')
        os.mkdir(opj(self.id, scanDirName))
        if file_name is not None:
            copyfile(file_name,
                     opj(self.id, scanDirName, 'sequence.xml'))

        for variant in measurement_variants:
            self.logger.info("Taking variant %d of %d.",
                             variant, variants)
            sequence_id = self.measure_sequence(sequence, variant, truncate,
                                                scanDirName=scanDirName)

            if self.check:
                self.logger.info("Checking for ion.")
                if self._check_for_ion():
                    self.logger.info("Found the ion.")
                else:
                    self.logger.error("Lost the ion. Aborting.")
                    complete = False
                    break

            measurement["variants"][variant] = sequence_id

        else:
            complete = True

        if self.useTDC:
            self.logger.info("Stopping TDC.")
            self.TDC.stop()

        if self.useRC:
            self.logger.info("Releasing hardware resources.")
            self.s.resources.remoteRelease()
            while not self.s.resources.remoteReleaseRequestHandled():
                self.logger.debug("Waiting for remote request to be handled.")
                time.sleep(0.5)
            while self.s.resources.isClaiming():
                self.logger.debug("Waiting for EFrame to release resources.")
                time.sleep(0.5)
            if self.s.resources.areClaimed():
                self.logger.error("Failed to release hardware resources.")
            else:
                self.logger.info("Released hardware resources.")

        self.db[self.id] = measurement

        return self.id, complete

    def measure_sequence(self, sequence, variant, truncate, scanDirName=''):
        sequence_id = self.couch.uuids(1)[0]

        doc = {
            "type": "sequence",
            "name": sequence.name,
            "variant": variant,
            "timestamp": time.time(),
            "measurement": self.id
        }

        self.logger.info("Compiling sequence %s.", sequence.name)
        compiler = Compiler()
        compiler.load(sequence)
        compiledSequence, report = compiler.compile(variant)
        compiledSequence = np.array(compiledSequence,
                                    dtype=np.uint32)

        compiledSequence = compiledSequence.tostring()
        doc["hashed_sequence"] = hashlib.md5(compiledSequence).hexdigest()

        self.logger.info("Configure and load FPGA.")
        self.FPGA.setRepeatCount(sequence.shots)
        self.FPGA.uploadSequence(compiledSequence)
        self.FPGA.setIdleState(
            sequence.HWConfig.idle_state ^ sequence.HWConfig.polarity_mask)

        spc_channels = []
        for name in sequence.control_channels:
            id_ = sequence.HWConfig.spc_channels[name].channelID
            self.FPGA.setSPCStatus(id_, 1)
            spc_channels.append(id_)

        for id_ in range(2):
            if id_ not in spc_channels:
                self.FPGA.setSPCStatus(id_, 0)

        self.logger.info("Starting FPGA.")
        self.FPGA.startSequence()

        while not self.FPGA.isFinished()[0]:
            self.logger.debug("Waiting for FPGA to finish measuring.")
            time.sleep(0.1)

        self.logger.info("Measurement finished, downloading data.")

        self.db[sequence_id] = doc
        self.db.put_attachment(doc, pickle.dumps(report),
                               "report.pickle",
                               content_type="application/octet-stream")

        if self.useTDC:
            tdc_data = self._get_tdc_data()
            self.logger.info("Retrieved TDC data of length %d", len(tdc_data))
            tdc_output = io.BytesIO()
            np.save(tdc_output, tdc_data)
            self.db.put_attachment(doc, tdc_output.getvalue(), "tdc.npy",
                                   content_type="application/octet-stream")

            os.mkdir(opj(self.id, scanDirName, 'raw'))
            self._storeData(tdc_data, self.id, scanDirName, variant)

        for id_ in spc_channels:
            spc_data, spc_missing = self._get_spc_data(id_)
            self.logger.info("Retrieved SPC data for channel %d of length %d.",
                             id_, len(spc_data))
            spc_output = io.BytesIO()
            np.save(spc_output, spc_data)
            self.db.put_attachment(doc, spc_output.getvalue(),
                                   "spc_%i.npy" % id_,
                                   content_type="application/octet-stream")
            doc["spc_%i_missing"] = spc_missing

        return sequence_id

    def _get_tdc_data(self):
        rawData = np.fromstring(self.TDC.readAll()[0], dtype="uint32")
        self.logger.info("Taken data of length %d", len(rawData))
        return np.array(rawData)

    def _get_spc_data(self, id_):
        results = self.FPGA.readSPCData(id_)
        spc_data = np.fromstring(results[0], dtype="uint32")
        spc_missing = results[2]
        return spc_data, spc_missing

    def _check_for_ion(self):
        try:
            self.s.ionDetector.remoteDetection()
            time.sleep(0.5)
            while self.s.ionDetector.isDetecting():
                time.sleep(0.5)
            return self.s.ionDetector.getIonPresent()
        except xmlrpclib.Fault as e:
            self.logger.error("Remote call to ionDetector failed: %s", e)
            return False

    def _storeData(self, TDCData, dataDir, scanDirName, variant):
        variants = self.measurement_variants
        if self.useTDC:
            TDCData.tofile(
                opj(dataDir, scanDirName, 'raw', str(variant).zfill(
                    int(np.ceil(np.log10(variants)))) + '.bin'))

    def close(self):
        self.logger.info("Closing all connections.")

        try:
            self.FPGA.close()
        except Exception as e:
            self.logger.error("Failed to disconnect FPGA: %s", e)

        if self.useTDC:
            try:
                self.TDC.close()
            except Exception as e:
                self.logger.error("Failed to disconnect TDC: %s", e)

        if self.useRC:
            try:
                self.s.resources.remoteRelease()
            except Exception as e:
                self.logger.error("Failed to release resources: %s", e)

    def __del__(self):
        self.close()
