import os

os.environ["SIGNOFF_OBS"] = "off"  # tests send no analytics events
os.environ["SIGNOFF_RECEIPTS"] = "memory"  # tests keep the receipt chain in memory; one test writes a file on purpose

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def no_notes_left_over():
    """Each test starts with no degraded-path notes from the one before."""
    from signoff.engine import health, rules
    health.reset()
    yield
    health.reset()
    rules.declare_units({})  # a sheet's own units do not outlive the test that loaded it
