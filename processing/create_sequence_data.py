import io
import pickle

import couchdb
import numpy as np

from ..data.raw import RawData
from ..data.sequence import SequenceData
from ..objects.Sequence import Sequence


def create_sequence_data(sequence_id=None):
    """Create SequenceData objects for all unprocessed sequences."""
    couch = couchdb.Server()
    db = couch["fecs"]

    if sequence_id is not None:
        _create_sequence_data(db, sequence_id)
    else:
        for row in db.view("sequences/need-sequence-data"):
            _create_sequence_data(db, row.id)


def _create_sequence_data(db, document_id):
    response = db.get_attachment(document_id, "tdc_processed.npy")
    data = io.BytesIO()
    data.write(response.read())
    data.seek(0)
    tdc_data = np.load(data)

    document = db[document_id]
    measurement_id = document["measurement"]

    sequence_xml = db.get_attachment(measurement_id, "sequence.xml")
    if sequence_xml is None:
        return
    else:
        sequence = Sequence.from_file(sequence_xml)

    report_file = db.get_attachment(document_id, "report.pickle")
    compiler_report = pickle.load(report_file)

    raw_data = RawData.from_parsed(tdc_data)
    sequence_data = SequenceData.from_raw_data(raw_data,
                                               sequence,
                                               compiler_report)

    sequence_data_file = io.BytesIO()
    pickle.dump(sequence_data, sequence_data_file)
    db.put_attachment(document,
                      sequence_data_file.getvalue(),
                      "sequence_data.pickle",
                      content_type="application/octet-stream")


if __name__ == "__main__":
    create_sequence_data()
