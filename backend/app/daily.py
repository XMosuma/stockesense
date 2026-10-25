"""python -m app.daily : import every CSV in the inbox folder, then re-forecast.

Drop new sales exports into data/inbox/. Good files move to data/processed/,
bad ones are renamed *.failed with the reason printed in the log.
"""
import glob
import os
import shutil

from .db import connect
from .forecast import run
from .importer import import_csv_text

INBOX = os.getenv("INBOX_DIR", "/data/inbox")
DONE = os.getenv("PROCESSED_DIR", "/data/processed")


def main():
    os.makedirs(INBOX, exist_ok=True)
    os.makedirs(DONE, exist_ok=True)
    with connect() as conn:
        for f in sorted(glob.glob(os.path.join(INBOX, "*.csv"))):
            try:
                with open(f, encoding="utf-8-sig") as fh:
                    print("imported", os.path.basename(f), import_csv_text(conn, fh.read()))
            except ValueError as e:
                conn.rollback()
                print("SKIPPED", os.path.basename(f), "-", e)
                shutil.move(f, f + ".failed")
                continue
            shutil.move(f, os.path.join(DONE, os.path.basename(f)))
        try:
            print("forecast:", run(conn))
        except ValueError as e:
            print("No forecast:", e)


if __name__ == "__main__":
    main()
