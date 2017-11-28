import numpy as np
from time import time as get_time

# The datastream is structured as described on pages 8 and 9 in the
# manual: Each entry is 32 bits long. The lower 24 bits are timestamps,
# the next 6 bits contain the channel, and the remaining 2 bits contain
# information on the type of the event, i.e. whether it is a falling/rising
# transition.
FALLING_TRANSITION = 2
RISING_TRANSITION = 3

CHANNEL_MASK = (2**6)-1 << 24
TIME_MASK = (2**24)-1

# Since the time information stored for each hit is only 24 bits long,
# there are timer rollovers each 419 microseconds (cf. manual page 7,
# section 1.5) which we need to find to calculate the actual timestamps.
# The TDC signals the rollovers in the marker region, i.e. the upper 8
# bits (cf. manual page 9).
ROLLOVER = 16

# In the FECS configuration, we detect falling transitions and use 8 channels
PHOTON_TYPE = FALLING_TRANSITION
TDC_CHANNELS = 8


class SyncPulseNotFoundException(Exception):
    pass


def parse(data_stream, sync_channel=7):
    """High-speed TDC-data parser.

    In the early days of PyFECS, the processing of TDC data was
    solved in a very complicated manner, which was very slow. The
    old code in `tools` and `ktools` can still be found in
    git revision 2596c391fe2a958752d27c84da26160a15386a22.

    The implementation here is significantly faster and
    straightforward to understand and debug.
    """
    start = get_time()

    # Processing Python lists is significantly faster than numpy.arrays
    if isinstance(data_stream, np.ndarray):
        data_stream = data_stream.tolist()

    channel_data = [[] for _ in xrange(TDC_CHANNELS)]
    rollover = 0
    for entry in data_stream:
        if entry >> 24 == ROLLOVER:
            rollover = (entry & TIME_MASK) << 24
        elif entry >> 30 == PHOTON_TYPE:
            channel = (entry & CHANNEL_MASK) >> 24
            time = entry & TIME_MASK
            channel_data[channel].append(time + rollover)
        else:
            print "Skipping entry %s" % format(entry, '#034b')

    print "Total Counts:"
    for channel, data in enumerate(channel_data):
        print "Ch. %d: %d counts" % (channel, len(data))

    synced_data = [[] for _ in xrange(TDC_CHANNELS)]
    if channel_data[sync_channel]:
        sync_time = channel_data[sync_channel][0]
        for channel, data in enumerate(channel_data):
            synced_data[channel] = [t-sync_time for t in data
                                    if (t-sync_time) >= 0]
    else:
        raise SyncPulseNotFoundException

    print "Parser Summary:"
    for channel, data in enumerate(synced_data):
        print "Ch. %d: %d counts" % (channel, len(data))

    print "Time: %d ms" % ((get_time()-start)*1000)
    return synced_data
