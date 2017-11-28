import couchdb
import io
import numpy as np

from .tdc_parser import parse, SyncPulseNotFoundException


def process_all():
    """Process all unprocessed sequences."""
    couch = couchdb.Server()
    db = couch["fecs"]

    for row in db.view("sequences/need-tdc-processing"):
        response = db.get_attachment(row.id, "tdc.npy")

        if response is not None:
            # convert to byte file which np.load can process
            data = io.BytesIO()
            data.write(response.read())
            data.seek(0)
            data_stream = np.load(data)

            try:
                parsed = parse(data_stream)
            except SyncPulseNotFoundException:
                continue
            else:
                processed = io.BytesIO()
                np.save(processed, parsed)
                doc = db[row.id]
                db.put_attachment(doc, processed.getvalue(),
                                  "tdc_processed.npy",
                                  content_type="application/octet-stream")
    

if __name__ == "__main__":
    process_all()