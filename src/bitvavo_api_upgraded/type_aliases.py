"""
This file contains all type aliases that I use within the lib,
to clearify the intention or semantics/meaning/unit of a variable
"""
from typing import Any, Dict

# type simplification
anydict = Dict[str, Any]
strdict = Dict[str, str]
intdict = Dict[str, int]
errordict = Dict[str, Any]  # same type as anydict, but the semantics/meaning is different

# note: You can also use these for type conversion, so instead of int(some_float / 1000), you can just do ms(some_float / 1000)
# units
s = int  # seconds
ms = int  # milliseconds
us = int  # microseconds, normally written as μs, but nobody has the μ (mu) symbol on their keyboard, so `us` it is.

# same as above, but as a float, especially for the seconds
s_f = float  # seconds, but as float
ms_f = float  # milliseconds, but as float
us_f = float  # microseconds, but as float
