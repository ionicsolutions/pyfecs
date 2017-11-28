import datetime
import io
import pickle
import time

import couchdb
import numpy as np


class DataRetrievalException(Exception):
    pass


class DataManager(object):
    """Access to FECS data stored in CouchDB for humans.

    Optional parameters provide access to backups or
    remote servers.

    :param database: Name of the database
    :param address: Server address
    """

    def __init__(self, database="fecs", address="localhost"):
        self.s = couchdb.Server("http://%s:5984/" % address)
        self.db = self.s[database]

    @property
    def today(self):
        """Retrieve all measurements taken today."""
        today = datetime.datetime.now()
        return self.get_measurements_by_date(today.day)

    @property
    def yesterday(self):
        """Retrieve all measurements taken yesterday."""
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        return self.get_measurements_by_date(yesterday.day,
                                             yesterday.month,
                                             yesterday.year)

    def show_measurements(self, view_result):
        """Output a nicely formatted list of the measurements in the view."""
        for row in view_result:
            doc = self.db[row.id]
            print("%s: %s (%d/%d variants) %s"
                  % (time.strftime("%d %b %Y %H:%M:%S",
                                   time.localtime(doc["timestamp"])),
                     doc["name"],
                     len(doc["variants"]),
                     doc["number_of_variants"],
                     row.id))

    def iter_measurements(self, view_result):
        for row in view_result:
            yield row.id, self.db[row.id]

    def get_measurements_by_date(self, day,
                                 month=datetime.datetime.now().month,
                                 year=datetime.datetime.now().year):
        """Retrieve all measurements taken on a specific day."""
        start = datetime.datetime(year, month, day)
        end = start + datetime.timedelta(days=1)
        startkey = time.mktime(start.timetuple())
        endkey = time.mktime(end.timetuple())
        return self.retrieve_measurements_by_time_range(startkey,
                                                        endkey)

    def get_measurements_by_time(self, timestamp=datetime.datetime.now(),
                                 duration=datetime.timedelta(hours=-1)):
        """Retrieve all measurements taken within a time range."""
        startkey = time.mktime(timestamp.timetuple())
        end = timestamp + duration
        endkey = time.mktime(end.timetuple())
        return self.retrieve_measurements_by_time_range(startkey, endkey)

    def get_measurements_by_timestamp(self, timestamp):
        """Retrieve all measurements with a specific timestamp.

        The *timestamp* parameter can be given as either a
        *float* as returned by :meth:`time.time`, or a
        :class:`datetime.datetime` object.
        """
        if isinstance(timestamp, float):
            key = timestamp
        elif isinstance(timestamp, datetime.datetime):
            key = time.mktime(timestamp.timetuple())
        else:
            raise ValueError

        return self.db.view("measurements/by-time", key=key)

    def retrieve_measurements_by_time_range(self, start, end):
        """View containing all measurements within the specified time range."""
        return self.db.view("measurements/by-time",
                            startkey=start, endkey=end)

    def variants(self, measurement_id):
        """Generator over all variants of the measurement.

        Note that variants are not necessarily returned in any
        particular order. If the measurement is not complete,
        some variants will be missing.
        """
        measurement = self.db[measurement_id]
        for variant, variant_id in measurement["variants"].iteritems():
            yield self.db[variant_id]

    def get(self, measurement_id):
        """Retrieve a single measurement (or any other document)."""
        return self.db[measurement_id]

    def get_variant_id(self, measurement_id, variant):
        measurement = self.db[measurement_id]
        try:
            return measurement["variants"][str(variant)]
        except KeyError:
            raise ValueError

    def get_file(self, document_id, filename):
        """Retrieve a single file attached to a document."""
        return self.db.get_attachment(document_id, filename)

    def get_numpy_array(self, document_id, filename):
        """Retrieve a numpy array attached to a document."""
        response = self.get_file(document_id, filename)
        # convert to byte file which np.load can process
        data = io.BytesIO()
        data.write(response.read())
        data.seek(0)
        return np.load(data)

    def get_pickle(self, document_id, filename):
        """Retrieve a pickle object attached to a document."""
        response = self.get_file(document_id, filename)
        data = io.BytesIO()
        data.write(response.read())
        data.seek(0)
        try:
            return pickle.load(data)
        except Exception as e:
            print e
            raise DataRetrievalException
