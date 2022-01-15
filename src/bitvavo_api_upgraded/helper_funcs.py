"""
Some helper functions that should make my life a lot easier
"""
from time import time

from bitvavo_api_upgraded.type_aliases import ms, s_f


def time_ms() -> ms:
    return int(time() * 1000)


def time_to_wait(rateLimitResetAt: ms) -> s_f:
    curr_time = time_ms()
    if curr_time > rateLimitResetAt:
        # rateLimitRemaining has already reset
        return 0
    else:
        return abs(s_f((rateLimitResetAt - curr_time) / 1000))
