import os

os.environ["SIGNOFF_OBS"] = "off"  # tests send no analytics events
os.environ["SIGNOFF_EGRESS"] = "off"  # and a faked model call leaves no row in the outbound ledger
os.environ["SIGNOFF_RECEIPTS"] = "memory"  # tests keep the receipt chain in memory; one test writes a file on purpose

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def no_notes_left_over():
    """Each test starts with no degraded-path notes from the one before."""
    from signoff.engine import health, rules, state
    health.reset()
    held, state._ratings_fn = state._ratings_fn, lambda: None  # no test reads the real reviews cache; one that needs ratings sets its own
    yield
    state._ratings_fn = held
    health.reset()
    rules.declare_units({})  # a sheet's own units do not outlive the test that loaded it
