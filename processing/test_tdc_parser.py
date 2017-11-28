import numpy as np

from processing import tdc_parser

print "chmask: %s" % format(tdc_parser.CHANNEL_MASK, "#034b")
print "tmask : %s" % format(tdc_parser.TIME_MASK, "#034b")
rawData = np.fromfile("test_data/7.bin", dtype=np.uint32)

channel_data = tdc_parser.parse(rawData)

print channel_data[7]
print channel_data[0][0], channel_data[0][-1]