"""SingleStore connection. Values come from config.env; none is ever printed."""
import os

import singlestoredb as s2

from signoff import config

DB = os.environ.get("SIGNOFF_DB", "signoff")


def connect(database: str | None = DB, timeout: int = 5):
    return s2.connect(host=config.env("SINGLESTORE_HOST"), port=int(config.env("SINGLESTORE_PORT") or 3306),
                      user=config.env("SINGLESTORE_USER"), password=config.env("SINGLESTORE_PASSWORD"),
                      database=database, connect_timeout=timeout)
