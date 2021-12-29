"""
Most of these tests check the keys of the response, the size of the response, the types of the response, which type
those values can be cast to (as quite a few responses return strings which are obviously int or float types, but those usually can also return "none")
"""
import json
import logging
from time import sleep

from pytest import mark

from bitvavo_api_upgraded.bitvavo import Bitvavo

logger = logging.getLogger("test_bitvavo")
"""
* This is an example utilising all functions of the python Bitvavo API wrapper.
* The APIKEY and APISECRET should be replaced by your own key and secret.
* For public functions the APIKEY and SECRET can be removed.
* Documentation: https://docs.bitvavo.com
* Bitvavo: https://bitvavo.com
* README: https://github.com/bitvavo/php-bitvavo-api
"""


class TestBitvavo:
    """this class functions as a grouping of tests, as the code is"""

    def test_remaining_limit(self, bitvavo: Bitvavo):
        limit = bitvavo.getRemainingLimit()
        assert limit == 1000, "default remaining limit should be 1000"

    def test_no_error(self, bitvavo: Bitvavo):
        """
        Any call to bitvavo should produce no errors.

        Below here is a giant list of undocumented error codes - source is CCTX:
        https://github.com/ccxt/ccxt/blob/master/python/ccxt/bitvavo.py

        101: Unknown error. Operation may or may not have succeeded.
        102: Invalid JSON.
        103: You have been rate limited. Please observe the Bitvavo-Ratelimit-AllowAt header to see when you can send requests again. Failure to respect self limit will result in an IP ban. The default value is 1000 weighted requests per minute. Please contact support if you wish to increase self limit.
        104: You have been rate limited by the number of new orders. The default value is 100 new orders per second or 100.000 new orders per day. Please update existing orders instead of cancelling and creating orders. Please contact support if you wish to increase self limit.
        105: Your IP or API key has been banned for not respecting the rate limit. The ban expires at ${expiryInMs}.
        107: The matching engine is overloaded. Please wait 500ms and resubmit your order.
        108: The matching engine could not process your order in time. Please consider increasing the access window or resubmit your order.
        109: The matching engine did not respond in time. Operation may or may not have succeeded.
        110: Invalid endpoint. Please check url and HTTP method.
        200: ${param} url parameter is not supported. Please note that parameters are case-sensitive and use body parameters for PUT and POST requests.
        201: ${param} body parameter is not supported. Please note that parameters are case-sensitive and use url parameters for GET and DELETE requests.
        202: ${param} order parameter is not supported. Please note that certain parameters are only allowed for market or limit orders.
        203: {"errorCode":203,"error":"symbol parameter is required."}
        204: ${param} parameter is not supported.
        205: ${param} parameter is invalid.
        206: Use either ${paramA} or ${paramB}. The usage of both parameters at the same time is not supported.
        210: Amount exceeds the maximum allowed amount(1000000000).
        211: Price exceeds the maximum allowed amount(100000000000).
        212: Amount is below the minimum allowed amount for self asset.
        213: Price is below the minimum allowed amount(0.000000000000001).
        214: Price is too detailed
        215: Price is too detailed. A maximum of 15 digits behind the decimal point are allowed.
        216: {"errorCode":216,"error":"You do not have sufficient balance to complete self operation."}
        217: {"errorCode":217,"error":"Minimum order size in quote currency is 5 EUR or 0.001 BTC."}
        230: The order is rejected by the matching engine.
        231: The order is rejected by the matching engine. TimeInForce must be GTC when markets are paused.
        232: You must change at least one of amount, amountRemaining, price, timeInForce, selfTradePrevention or postOnly.
        233: {"errorCode":233,"error":"Order must be active(status new or partiallyFilled) to allow updating/cancelling."}
        234: Market orders cannot be updated.
        235: You can only have 100 open orders on each book.
        236: You can only update amount or amountRemaining, not both.
        240: {"errorCode":240,"error":"No order found. Please be aware that simultaneously updating the same order may return self error."}
        300: Authentication is required for self endpoint.
        301: {"errorCode":301,"error":"API Key must be of length 64."}
        302: Timestamp is invalid. This must be a timestamp in ms. See Bitvavo-Access-Timestamp header or timestamp parameter for websocket.
        303: Window must be between 100 and 60000 ms.
        304: Request was not received within acceptable window(default 30s, or custom with Bitvavo-Access-Window header) of Bitvavo-Access-Timestamp header(or timestamp parameter for websocket).
        304: Authentication is required for self endpoint.
        305: {"errorCode":305,"error":"No active API key found."}
        306: No active API key found. Please ensure that you have confirmed the API key by e-mail.
        307: This key does not allow access from self IP.
        308: {"errorCode":308,"error":"The signature length is invalid(HMAC-SHA256 should return a 64 length hexadecimal string)."}
        309: {"errorCode":309,"error":"The signature is invalid."}
        310: This key does not allow trading actions.
        311: This key does not allow showing account information.
        312: This key does not allow withdrawal of funds.
        315: Websocket connections may not be used in a browser. Please use REST requests for self.
        317: This account is locked. Please contact support.
        400: Unknown error. Please contact support with a copy of your request.
        401: Deposits for self asset are not available at self time.
        402: You need to verify your identitiy before you can deposit and withdraw digital assets.
        403: You need to verify your phone number before you can deposit and withdraw digital assets.
        404: Could not complete self operation, because our node cannot be reached. Possibly under maintenance.
        405: You cannot withdraw digital assets during a cooldown period. This is the result of newly added bank accounts.
        406: {"errorCode":406,"error":"Your withdrawal is too small."}
        407: Internal transfer is not possible.
        408: {"errorCode":408,"error":"You do not have sufficient balance to complete self operation."}
        409: {"errorCode":409,"error":"This is not a verified bank account."}
        410: Withdrawals for self asset are not available at self time.
        411: You can not transfer assets to yourself.
        412: {"errorCode":412,"error":"eth_address_invalid."}
        413: This address violates the whitelist.
        414: You cannot withdraw assets within 2 minutes of logging in.
        """
        response = bitvavo.time()
        assert "error" not in response
        assert "errorCode" not in response

    def test_time(self, bitvavo: Bitvavo):
        response = bitvavo.time()
        assert type(response) == dict
        assert "time" in response
        assert type(response["time"]) == int

    def test_market(self, bitvavo: Bitvavo):
        response = bitvavo.markets({})

        # assert that the first result is 1INCH (just to check )
        assert response[0] == {
            "market": "1INCH-EUR",
            "status": "trading",
            "base": "1INCH",
            "quote": "EUR",
            "pricePrecision": 5,
            "minOrderInBaseAsset": "2",
            "minOrderInQuoteAsset": "5",
            "orderTypes": ["market", "limit", "stopLoss", "stopLossLimit", "takeProfit", "takeProfitLimit"],
        }

        for market in response:
            # Assert that each market contains these keys
            assert "market" in market
            assert "status" in market
            assert "base" in market
            assert "quote" in market
            assert "pricePrecision" in market
            assert "minOrderInBaseAsset" in market
            assert "minOrderInQuoteAsset" in market
            assert "orderTypes" in market

    def test_assets(self, bitvavo: Bitvavo):
        response = bitvavo.assets({})
        assert type(response) == list
        if len(response) > 0:
            assert type(response[0]) == dict

        # check all assets for the expected keys
        for asset in response:
            assert len(asset) == 11
            assert "symbol" in asset
            assert "name" in asset
            assert "decimals" in asset
            assert "depositFee" in asset
            assert "depositConfirmations" in asset
            assert "depositStatus" in asset
            assert "withdrawalFee" in asset
            assert "withdrawalMinAmount" in asset
            assert "withdrawalStatus" in asset
            assert "networks" in asset
            assert "message" in asset

        # check all assets for expected types
        for asset in response:
            assert type(asset["symbol"]) == str
            assert type(asset["name"]) == str
            assert type(asset["decimals"]) == int
            assert (
                type(asset["depositFee"]) == str
            )  # this can also return a "none" string. That's why this isn't a number type
            assert type(asset["depositConfirmations"]) == int
            assert type(asset["depositStatus"]) == str
            assert type(asset["withdrawalFee"]) == str
            assert type(asset["withdrawalMinAmount"]) == str
            assert type(asset["withdrawalStatus"]) == str
            assert type(asset["networks"]) == list  # so far it's always a list of one string.
            assert type(asset["message"]) == str

    def test_book(self, bitvavo: Bitvavo):
        response = bitvavo.book(symbol="BTC-EUR", options={})
        assert len(response) == 4
        assert "market" in response
        assert "nonce" in response
        assert "asks" in response
        assert "bids" in response

        assert response["market"] == "BTC-EUR"

        assert type(response["market"]) == str
        assert type(response["nonce"]) == int  # not a value that should ever be 0
        assert type(response["asks"]) == list
        assert type(response["bids"]) == list

        if len(response["asks"]) > 0:
            # first item in asks list is ALSO a list!
            assert type(response["asks"][0]) == list
            assert int(response["asks"][0][0]) >= 0, "zeroth item should be an int"
            assert float(response["asks"][0][1]) >= 0, "oneth item should be a float"
        if len(response["bids"]) > 0:
            # first item in bids list is ALSO a list!
            assert type(response["bids"][0]) == list
            assert int(response["bids"][0][0]) >= 0, "zeroth item should be an int"
            assert float(response["bids"][0][1]) >= 0, "oneth item should be a float"

    def test_public_trades(self, bitvavo: Bitvavo):
        response = bitvavo.publicTrades(symbol="BTC-EUR", options={})

        for public_trade in response:
            assert len(public_trade) == 5
            assert "id" in public_trade
            assert "timestamp" in public_trade
            assert "amount" in public_trade
            assert "price" in public_trade
            assert "side" in public_trade

        for public_trade in response:
            assert type(public_trade["id"]) == str
            assert type(public_trade["timestamp"]) == int
            assert type(public_trade["amount"]) == str
            assert type(public_trade["price"]) == str
            assert type(public_trade["side"]) == str

        for public_trade in response:
            # these are strings that can convert to another value
            assert float(public_trade["amount"]) >= 0
            assert float(public_trade["price"]) >= 0

    def test_candle(self, bitvavo: Bitvavo):
        """This is one of the weirder results: a list of lists"""
        # Timestamp: candle[0], open: candle[1], high: candle[2], low: candle[3], close: candle[4], volume: candle[5]
        response = bitvavo.candles(market="BTC-EUR", interval="1h", options={})
        for candle in response:
            assert len(candle) == 6
            assert type(candle) == list
            assert type(candle[0]) == int  # timestamp
            assert type(candle[1]) == str  # open
            assert type(candle[2]) == str  # high
            assert type(candle[3]) == str  # low
            assert type(candle[4]) == str  # close
            assert type(candle[5]) == str  # volume

        for candle in response:
            assert int(candle[1]) >= 0  # open
            assert int(candle[2]) >= 0  # high
            assert int(candle[3]) >= 0  # low
            assert int(candle[4]) >= 0  # close
            assert float(candle[5]) >= 0  # volume

    def test_ticker_price(self, bitvavo: Bitvavo):
        response = bitvavo.tickerPrice({})

        # assert keys
        for ticker_price in response:
            assert len(ticker_price) == 2
            assert "market" in ticker_price
            assert "price" in ticker_price

        # assert types
        for ticker_price in response:
            assert type(ticker_price["market"]) == str
            assert type(ticker_price["price"]) == str

        # convertable types
        for ticker_price in response:
            assert float(ticker_price["price"]) >= 0

    def test_ticker_book(self, bitvavo: Bitvavo):
        """
        Don't worry too much about the *-BTC markets, as they are not used (and thus not visible on the website)
        """
        response = bitvavo.tickerBook({})

        # assert keys
        for ticker_book in response:
            # All non *-BTC markets should have 5 keys
            if not ticker_book["market"].endswith("BTC"):
                assert len(ticker_book) == 5
                assert "market" in ticker_book
                assert "bid" in ticker_book
                assert "ask" in ticker_book
                assert "bidSize" in ticker_book
                assert "askSize" in ticker_book
            else:
                assert len(ticker_book) == 5 or len(ticker_book) == 4
                assert "market" in ticker_book
                assert "bid" in ticker_book
                assert "ask" in ticker_book
                assert "askSize" in ticker_book

        # assert types
        for ticker_book in response:
            if not ticker_book["market"].endswith("BTC"):
                assert type(ticker_book["market"]) == str
                assert type(ticker_book["bid"]) == str
                assert type(ticker_book["ask"]) == str
                assert type(ticker_book["bidSize"]) == str
                assert type(ticker_book["askSize"]) == str
            else:
                assert type(ticker_book["market"]) == str
                assert type(ticker_book["ask"]) == str
                assert type(ticker_book["askSize"]) == str

        # convertable types
        for ticker_book in response:
            if not ticker_book["market"].endswith("BTC"):
                assert float(ticker_book["bid"]) >= 0
                assert float(ticker_book["ask"]) >= 0
                assert float(ticker_book["bidSize"]) >= 0
                assert float(ticker_book["askSize"]) >= 0
            else:
                assert float(ticker_book["ask"]) >= 0
                assert float(ticker_book["askSize"]) >= 0

    def test_ticker_24h(self, bitvavo: Bitvavo):
        response = bitvavo.ticker24h({})

        for ticker_24h in response:
            assert len(ticker_24h) == 12
            assert "market" in ticker_24h
            assert "open" in ticker_24h
            assert "high" in ticker_24h
            assert "low" in ticker_24h
            assert "last" in ticker_24h
            assert "volume" in ticker_24h
            assert "volumeQuote" in ticker_24h
            assert "bid" in ticker_24h
            assert "bidSize" in ticker_24h
            assert "ask" in ticker_24h
            assert "askSize" in ticker_24h
            assert "timestamp" in ticker_24h

        for ticker_24h in response:
            if not ticker_24h["market"].endswith("BTC"):
                assert type(ticker_24h["market"]) == str
                assert type(ticker_24h["open"]) == str or ticker_24h["open"] is None
                assert type(ticker_24h["high"]) == str or ticker_24h["high"] is None
                assert type(ticker_24h["low"]) == str or ticker_24h["low"] is None
                assert type(ticker_24h["last"]) == str or ticker_24h["last"] is None
                assert type(ticker_24h["volume"]) == str or ticker_24h["volume"] is None
                assert type(ticker_24h["volumeQuote"]) == str or ticker_24h["volumeQuote"] is None
                assert type(ticker_24h["bid"]) == str
                assert type(ticker_24h["bidSize"]) == str
                assert type(ticker_24h["ask"]) == str
                assert type(ticker_24h["askSize"]) == str
                assert type(ticker_24h["timestamp"]) == int

        for ticker_24h in response:
            if not ticker_24h["market"].endswith("BTC"):
                assert float(ticker_24h["open"] if ticker_24h["open"] else 1) >= 0  # else 1, because 1 is truthy
                assert float(ticker_24h["high"] if ticker_24h["high"] else 1) >= 0
                assert float(ticker_24h["low"] if ticker_24h["low"] else 1) >= 0
                assert float(ticker_24h["last"] if ticker_24h["last"] else 1) >= 0
                assert float(ticker_24h["volume"] if ticker_24h["volume"] else 1) >= 0
                assert float(ticker_24h["volumeQuote"] if ticker_24h["volumeQuote"] else 1) >= 0
                assert float(ticker_24h["bid"]) >= 0
                assert float(ticker_24h["bidSize"]) >= 0
                assert float(ticker_24h["ask"]) >= 0
                assert float(ticker_24h["askSize"]) >= 0
                assert int(ticker_24h["timestamp"])

    @mark.skip(reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_place_order_buy(self, bitvavo: Bitvavo):
        response = bitvavo.placeOrder(
            market="BTC-EUR",
            side="buy",
            orderType="limit",
            body={"amount": "0.1", "price": "2000"},
        )
        print(json.dumps(response, indent=2))

    @mark.skip(reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_place_order_sell(self, bitvavo: Bitvavo):
        response = bitvavo.placeOrder(
            market="BTC-EUR",
            side="sell",
            orderType="stopLoss",
            body={"amount": "0.1", "triggerType": "price", "triggerReference": "lastTrade", "triggerAmount": "5000"},
        )
        print(json.dumps(response, indent=2))

    def test_get_order(self, bitvavo: Bitvavo):
        response = bitvavo.getOrder(market="BTC-EUR", orderId="dd055772-0f02-493c-a049-f4356fa0d221")
        assert len(response) == 2
        assert "error" in response
        assert "errorCode" in response
        long_str = "No order found. Please be aware that simultaneously updating the same order may return this error."
        assert response["error"] == long_str
        assert response["errorCode"] == 240

    def test_update_order(self, bitvavo: Bitvavo):
        response = bitvavo.updateOrder(
            market="BTC-EUR",
            orderId="dd055772-0f02-493c-a049-f4356fa0d221",
            body={"amount": "0.2"},
        )
        assert len(response) == 2
        assert "errorCode" in response
        assert "error" in response
        assert response["errorCode"] == 310
        assert response["error"] == "This key does not allow trading actions."

    def test_cancel_order(self, bitvavo: Bitvavo):
        response = bitvavo.cancelOrder(market="BTC-EUR", orderId="dd055772-0f02-493c-a049-f4356fa0d221")
        assert len(response) == 2
        assert "errorCode" in response
        assert "error" in response
        assert response["errorCode"] == 310
        assert response["error"] == "This key does not allow trading actions."

    def test_get_orders(self, bitvavo: Bitvavo):
        response = bitvavo.getOrders(market="BTC-EUR", options={})
        assert response == []  # at least it's not an error or something

    def test_cancel_orders(self, bitvavo: Bitvavo):
        response = bitvavo.cancelOrders({"market": "BTC-EUR"})
        assert "errorCode" in response
        assert "error" in response
        assert response["errorCode"] == 311
        assert response["error"] == "This key does not allowing showing account information."

    def test_orders_open(self, bitvavo: Bitvavo):
        response = bitvavo.ordersOpen({})
        for item in response:
            assert len(item) == 21
            assert "orderId" in item
            assert "market" in item
            assert "created" in item
            assert "updated" in item
            assert "status" in item
            assert "side" in item
            assert "orderType" in item
            assert "amount" in item
            assert "amountRemaining" in item
            assert "price" in item
            assert "onHold" in item
            assert "onHoldCurrency" in item
            assert "filledAmount" in item
            assert "filledAmountQuote" in item
            assert "feePaid" in item
            assert "feeCurrency" in item
            assert "fills" in item
            assert "selfTradePrevention" in item
            assert "visible" in item
            assert "timeInForce" in item
            assert "postOnly" in item

        for item in response:
            assert type(item["orderId"]) == str
            assert type(item["market"]) == str
            assert type(item["created"]) == int
            assert type(item["updated"]) == int
            assert type(item["status"]) == str
            assert type(item["side"]) == str
            assert type(item["orderType"]) == str
            assert type(item["amount"]) == str
            assert type(item["amountRemaining"]) == str
            assert type(item["price"]) == str
            assert type(item["onHold"]) == str
            assert type(item["onHoldCurrency"]) == str
            assert type(item["filledAmount"]) == str
            assert type(item["filledAmountQuote"]) == str
            assert type(item["feePaid"]) == str
            assert type(item["feeCurrency"]) == str
            assert type(item["fills"]) == list
            assert type(item["selfTradePrevention"]) == str
            assert type(item["visible"]) == bool
            assert type(item["timeInForce"]) == str
            assert type(item["postOnly"]) == bool

        for item in response:
            assert item["status"] in ["new"]
            assert item["side"] in ["sell", "buy"]
            assert item["orderType"] in ["limit"]
            assert float(item["amount"]) >= 0
            assert float(item["amountRemaining"]) >= 0
            assert float(item["price"]) >= 0
            assert float(item["onHold"]) >= 0
            assert float(item["filledAmount"]) >= 0
            assert float(item["filledAmountQuote"]) >= 0
            assert float(item["feePaid"]) >= 0
            assert item["selfTradePrevention"] in ["decrementAndCancel"]
            assert item["timeInForce"] in ["GTC"]

    def test_trades(self, bitvavo: Bitvavo):
        response = bitvavo.trades(market="BTC-EUR", options={})
        assert response == []

    def test_account(self, bitvavo: Bitvavo):
        response = bitvavo.account()

        assert len(response) == 1
        assert "fees" in response

        assert len(response["fees"]) == 3
        assert "taker" in response["fees"]
        assert "maker" in response["fees"]
        assert "volume" in response["fees"]
        assert float(response["fees"]["taker"]) >= 0
        assert float(response["fees"]["maker"]) >= 0
        assert float(response["fees"]["volume"]) >= 0

    def test_balance(self, bitvavo: Bitvavo):
        response = bitvavo.balance({})
        for item in response:
            assert len(item) == 3
            assert "symbol" in item
            assert "available" in item
            assert "inOrder" in item

        for item in response:
            assert type(item["symbol"]) == str
            assert type(item["available"]) == str
            assert type(item["inOrder"]) == str

        for item in response:
            assert float(item["available"]) >= 0
            assert float(item["inOrder"]) >= 0

    def test_deposit_assets(self, bitvavo: Bitvavo):
        """
        This function is currently broken - will fix after adding tests (and checking if they cover everything I
        need to cover
        """
        response = bitvavo.depositAssets("BTC")

        assert "address" in response
        assert type(response["address"]) == str

    def test_withdraw_assets(self, bitvavo: Bitvavo):
        response = bitvavo.withdrawAssets("BTC", "1", "BitcoinAddress", {})

        assert "errorCode" in response
        assert "error" in response

        assert response["errorCode"] == 312
        assert response["error"] == "This key does not allowing withdrawal of funds."

    def test_deposit_history(self, bitvavo: Bitvavo):
        response = bitvavo.depositHistory({})
        assert type(response) == list
        for item in response:
            assert "timestamp" in item
            assert "symbol" in item
            assert "amount" in item
            assert "fee" in item
            assert "status" in item
            assert "address" in item or "txId" in item

        for item in response:
            assert type(item["timestamp"]) == int
            assert type(item["symbol"]) == str
            assert type(item["amount"]) == str
            assert type(item["fee"]) == str
            assert type(item["status"]) == str
            if "address" in item:
                assert type(item["address"]) == str
            if "txId" in item:
                assert type(item["txId"]) == str

        for item in response:
            assert float(item["amount"]) >= 0
            assert float(item["fee"]) >= 0

    def test_withdrawal_history(self, bitvavo: Bitvavo):
        response = bitvavo.withdrawalHistory({})
        assert type(response) == list
        for item in response:
            assert "timestamp" in item
            assert "symbol" in item
            assert "amount" in item
            assert "address" in item
            assert "paymentId" in item
            assert "txId" in item
            assert "fee" in item
            assert "status" in item

        for item in response:
            assert type(item["timestamp"]) == int
            assert type(item["symbol"]) == str
            assert type(item["amount"]) == str
            assert type(item["address"]) == str
            assert type(item["paymentId"]) == str
            assert type(item["txId"]) == str
            assert type(item["fee"]) == str
            assert type(item["status"]) == str

        for item in response:
            assert float(item["amount"]) >= 0
            assert float(item["fee"]) >= 0
            assert item["status"] in ["awaiting_processing"]  # FIXME expand this list, if possible


# Normally you would define a seperate callback for every function.
def generic_callback(response):
    # print(f"generic_callback: {response=}")
    print(f"generic_callback: {json.dumps(response, indent=2)}")


class TestWebsocket:
    """
    Since this method has to take another Python Thread into account, we'll check output and such via caplog and capsys.
    I'll be honest: I have no idea when one or the other is used, so I included them both, in case I ever change some
    setting that is going to switch the outputs or something (right now, capsys is used most often).

    This is also due to experience in another project, where sometimes caplog, sometimes capsys and sometimes both were
    used, depending on the settings of the logger (structlog, in that case). I'm using the regular logging for now, for
    this project, to keep dependencies at a minimum.
    """

    def wait(self):
        """
        Helper method that you must run after making a websocket call.
        This method waits for some time in the hopes that the websocket is done within that time.
        If you do not have this waiting time, the logs won't print because those are created by a separate thread,
        which would not be able to actually print the logs, because the main thread will have done running.
        """
        # If all websocket tests fail, just up thisnumber
        sleep(1)

    def test_time(self, caplog, capsys, websocket: Bitvavo.websocket):
        try:
            websocket.time(generic_callback)
            self.wait()
            assert caplog.text == ""
            stdout, stderr = capsys.readouterr()
            assert 'generic_callback: {\n  "time":' in stdout
            assert stderr == ""
        except TypeError:
            assert False

    def test_markets(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.markets(options={"market": "BTC-EUR"}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "market": "BTC-EUR",\n  "status": "trading"' in stdout

    def test_assets(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.assets(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "symbol": "1INCH",\n    "name": "1inch"' in stdout

    def test_book(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.book(market="BTC-EUR", options={}, callback=generic_callback)
        self.wait()
        self.wait()  # slower function; needs a bit more time

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "market": "BTC-EUR",\n  "nonce":' in stdout

    def test_public_trades(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.publicTrades(market="BTC-EUR", options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "id": "' in stdout

    def test_candles(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.candles(market="BTC-EUR", interval="1h", options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert "generic_callback: [\n  [\n    " in stdout

    def test_ticker_24h(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.ticker24h(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "market": "1INCH-EUR",\n    "open":' in stdout

    def test_ticker_price(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.tickerPrice(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "market": "1INCH-EUR",\n    "price": ' in stdout

    def test_ticker_book(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.tickerBook(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "market": "1INCH-EUR",\n    "bid": ' in stdout

    @mark.skip(reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_place_order(self, caplog, capsys, websocket: Bitvavo.websocket):
        # FIXME? body?
        websocket.placeOrder(
            market="BTC-EUR",
            side="buy",
            orderType="limit",
            body={"amount": "1", "price": "3000"},
            callback=generic_callback,
        )

    def test_get_order(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.getOrder(market="BTC-EUR", orderId="6d0dffa7-07fe-448e-9928-233821e7cdb5", callback=generic_callback)
        self.wait()

        assert "'errorCode': 240" in caplog.text
        assert (
            "'error': 'No order found. Please be aware that simultaneously updating the same order may return this error.'"
            in caplog.text
        )
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert stdout == ""

    @mark.skip(reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_update_order(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.updateOrder(
            market="BTC-EUR",
            orderId="6d0dffa7-07fe-448e-9928-233821e7cdb5",
            body={"amount": "1.1"},
            callback=generic_callback,
        )

    @mark.skip(reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_cancel_order(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.cancelOrder(
            market="BTC-EUR",
            orderId="6d0dffa7-07fe-448e-9928-233821e7cdb5",
            callback=generic_callback,
        )

    def test_get_orders(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.getOrders(market="BTC-EUR", options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert "generic_callback: []\n" in stdout

    @mark.skip(reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_cancel_orders(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.cancelOrders({"market": "BTC-EUR"}, callback=generic_callback)

    def test_orders_open(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.ordersOpen(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "orderId": ' in stdout

    def test_trades(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.trades(market="BTC-EUR", options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert "generic_callback: []\n" in stdout

    def test_account(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.account(callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "fees": {\n    "taker": ' in stdout

    def test_balance(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.balance(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "symbol": ' in stdout

    @mark.skip(reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_deposit_assets(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.depositAssets("BTC", callback=generic_callback)

    @mark.skip(reason="I'm not touching methods where I can accidentally sell all my shit")
    def test_withdraw_assets(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.withdrawAssets(symbol="BTC", amount="1", address="BitcoinAddress", body={}, callback=generic_callback)

    def test_deposit_history(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.depositHistory(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: [\n  {\n    "timestamp": ' in stdout

    def test_withdrawal_history(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.withdrawalHistory(options={}, callback=generic_callback)
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert "generic_callback: []\n" in stdout

    @mark.skip(reason="It's really hard to test a method that may or may not return data")
    def test_subscription_ticker(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.subscriptionTicker(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "event": "ticker",\n  "market": "BTC-EUR",\n  "bestAsk": ' in stdout

    @mark.skip(reason="It's really hard to test a method that may or may not return data")
    def test_subscription_ticker_24h(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.subscriptionTicker24h(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "market": "BTC-EUR",\n  "open": "' in stdout

    @mark.skip(reason="It's really hard to test a method that may or may not return data")
    def test_subscription_ticker_account(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.subscriptionAccount(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert "" in stdout  # no output found manually ;_;

    @mark.skip(reason="It's really hard to test a method that may or may not return data")
    def test_subscription_ticker_candles(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.subscriptionCandles(market="BTC-EUR", interval="1h", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert (
            'generic_callback: {\n  "event": "candle",\n  "market": "BTC-EUR",\n  "interval": "1h",\n  "candle": [\n    [\n      '
            in stdout
        )

    @mark.skip(reason="It's really hard to test a method that may or may not return data")
    def test_subscription_trades(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.subscriptionTrades(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "event": "trade",\n  "timestamp": ' in stdout

    @mark.skip(reason="It's really hard to test a method that may or may not return data")
    def test_subscription_book_update(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.subscriptionBookUpdate(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "event": "book",\n  "market": "BTC-EUR",\n  "nonce": ' in stdout

    @mark.skip(reason="It's really hard to test a method that may or may not return data")
    def test_subscription_book(self, caplog, capsys, websocket: Bitvavo.websocket):
        websocket.subscriptionBook(market="BTC-EUR", callback=generic_callback)
        self.wait()
        self.wait()
        self.wait()

        assert caplog.text == ""
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert 'generic_callback: {\n  "bids": [\n    [\n      "' in stdout
