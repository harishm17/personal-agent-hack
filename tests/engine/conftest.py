import os

os.environ["SIGNOFF_OBS"] = "off"  # tests send no analytics events
os.environ["SIGNOFF_RECEIPTS"] = "memory"  # tests keep the receipt chain in memory; one test writes a file on purpose
