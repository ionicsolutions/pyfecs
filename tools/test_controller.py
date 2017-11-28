import PyHWI
import xmlrpclib
import time
import logging
logging.basicConfig(level=logging.DEBUG)
from PyFECS.tools import controller

server = PyHWI.lookup.resolve("IRC_EFrameRemote")
s = xmlrpclib.ServerProxy("http://%s:%d" % server)

c = controller.Controller("IRC_PulseSequenceFPGA", EFrame="IRC_EFrameRemote")
c.resume_measurement("data-20171025-161931")
print c._check_for_ion()
c.close()

huggel




def _check_for_ion(s):
    s.ionDetector.remoteDetection()
    time.sleep(0.5)
    while s.ionDetector.isDetecting():
        print "Detecting"
        time.sleep(0.5)
    return s.ionDetector.getIonPresent()

def _remote_load(s):
    s.loadingSequenceCW.remoteLoading()

print _check_for_ion(s)
print _remote_load(s)
