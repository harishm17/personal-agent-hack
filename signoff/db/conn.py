"""SingleStore connection. Values come from config.env; none is ever printed."""
import os

import singlestoredb as s2

from signoff import config

DB = os.environ.get("SIGNOFF_DB", "signoff")


_APP = "__app__"


def connect(database: str | None = _APP, timeout: int = 5):
    """database=None connects to the server only; the default is the current `DB` (tests swap it per run)."""
    if database == _APP:
        database = DB
    return s2.connect(host=config.env("SINGLESTORE_HOST"), port=int(config.env("SINGLESTORE_PORT") or 3306),
                      user=config.env("SINGLESTORE_USER"), password=config.env("SINGLESTORE_PASSWORD"),
                      database=database, connect_timeout=timeout)
