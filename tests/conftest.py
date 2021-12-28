"""
run `pytest --fixtures` to see what's available within a test_* function
"""
import logging
import os

from dotenv.main import load_dotenv
from pytest import fixture

from bitvavo_api_upgraded.bitvavo import Bitvavo

load_dotenv()  # load variables from `.env` file

logger = logging.getLogger("conftest")


@fixture(scope="session")
def bitvavo():
    return Bitvavo(
        {
            # create a file called .env and put the keys there
            "APIKEY": os.environ["BITVAVO_APIKEY"],
            "APISECRET": os.environ["BITVAVO_APISECRET"],
            "RESTURL": "https://api.bitvavo.com/v2",
            "WSURL": "wss://ws.bitvavo.com/v2/",
            "ACCESSWINDOW": 10000,
            "DEBUGGING": False,
        },
    )


@fixture(scope="session")
def websocket(bitvavo: Bitvavo):
    def errorCallback(error):
        logger.error(f"Error callback: {error}")

    bitvavo = Bitvavo(
        {
            # create a file called .env and put the keys there
            "APIKEY": os.environ["BITVAVO_APIKEY"],
            "APISECRET": os.environ["BITVAVO_APISECRET"],
            "RESTURL": "https://api.bitvavo.com/v2",
            "WSURL": "wss://ws.bitvavo.com/v2/",
            "ACCESSWINDOW": 10000,
            "DEBUGGING": False,
        },
    )

    websocket: Bitvavo.websocket = bitvavo.newWebsocket()
    websocket.setErrorCallback(errorCallback)
    return websocket
