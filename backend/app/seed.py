"""python -m app.seed : load the sample shops and run the first forecast."""
from .db import connect
from .forecast import run
from .importer import import_df
from .sample import make_sample

if __name__ == "__main__":
    with connect() as conn:
        print("import:", import_df(conn, make_sample()))
        print("forecast:", run(conn))
