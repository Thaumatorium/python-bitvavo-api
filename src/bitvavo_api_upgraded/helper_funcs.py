"""
Some helper functions that should make my life a lot easier
"""
from time import time

from bitvavo_api_upgraded.type_aliases import ms, s_f


def time_ms() -> ms:
    return int(time() * 1000)


def time_to_wait(rateLimitResetAt: ms) -> s_f:
    return s_f((rateLimitResetAt - time_ms()) / 1000)
