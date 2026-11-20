"""Keys and settings. Integrator-owned. Never print or log a value from here."""
import os
import pathlib

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEYS_FILE = pathlib.Path.home() / ".config" / "tokensand.env"

# The shared keys file first (every worktree sees a key the moment it is added), then this checkout's .env.
load_dotenv(KEYS_FILE)
load_dotenv(ROOT / ".env", override=True)


def env(name: str, default: str | None = None) -> str | None:
    """Reads the keys file again on a miss, so a key added mid-day needs no restart."""
    value = os.environ.get(name)
    if not value:
        load_dotenv(KEYS_FILE, override=True)
        value = os.environ.get(name)
    return value or default


def have(name: str) -> bool:
    return bool(env(name))


def public_url() -> str:
    """The day's tunnel address, no trailing slash. Empty until the tunnel is up."""
    return (env("PUBLIC_URL") or "").rstrip("/")


def mode() -> str:
    return env("SIGNOFF_MODE", "live")
