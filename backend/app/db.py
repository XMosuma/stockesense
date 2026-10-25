import os

import psycopg
from psycopg.rows import dict_row

URL = os.getenv("DATABASE_URL", "postgresql://stocksense:stocksense@localhost:5432/stocksense")


def connect():
    """New connection; use as `with connect() as conn:` (commits on success, rolls back on error)."""
    return psycopg.connect(URL, row_factory=dict_row)
