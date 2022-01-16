"""
run `pytest --fixtures` to see what's available within a test_* function
"""
import logging
import os
from typing import Any

from pytest import fixture

from bitvavo_api_upgraded.bitvavo import Bitvavo
from bitvavo_api_upgraded.settings import BITVAVO

logger = logging.getLogger("conftest")


@fixture(scope="session")
def bitvavo() -> Bitvavo:
    return Bitvavo(
        {
            # create a file called .env and put the keys there
            "APIKEY": BITVAVO.APIKEY,
            "APISECRET": BITVAVO.APISECRET,
            "RESTURL": BITVAVO.RESTURL,
            "WSURL": BITVAVO.WSURL,
            "ACCESSWINDOW": BITVAVO.ACCESSWINDOW,
            "DEBUGGING": BITVAVO.DEBUGGING,
        },
    )


@fixture(scope="session")
def websocket(bitvavo: Bitvavo) -> Bitvavo.websocket:
    def errorCallback(error: Any) -> None:
        logger.error(f"Error callback: {error}")

    bitvavo = Bitvavo(
        {
            # create a file called .env and put the keys there
            "APIKEY": BITVAVO.APIKEY,
            "APISECRET": BITVAVO.APISECRET,
            "RESTURL": BITVAVO.RESTURL,
            "WSURL": BITVAVO.WSURL,
            "ACCESSWINDOW": BITVAVO.ACCESSWINDOW,
            "DEBUGGING": BITVAVO.DEBUGGING,
        },
    )

    websocket: Bitvavo.websocket = bitvavo.newWebsocket()
    websocket.setErrorCallback(errorCallback)
    return websocket
