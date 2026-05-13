from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def reset_limiter() -> None:
    """Reset the in-memory rate-limit counters. Used in tests only."""
    limiter._storage.reset()
