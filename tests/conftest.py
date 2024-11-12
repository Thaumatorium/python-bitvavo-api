"""
run `pytest --fixtures` to see what's available within a test_* function
"""

import logging
from typing import Any

import pytest

from bitvavo_api_upgraded.bitvavo import Bitvavo
from bitvavo_api_upgraded.settings import BITVAVO

logger = logging.getLogger("conftest")


@pytest.fixture(scope="session")
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


@pytest.fixture(scope="session")
def websocket(bitvavo: Bitvavo) -> Bitvavo.WebSocketAppFacade:
    def errorCallback(error: Any) -> None:
        msg = f"Error callback: {error}"
        logger.error(msg)

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

    websocket: Bitvavo.WebSocketAppFacade = bitvavo.newWebsocket()
    websocket.setErrorCallback(errorCallback)
    return websocket


@pytest.fixture(autouse=True)
def wrap_public_request(monkeypatch: pytest.MonkeyPatch, bitvavo: Bitvavo) -> None:
    """
    The reason for this wrapper fixture, is that the Bitvavo API has changed a
    bit and is now generating output that doesn't conform to my tests, but since
    I presume that this output does not matter - typically it contains markets
    that are not in use anymore - I can remove them.
    """
    # Market exceptions to remove, as of 2024-11-11
    market_exceptions = ["BABYDOGE-EUR", "PEAQ-EUR", "UXLINK-EUR", "KLAY-EUR", "ORN-EUR", "DEGEN-EUR"]
    original_public_request = bitvavo.publicRequest

    def wrapped_public_request(*args: Any, **kwargs: Any) -> Any:
        # Call the original method
        response = original_public_request(*args, **kwargs)

        if isinstance(response, list):
            for idx, item in enumerate(response):
                if isinstance(item, list):
                    continue
                if item.get("market", None) and item["market"] in market_exceptions:
                    # remove the market item
                    del response[idx]
        return response

    # Monkeypatch the `publicRequest` method of the Bitvavo instance
    monkeypatch.setattr(bitvavo, "publicRequest", wrapped_public_request)
