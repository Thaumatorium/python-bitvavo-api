import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from threading import Thread
from typing import Any, Callable, Dict, List, Union

import structlog
import websocket as ws_lib
from requests import delete, get, post, put
from websocket import WebSocketApp  # missing stubs for WebSocketApp

from bitvavo_api_upgraded.helper_funcs import configure_loggers, time_ms, time_to_wait
from bitvavo_api_upgraded.type_aliases import anydict, errordict, intdict, ms, s_f, strdict

configure_loggers()

logger = structlog.stdlib.get_logger("bitvavo-api-upgraded")


def createSignature(timestamp: ms, method: str, url: str, body: anydict, APISECRET: str) -> str:
    string = f"{timestamp}{method}/v2{url}"
    if len(body.keys()) != 0:
        string += json.dumps(body, separators=(",", ":"))
    signature = hmac.new(APISECRET.encode("utf-8"), string.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature


def createPostfix(options: anydict) -> str:
    """Generate a URL postfix, based on the `options` dict.

    ---
    Args:
        options (bvdict): [description]

    ---
    Returns:
        str: [description]
    """
    params = [f"{key}={options[key]}" for key in options]
    postfix = "&".join(params)  # intersperse
    return f"?{postfix}" if len(options) > 0 else postfix


def asksCompare(a: float, b: float) -> bool:
    return a < b


def bidsCompare(a: float, b: float) -> bool:
    return a > b


def sortAndInsert(
    asks_or_bids: List[List[str]],
    update: List[List[str]],
    compareFunc: Callable[[float, float], bool],
) -> Union[List[List[str]], errordict]:
    for updateEntry in update:
        entrySet: bool = False
        for j in range(len(asks_or_bids)):
            bookItem = asks_or_bids[j]
            if compareFunc(float(updateEntry[0]), float(bookItem[0])):
                asks_or_bids.insert(j, updateEntry)
                entrySet = True
                break
            if float(updateEntry[0]) == float(bookItem[0]):
                if float(updateEntry[1]) > 0.0:
                    asks_or_bids[j] = updateEntry
                    entrySet = True
                    break
                else:
                    asks_or_bids.pop(j)
                    entrySet = True
                    break
        if not entrySet:
            asks_or_bids.append(updateEntry)
    return asks_or_bids


def processLocalBook(ws: "Bitvavo.websocket", message: anydict) -> None:
    market: str = ""
    if "action" in message:
        if message["action"] == "getBook":
            market = message["response"]["market"]
            ws.localBook[market]["bids"] = message["response"]["bids"]
            ws.localBook[market]["asks"] = message["response"]["asks"]
            ws.localBook[market]["nonce"] = message["response"]["nonce"]
            ws.localBook[market]["market"] = market
    elif "event" in message:
        if message["event"] == "book":
            market = message["market"]

            if message["nonce"] != ws.localBook[market]["nonce"] + 1:
                # I think I've fixed this, by looking at the other Bitvavo repos (search for 'nonce' or '!=' 😆)
                ws.subscriptionBook(market, ws.callbacks[market])
                return
            ws.localBook[market]["bids"] = sortAndInsert(ws.localBook[market]["bids"], message["bids"], bidsCompare)
            ws.localBook[market]["asks"] = sortAndInsert(ws.localBook[market]["asks"], message["asks"], asksCompare)
            ws.localBook[market]["nonce"] = message["nonce"]

    if market != "":
        ws.callbacks["subscriptionBookUser"][market](ws.localBook[market])


class receiveThread(Thread):
    def __init__(self, ws: WebSocketApp, wsObject: "Bitvavo.websocket"):
        self.ws = ws
        self.wsObject = wsObject
        Thread.__init__(self)

    def run(self) -> None:
        try:
            while self.wsObject.keepAlive:
                self.ws.run_forever()
                self.wsObject.reconnect = True
                self.wsObject.authenticated = False
                time.sleep(self.wsObject.reconnectTimer)
                if self.wsObject.bitvavo.debugging:
                    logger.debug(
                        f"we have just set reconnect to true and have waited for {self.wsObject.reconnectTimer}"
                    )
                self.wsObject.reconnectTimer = self.wsObject.reconnectTimer * 2
        except KeyboardInterrupt:
            if self.wsObject.bitvavo.debugging:
                logger.debug("keyboard-interrupt")

    def stop(self) -> None:
        self.wsObject.keepAlive = False


def callback_example(response: Any) -> None:
    """
    You can use this example as a starting point, for the websocket code, IF you want to

    I  made this so you can see what kind of function you'll need to stick into the websocket functions.
    """
    if isinstance(response, Dict):
        # instead of printing, you could save the object to a file:
        import json
        from pathlib import Path

        HERE = Path.cwd()  # root of your project folder
        filepath = HERE / "your_output.json"
        # a = append; figure out yourself to create multiple callback functions, probably one for each type of call that you want to make
        with filepath.open("a") as file:
            file.write(json.dumps(response))
    elif isinstance(response, List):
        # Whether `item` is a list or a dict doesn't matter to print
        for item in response:
            print(item)
        # You can also copy-paste stuff to write it to a file or something
        # of maybe mess around with sqlite. ¯\_(ツ)_/¯
    else:
        # Normally, I would raise an exception here, but the websocket Thread would just eat it up anyway :/
        # I don't even know if this log will be shown to you.
        # Yes, I haven't tested this function; it's just some off-the-cuff example to get you started.
        logger.critical("what in the blazes did I just receive!?")


def error_callback_example(msg: errordict) -> None:
    """
    When using the websocket, I really REALLY recommend using `ws.setErrorCallback(error_callback_example)`, instead of
    using the default (yes, there is a default on_error function, but that just prints the error, which in practice
    means it won't show for the user, as the websocket has a tendency to silently fail printing).

    I would recommand adding some alerting mechanism, where the error isn't written to a log,
    but to some external system instead, like Discord, Slack, Email, Signal, Telegram, etc
    As I said, this is due to the websocket silently dropping python Exceptions and Bitvavo Errors.

    I can't speak for all options (yet), but the Discord one was VERY easy (mostly due to me already having a Discord channel :p)

    ```shell
    pip install discord-webhook
    ```

    Create a webhook for some channel (look for the cog icon) and copy it into a `DISCORD_WEBHOOK` variable

    ```python
    from discord_webhook import DiscordWebhook

    # send the message directly to your discord channel! :D
    DiscordWebhook(
        url=DISCORD_WEBHOOK,
        rate_limit_retry=True,
        content=f"{msg}",
    ).execute()
    ```
    """
    # easiest thing is to use the logger, but there's a good chance this message gets silently eaten.
    logger.error(msg)


class Bitvavo:
    def __init__(self, options: Dict[str, Union[str, int]] = {}):
        _options = {k.upper(): v for k, v in options.items()}
        self.base: str = str(_options.get("RESTURL", "https://api.bitvavo.com/v2"))
        self.wsUrl: str = str(_options.get("WSURL", "wss://ws.bitvavo.com/v2/"))
        self.ACCESSWINDOW = ms(_options.get("ACCESSWINDOW", 10000))
        self.APIKEY = str(_options.get("APIKEY", ""))
        self.APISECRET = str(_options.get("APISECRET", ""))
        self.rateLimitRemaining: int = 1000
        self.rateLimitResetAt: ms = 0
        self.debugging = bool(_options.get("DEBUGGING", False))
        self.lag = 0  # have to set it to 0, as it's ALSO used in calcLag 😅
        self.lag = self.calcLag()

    def calcLag(self) -> ms:
        """
        Calculate the time difference between the client and server; use this value when you make an api call,
        to precent 304 errors
        """
        lag_list = [
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
            self.time()["time"] - time_ms(),
        ]

        return ms(sum(lag_list) / len(lag_list))

    def getRemainingLimit(self) -> int:
        """Get the remaing rate limit

        ---
        Returns:
        ```python
        1000  # or lower
        ```
        """
        return self.rateLimitRemaining

    def updateRateLimit(self, response: Union[anydict, errordict]) -> None:
        """
        Update the rate limited

        If you're banned, use the errordict to sleep until you're not banned

        If you're not banned, then use the received headers to update the variables.
        """
        if "errorCode" in response:
            if response["errorCode"] == 105:
                self.rateLimitRemaining = 0
                # rateLimitResetAt is a value that's stripped from a string.
                # Kind of a terrible way to pass that information, but eh, whatever, I guess...
                # Anyway, here is the string that's being pulled apart:
                # "Your IP or API key has been banned for not respecting the rate limit. The ban expires at ${expiryInMs}""
                self.rateLimitResetAt = ms(response["error"].split(" at ")[1].split(".")[0])
                timeToWait = time_to_wait(self.rateLimitResetAt)
                if self.debugging:
                    logger.debug(
                        "banned",
                        info={
                            "wait_time_seconds": timeToWait + 1,
                            "until": (datetime.now() + timedelta(seconds=timeToWait + 1)).isoformat(),
                        },
                    )
                time.sleep(timeToWait + 1)  # plus one second to ENSURE we're able to run again.
        if "Bitvavo-Ratelimit-Remaining" in response:
            self.rateLimitRemaining = int(response["Bitvavo-Ratelimit-Remaining"])
        if "Bitvavo-Ratelimit-ResetAt" in response:
            self.rateLimitResetAt = int(response["Bitvavo-Ratelimit-ResetAt"])

    def publicRequest(self, url: str) -> Union[List[anydict], List[List[str]], intdict, strdict, anydict, errordict]:
        """Execute a request to the public part of the API; no API key and/or SECRET necessary.
        Will return the reponse as one of three types.

        ---
        Args:
        ```python
        url: str = "https://api.bitvavo.com/v2/time" # example of how the url looks like
        ```

        ---
        Returns:
        ```python
        # either of one:
        Dict[str, Any]
        List[Dict[str, Any]]
        List[List[str]]
        ```
        """
        if self.debugging:
            logger.debug(
                "api-request",
                info={
                    "url": url,
                    "with_api_key": bool(self.APIKEY != ""),
                    "public_or_private": "public",
                },
            )
        if self.APIKEY != "":
            now = time_ms() - self.lag
            sig = createSignature(now, "GET", url.replace(self.base, ""), {}, self.APISECRET)
            headers = {
                "Bitvavo-Access-Key": self.APIKEY,
                "Bitvavo-Access-Signature": sig,
                "Bitvavo-Access-Timestamp": str(now),
                "Bitvavo-Access-Window": str(self.ACCESSWINDOW),
            }
            r = get(url, headers=headers)
        else:
            r = get(url)
        if "error" in r.json():
            self.updateRateLimit(r.json())
        else:
            self.updateRateLimit(dict(r.headers))
        return r.json()  # type:ignore

    def privateRequest(
        self,
        endpoint: str,
        postfix: str,
        body: anydict,
        method: str = "GET",
    ) -> Union[List[anydict], List[List[str]], intdict, strdict, anydict, Any, errordict]:
        """Execute a request to the private  part of the API. API key and SECRET are required.
        Will return the reponse as one of three types.

        ---
        Args:
        # TODO(NostraDavid) fill these in
        ```python
        endpoint: str = "/order", "", body, )
        postfix: str = ""
        body: bvdict = body
        method: Optional[str] = "POST"  # Defaults to "GET"
        ```

        ---
        Returns:
        ```python
        # either of one:
        Dict[str, Any]
        List[Dict[str, Any]]
        List[List[str]]
        ```
        """
        # if this method breaks: add `= {}` after `body:Dict``
        now = time_ms() - self.lag
        sig = createSignature(now, method, (endpoint + postfix), body, self.APISECRET)
        url = self.base + endpoint + postfix
        headers = {
            "Bitvavo-Access-Key": self.APIKEY,
            "Bitvavo-Access-Signature": sig,
            "Bitvavo-Access-Timestamp": str(now),
            "Bitvavo-Access-Window": str(self.ACCESSWINDOW),
        }
        if self.debugging:
            logger.debug(
                "api-request",
                info={
                    "url": url,
                    "with_api_key": bool(self.APIKEY != ""),
                    "public_or_private": "private",
                    "method": method,
                },
            )
        if method == "DELETE":
            r = delete(url, headers=headers)
        elif method == "POST":
            r = post(url, headers=headers, json=body)
        elif method == "PUT":
            r = put(url, headers=headers, json=body)
        else:  # method == "GET"
            r = get(url, headers=headers)
        if "error" in r.json():
            self.updateRateLimit(r.json())
        else:
            self.updateRateLimit(dict(r.headers))
        return r.json()

    def time(self) -> intdict:
        """Get server-time, in milliseconds, since 1970-01-01

        ---
        Examples:
        * https://api.bitvavo.com/v2/time

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {"time": 1539180275424 }
        ```
        """
        return self.publicRequest(f"{self.base}/time")

    def markets(self, options: strdict) -> Union[List[anydict], anydict, errordict]:
        """Get all available markets with some meta-information, unless options is given a `market` key.
        Then you will get a single market, instead of a list of markets.

        ---
        Examples:
        * https://api.bitvavo.com/v2/markets
        * https://api.bitvavo.com/v2/markets?market=BTC-EUR
        * https://api.bitvavo.com/v2/markets?market=SHIB-EUR

        ---
        Args:
        ```python
        # Choose one:
        options={}  # returns all markets
        options={"market": "BTC-EUR"}  # returns only the BTC-EUR market
        # If you want multiple markets, but not all, make multiple calls
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        [
          {
            "market": "BTC-EUR",
            "status": "trading",
            "base": "BTC",
            "quote": "EUR",
            "pricePrecision": "5",
            "minOrderInQuoteAsset": "10",
            "minOrderInBaseAsset": "0.001",
            "orderTypes": [
            "market",
            "limit",
            "stopLoss",
            "stopLossLimit",
            "takeProfit",
            "takeProfitLimit"
            ]
          }
        ]
        ```
        """
        postfix = createPostfix(options)
        return self.publicRequest(f"{self.base}/markets{postfix}")

    def assets(self, options: strdict) -> Union[List[anydict], anydict]:
        """Get all available assets, unless `options` is given a `symbol` key.
        Then you will get a single asset, instead of a list of assets.

        ---
        Examples:
        * https://api.bitvavo.com/v2/assets
        * https://api.bitvavo.com/v2/assets?symbol=BTC
        * https://api.bitvavo.com/v2/assets?symbol=SHIB
        * https://api.bitvavo.com/v2/assets?symbol=ADA
        * https://api.bitvavo.com/v2/assets?symbol=EUR

        ---
        Args:
        ```python
        # pick one
        options={}  # returns all assets
        options={"symbol": "BTC"} # returns a single asset (the one of Bitcoin)
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        [
          {
            "symbol": "BTC",
            "name": "Bitcoin",
            "decimals": 8,
            "depositFee": "0",
            "depositConfirmations": 10,
            "depositStatus": "OK",
            "withdrawalFee": "0.2",
            "withdrawalMinAmount": "0.2",
            "withdrawalStatus": "OK",
            "networks": ["Mainnet"],
            "message": ""
          }
        ]
        ```
        """
        postfix = createPostfix(options)
        return self.publicRequest(f"{self.base}/assets{postfix}")

    def book(self, market: str, options: intdict) -> Union[Dict[str, Union[str, int, List[str]]], errordict]:
        """Get a book (with two lists: asks and bids, as they're called)

        ---
        Examples:
        * https://api.bitvavo.com/v2/BTC-EUR/book
        * https://api.bitvavo.com/v2/SHIB-EUR/book?depth=10
        * https://api.bitvavo.com/v2/ADA-EUR/book?depth=0

        ---
        Args:
        ```python
        market="ADA-EUR"
        options={"depth": 3}  # returns the best 3 asks and 3 bids
        options={}  # same as `{"depth": 0}`; returns all bids and asks for that book
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "market": "ADA-EUR",
          "nonce": 10378032,
          "bids": [["1.1908", "600"], ["1.1902", "4091.359809"], ["1.1898", "7563"]],
          "asks": [["1.1917", "2382.166997"], ["1.1919", "440.7"], ["1.192", "600"]],
        }

        # Notice how each bid and ask is also a list
        bid = ["1.1908", "600"]  # the first bid from the bids list
        price = bid[0] # the price for one coin/token
        size = bid[1]  # how many tokens are asked (or bidded, in this case)
        result = price * size
        assert result == 714.48  # EUR can be gained from this bid if it's sold (minus the fee)
        ```
        """
        postfix = createPostfix(options)
        return self.publicRequest(f"{self.base}/{market}/book{postfix}")

    def publicTrades(self, market: str, options: Dict[str, Union[str, int]]) -> Union[List[anydict], errordict]:
        """Publically available trades

        ---
        Examples:
        * https://api.bitvavo.com/v2/BTC-EUR/trades
        * https://api.bitvavo.com/v2/SHIB-EUR/trades?limit=10
        * https://api.bitvavo.com/v2/ADA-EUR/trades?tradeIdFrom=532f4d4d-f545-4a2d-a175-3d37919cb73c
        * https://api.bitvavo.com/v2/NANO-EUR/trades

        ---
        Args:
        ```python
        market="NANO-EUR"
        # note that any of these `options` are optional
        # use `int(time.time() * 1000)` to get current timestamp in milliseconds
        # or `int(datetime.datetime.now().timestamp()*1000)`
        options={
            "limit": [ 1 .. 1000 ], default 500
            "start": int timestamp in ms >= 0
            "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
            "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
            "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        [
          {
            "timestamp": 1542967486256,
            "id": "57b1159b-6bf5-4cde-9e2c-6bd6a5678baf",
            "amount": "0.1",
            "price": "5012",
            "side": "sell"
          }
        ]
        ```
        """
        postfix = createPostfix(options)
        return self.publicRequest(f"{self.base}/{market}/trades{postfix}")

    def candles(
        self,
        market: str,
        interval: str,
        options: Dict[str, Union[str, int]],
    ) -> Union[List[List[str]], errordict]:
        """Get up to 1440 candles for a market, with a specific interval (candle size)

        Extra reading material: https://en.wikipedia.org/wiki/Candlestick_chart

        ## WARNING: RETURN TYPE IS WEIRD - CHECK BOTTOM OF THIS TEXT FOR EXPLANATION

        ---
        Examples:
        * https://api.bitvavo.com/v2/BTC-EUR/candles?interval=1h&limit=100

        ---
        Args:
        ```python
        market="BTC-EUR"
        interval="1h"  # Choose: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d
        # use `int(time.time() * 1000)` to get current timestamp in milliseconds
        # or `int(datetime.datetime.now().timestamp()*1000)`
        options={
            "limit": [ 1 .. 1440 ], default 1440
            "start": int timestamp in ms >= 0
            "end": int timestamp in ms <= 8640000000000000
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        [
          # For whatever reason, you're getting a list of lists; no keys,
          # so here is the explanation of what's what.
          # timestamp,     open,    high,    low,     close,   volume
          [1640815200000, "41648", "41859", "41519", "41790", "12.1926685"],
          [1640811600000, "41771", "41780", "41462", "41650", "13.90917427"],
          [1640808000000, "41539", "42083", "41485", "41771", "14.39770267"],
          [1640804400000, "41937", "41955", "41449", "41540", "23.64498292"],
          [1640800800000, "41955", "42163", "41807", "41939", "10.40093845"],
        ]
        ```
        """
        options["interval"] = interval
        postfix = createPostfix(options)
        return self.publicRequest(f"{self.base}/{market}/candles{postfix}")

    def tickerPrice(self, options: strdict) -> Union[List[strdict], strdict]:
        """Get the current price for each market

        ---
        Examples:
        * https://api.bitvavo.com/v2/ticker/price
        * https://api.bitvavo.com/v2/ticker/price?market=BTC-EUR
        * https://api.bitvavo.com/v2/ticker/price?market=ADA-EUR
        * https://api.bitvavo.com/v2/ticker/price?market=SHIB-EUR
        * https://api.bitvavo.com/v2/ticker/price?market=DOGE-EUR
        * https://api.bitvavo.com/v2/ticker/price?market=NANO-EUR

        ---
        Args:
        ```python
        options={}
        options={"market": "BTC-EUR"}
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        # Note that `price` is unconverted
        [
          {"market": "1INCH-EUR", "price": "2.1594"},
          {"market": "AAVE-EUR", "price": "214.42"},
          {"market": "ADA-BTC", "price": "0.000021401"},
          {"market": "ADA-EUR", "price": "1.2011"},
          {"market": "ADX-EUR", "price": "0.50357"},
          {"market": "AE-BTC", "price": "0.0000031334"},
          {"market": "AE-EUR", "price": "0.064378"},
          {"market": "AION-BTC", "price": "0.000004433"},
          {"market": "AION-EUR", "price": "0.1258"},
          {"market": "AKRO-EUR", "price": "0.020562"},
          {"market": "ALGO-EUR", "price": "1.3942"},
          # and another 210 markets below this point
        ]
        ```
        """
        postfix = createPostfix(options)
        return self.publicRequest(f"{self.base}/ticker/price{postfix}")

    def tickerBook(self, options: strdict) -> Union[List[strdict], strdict]:
        """Get current bid/ask, bidsize/asksize per market

        ---
        Examples:
        * https://api.bitvavo.com/v2/ticker/book
        * https://api.bitvavo.com/v2/ticker/book?market=BTC-EUR
        * https://api.bitvavo.com/v2/ticker/book?market=ADA-EUR
        * https://api.bitvavo.com/v2/ticker/book?market=SHIB-EUR
        * https://api.bitvavo.com/v2/ticker/book?market=DOGE-EUR
        * https://api.bitvavo.com/v2/ticker/book?market=NANO-EUR

        ---
        Args:
        ```python
        options={}
        options={"market": "BTC-EUR"}
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        [
          {"market": "1INCH-EUR", "bid": "2.1534", "ask": "2.1587", "bidSize": "194.8", "askSize": "194.8"},
          {"market": "AAVE-EUR", "bid": "213.7", "ask": "214.05", "bidSize": "212.532", "askSize": "4.77676965"},
          {"market": "ADA-EUR", "bid": "1.2", "ask": "1.2014", "bidSize": "415.627597", "askSize": "600"},
          {"market": "ADX-EUR", "bid": "0.49896", "ask": "0.50076", "bidSize": "1262.38216882", "askSize": "700.1"},
          {"market": "AION-EUR", "bid": "0.12531", "ask": "0.12578", "bidSize": "3345", "askSize": "10958.49228653"},
          # and another 215 markets below this point
        ]
        ```
        """
        postfix = createPostfix(options)
        return self.publicRequest(f"{self.base}/ticker/book{postfix}")

    def ticker24h(self, options: strdict) -> Union[List[anydict], anydict, errordict]:
        """Get current bid/ask, bidsize/asksize per market

        ---
        Examples:
        * https://api.bitvavo.com/v2/ticker/24h
        * https://api.bitvavo.com/v2/ticker/24h?market=BTC-EUR
        * https://api.bitvavo.com/v2/ticker/24h?market=ADA-EUR
        * https://api.bitvavo.com/v2/ticker/24h?market=SHIB-EUR
        * https://api.bitvavo.com/v2/ticker/24h?market=DOGE-EUR
        * https://api.bitvavo.com/v2/ticker/24h?market=NANO-EUR

        ---
        Args:
        ```python
        options={}
        options={"market": "BTC-EUR"}
        ```

        ---
        Rate Limit Weight:
        ```python
        25  # if no market option is used
        1  # if a market option is used
        ```

        ---
        Returns:
        ```python
        [
          {
            "market": "1INCH-EUR",
            "open": "2.2722",
            "high": "2.2967",
            "low": "2.1258",
            "last": "2.1552",
            "volume": "92921.3792573",
            "volumeQuote": "204118.95",
            "bid": "2.1481",
            "bidSize": "392.46514457",
            "ask": "2.1513",
            "askSize": "195.3",
            "timestamp": 1640819573777
          },
          {
            "market": "AAVE-EUR",
            "open": "224.91",
            "high": "228.89",
            "low": "210.78",
            "last": "213.83",
            "volume": "5970.52391148",
            "volumeQuote": "1307777.47",
            "bid": "213.41",
            "bidSize": "2.61115011",
            "ask": "213.85",
            "askSize": "1.864",
            "timestamp": 1640819573285
          },
          # and then 219 more markets
        ]
        ```
        """
        postfix = createPostfix(options)
        return self.publicRequest(f"{self.base}/ticker/24h{postfix}")

    def placeOrder(self, market: str, side: str, orderType: str, body: anydict) -> anydict:
        """Place a new order on the exchange

        ---
        Args:
        ```python
        market="SHIB-EUR"
        side="buy" # Choose: buy, sell
        # For market orders either `amount` or `amountQuote` is required
        orderType="market"  # Choose: market, limit, stopLoss, stopLossLimit, takeProfit, takeProfitLimit
        body={
          "amount": "1.567",
          "amountQuote": "5000",
          # GTC orders will remain on the order book until they are filled or canceled.
          # IOC orders will fill against existing orders, but will cancel any remaining amount after that.
          # FOK orders will fill against existing orders in its entirety, or will be canceled (if the entire order cannot be filled).
          "timeInForce": "GTC",  # Choose: GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
          # 'decrementAndCancel' decrements both orders by the amount that would have been filled, which in turn cancels the smallest of the two orders.
          # 'cancelOldest' will cancel the entire older order and places the new order.
          # 'cancelNewest' will cancel the order that is submitted.
          # 'cancelBoth' will cancel both the current and the old order.
          "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
          "disableMarketProtection": false,
          "responseRequired": true  # setting this to `false` will return only an 'acknowledged', and be faster
        }

        # For limit orders `amount` and `price` are required.
        orderType="limit"  # Choose: market, limit, stopLoss, stopLossLimit, takeProfit, takeProfitLimit
        body={
          "amount": "1.567",
          "price": "6000",
          "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
          "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
          "postOnly": false,  # Only for limit orders
          "responseRequired": True
        }

        orderType="stopLoss"
        # or
        orderType="takeProfit"
        body={
          "amount": "1.567",
          "amountQuote": "5000",
          "triggerAmount": "4000",
          "triggerType": "price",
          "triggerReference": "lastTrade",
          "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
          "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
          "disableMarketProtection": false,
          "responseRequired": true
        }

        orderType="stopLossLimit"
        # or
        orderType="takeProfitLimit"
        body={
          "amount": "1.567",
          "price": "6000",
          "triggerAmount": "4000",
          "triggerType": "price",
          "triggerReference": "lastTrade",
          "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
          "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
          "postOnly": false,  # Only for limit orders
          "responseRequired": true
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
          "market": "BTC-EUR",
          "created": 1542621155181,
          "updated": 1542621155181,
          "status": "new",
          "side": "buy",
          "orderType": "limit",
          "amount": "10",
          "amountRemaining": "10",
          "price": "7000",
          "amountQuote": "5000",
          "amountQuoteRemaining": "5000",
          "onHold": "9109.61",
          "onHoldCurrency": "BTC",
          "triggerPrice": "4000",
          "triggerAmount": "4000",
          "triggerType": "price",
          "triggerReference": "lastTrade",
          "filledAmount": "0",
          "filledAmountQuote": "0",
          "feePaid": "0",
          "feeCurrency": "EUR",
          "fills": [
            {
              "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
              "timestamp": 1542967486256,
              "amount": "0.005",
              "price": "5000.1",
              "taker": true,
              "fee": "0.03",
              "feeCurrency": "EUR",
              "settled": true
            }
          ],
          "selfTradePrevention": "decrementAndCancel",
          "visible": true,
          "timeInForce": "GTC",
          "postOnly": false,
          "disableMarketProtection": true
        }
        ```
        """
        body["market"] = market
        body["side"] = side
        body["orderType"] = orderType
        return self.privateRequest("/order", "", body, "POST")

    def updateOrder(self, market: str, orderId: str, body: anydict) -> anydict:
        """Update an existing order for a specific market. Make sure that at least one of the optional parameters is set,
        otherwise nothing will be updated.

        ---
        Args:
        ```python
        market="BTC-EUR"
        orderId="95d92d6c-ecf0-4960-a608-9953ef71652e"
        body={
          "amount": "1.567",
          "amountRemaining": "1.567",
          "price": "6000",
          "triggerAmount": "4000",  # only for stop orders
          # GTC orders will remain on the order book until they are filled or canceled.
          # IOC orders will fill against existing orders, but will cancel any remaining amount after that.
          # FOK orders will fill against existing orders in its entirety, or will be canceled (if the entire order cannot be filled).
          "timeInForce": "GTC",  # Choose: GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
          # 'decrementAndCancel' decrements both orders by the amount that would have been filled, which in turn cancels the smallest of the two orders.
          # 'cancelOldest' will cancel the entire older order and places the new order.
          # 'cancelNewest' will cancel the order that is submitted.
          # 'cancelBoth' will cancel both the current and the old order.
          "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
          "postOnly": false,  # Only for limit orders
          "responseRequired": true  # setting this to `false` will return only an 'acknowledged', and be faster
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
          "market": "BTC-EUR",
          "created": 1542621155181,
          "updated": 1542621155181,
          "status": "new",
          "side": "buy",
          "orderType": "limit",
          "amount": "10",
          "amountRemaining": "10",
          "price": "7000",
          "amountQuote": "5000",
          "amountQuoteRemaining": "5000",
          "onHold": "9109.61",
          "onHoldCurrency": "BTC",
          "triggerPrice": "4000",
          "triggerAmount": "4000",
          "triggerType": "price",
          "triggerReference": "lastTrade",
          "filledAmount": "0",
          "filledAmountQuote": "0",
          "feePaid": "0",
          "feeCurrency": "EUR",
          "fills": [
            {
              "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
              "timestamp": 1542967486256,
              "amount": "0.005",
              "price": "5000.1",
              "taker": true,
              "fee": "0.03",
              "feeCurrency": "EUR",
              "settled": true
            }
          ],
          "selfTradePrevention": "decrementAndCancel",
          "visible": true,
          "timeInForce": "GTC",
          "postOnly": true,
          "disableMarketProtection": true
        }
        ```
        """
        body["market"] = market
        body["orderId"] = orderId
        return self.privateRequest("/order", "", body, "PUT")

    def cancelOrder(self, market: str, orderId: str) -> strdict:
        """Cancel an existing order for a specific market

        ---
        Args:
        ```python
        market="BTC-EUR"
        orderId="a4a5d310-687c-486e-a3eb-1df832405ccd"
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {"orderId": "2e7ce7fc-44e2-4d80-a4a7-d079c4750b61"}
        ```
        """
        postfix = createPostfix({"market": market, "orderId": orderId})
        return self.privateRequest("/order", postfix, {}, "DELETE")

    def getOrder(self, market: str, orderId: str) -> Union[List[anydict], errordict]:
        """Get an existing order for a specific market

        ---
        Args:
        ```python
        market="BTC-EUR"
        orderId="ff403e21-e270-4584-bc9e-9c4b18461465"
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
          "market": "BTC-EUR",
          "created": 1542621155181,
          "updated": 1542621155181,
          "status": "new",
          "side": "buy",
          "orderType": "limit",
          "amount": "10",
          "amountRemaining": "10",
          "price": "7000",
          "amountQuote": "5000",
          "amountQuoteRemaining": "5000",
          "onHold": "9109.61",
          "onHoldCurrency": "BTC",
          "triggerPrice": "4000",
          "triggerAmount": "4000",
          "triggerType": "price",
          "triggerReference": "lastTrade",
          "filledAmount": "0",
          "filledAmountQuote": "0",
          "feePaid": "0",
          "feeCurrency": "EUR",
          "fills": [
            {
              "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
              "timestamp": 1542967486256,
              "amount": "0.005",
              "price": "5000.1",
              "taker": true,
              "fee": "0.03",
              "feeCurrency": "EUR",
              "settled": true
            }
          ],
          "selfTradePrevention": "decrementAndCancel",
          "visible": true,
          "timeInForce": "GTC",
          "postOnly": true,
          "disableMarketProtection": true
        }
        ```
        """
        postfix = createPostfix({"market": market, "orderId": orderId})
        return self.privateRequest("/order", postfix, {}, "GET")

    def getOrders(self, market: str, options: anydict) -> Union[List[anydict], errordict]:
        """Get multiple existing orders for a specific market

        ---
        Args:
        ```python
        market="BTC-EUR"
        options={
            "limit": [ 1 .. 1000 ], default 500
            "start": int timestamp in ms >= 0
            "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
            "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
            "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        # A whole list of these
        [
          {
            "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
            "market": "BTC-EUR",
            "created": 1542621155181,
            "updated": 1542621155181,
            "status": "new",
            "side": "buy",
            "orderType": "limit",
            "amount": "10",
            "amountRemaining": "10",
            "price": "7000",
            "amountQuote": "5000",
            "amountQuoteRemaining": "5000",
            "onHold": "9109.61",
            "onHoldCurrency": "BTC",
            "triggerPrice": "4000",
            "triggerAmount": "4000",
            "triggerType": "price",
            "triggerReference": "lastTrade",
            "filledAmount": "0",
            "filledAmountQuote": "0",
            "feePaid": "0",
            "feeCurrency": "EUR",
            "fills": [
              {
                "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                "timestamp": 1542967486256,
                "amount": "0.005",
                "price": "5000.1",
                "taker": true,
                "fee": "0.03",
                "feeCurrency": "EUR",
                "settled": true
              }
            ],
            "selfTradePrevention": "decrementAndCancel",
            "visible": true,
            "timeInForce": "GTC",
            "postOnly": true,
            "disableMarketProtection": true
          }
        ]
        ```
        """
        options["market"] = market
        postfix = createPostfix(options)
        return self.privateRequest("/orders", postfix, {}, "GET")

    def cancelOrders(self, options: anydict) -> Union[List[strdict], errordict]:
        """Cancel all existing orders for a specific market (or account)

        ---
        Args:
        ```python
        options={} # WARNING - WILL REMOVE ALL OPEN ORDERS ON YOUR ACCOUNT!
        options={"market":"BTC-EUR"}  # Removes all open orders for this market
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        # A whole list of these
        [
          {"orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6"}
        ]
        ```
        """
        postfix = createPostfix(options)
        return self.privateRequest("/orders", postfix, {}, "DELETE")

    def ordersOpen(self, options: anydict) -> Union[List[anydict], errordict]:
        """Get all open orders, either for all markets, or a single market

        ---
        Args:
        ```python
        options={} # Gets all open orders for all markets
        options={"market":"BTC-EUR"}  # Get open orders for this market
        ```

        ---
        Rate Limit Weight:
        ```python
        25  # if no market option is used
        1  # if a market option is used
        ```

        ---
        Returns:
        ```python
        [
          {
            "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
            "market": "BTC-EUR",
            "created": 1542621155181,
            "updated": 1542621155181,
            "status": "new",
            "side": "buy",
            "orderType": "limit",
            "amount": "10",
            "amountRemaining": "10",
            "price": "7000",
            "amountQuote": "5000",
            "amountQuoteRemaining": "5000",
            "onHold": "9109.61",
            "onHoldCurrency": "BTC",
            "triggerPrice": "4000",
            "triggerAmount": "4000",
            "triggerType": "price",
            "triggerReference": "lastTrade",
            "filledAmount": "0",
            "filledAmountQuote": "0",
            "feePaid": "0",
            "feeCurrency": "EUR",
            "fills": [
              {
                "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                "timestamp": 1542967486256,
                "amount": "0.005",
                "price": "5000.1",
                "taker": true,
                "fee": "0.03",
                "feeCurrency": "EUR",
                "settled": true
              }
            ],
            "selfTradePrevention": "decrementAndCancel",
            "visible": true,
            "timeInForce": "GTC",
            "postOnly": true,
            "disableMarketProtection": true
          }
        ]
        ```
        """
        postfix = createPostfix(options)
        return self.privateRequest("/ordersOpen", postfix, {}, "GET")

    def trades(self, market: str, options: anydict) -> Union[List[anydict], errordict]:
        """Get all historic trades from this account

        ---
        Args:
        ```python
        market="BTC-EUR"
        options={
            "limit": [ 1 .. 1000 ], default 500
            "start": int timestamp in ms >= 0
            "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
            "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
            "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        [
          {
            "id": "108c3633-0276-4480-a902-17a01829deae",
            "orderId": "1d671998-3d44-4df4-965f-0d48bd129a1b",
            "timestamp": 1542967486256,
            "market": "BTC-EUR",
            "side": "buy",
            "amount": "0.005",
            "price": "5000.1",
            "taker": true,
            "fee": "0.03",
            "feeCurrency": "EUR",
            "settled": true
          }
        ]
        ```
        """
        options["market"] = market
        postfix = createPostfix(options)
        return self.privateRequest("/trades", postfix, {}, "GET")

    def account(self) -> Dict[str, strdict]:
        """Get all fees for this account

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "fees": {
            "taker": "0.0025",
            "maker": "0.0015",
            "volume": "10000.00"
          }
        }
        ```
        """
        return self.privateRequest("/account", "", {}, "GET")

    def balance(self, options: strdict) -> Union[List[strdict], errordict]:
        """Get the balance for this account

        ---
        Args:
        ```python
        options={}  # return all balances
        options={symbol="BTC"} # return a single balance
        ```

        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        [
          {
            "symbol": "BTC",
            "available": "1.57593193",
            "inOrder": "0.74832374"
          }
        ]
        ```
        """
        postfix = createPostfix(options)
        return self.privateRequest("/balance", postfix, {}, "GET")

    def depositAssets(self, symbol: str) -> strdict:
        """Get the deposit address (with paymentId for some assets) or bank account information to increase your balance

        ---
        Args:
        ```python
        symbol="BTC"
        symbol="SHIB"
        symbol="EUR"
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "address": "CryptoCurrencyAddress",
          "paymentId": "10002653"
        }
        # or
        {
          "iban": "NL32BUNQ2291234129",
          "bic": "BUNQNL2A",
          "description": "254D20CC94"
        }
        ```
        """
        postfix = createPostfix({"symbol": symbol})
        return self.privateRequest("/deposit", postfix, {}, "GET")

    def depositHistory(self, options: anydict) -> Union[List[anydict], errordict]:
        """Get the deposit history of the account

        Even when you want something from a single `symbol`, you'll still receive a list with multiple deposits.

        ---
        Args:
        ```python
        options={
            "symbol":"EUR"
            "limit": [ 1 .. 1000 ], default 500
            "start": int timestamp in ms >= 0
            "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        [
          {
            "timestamp": 1542967486256,
            "symbol": "BTC",
            "amount": "0.99994",
            "address": "BitcoinAddress",
            "paymentId": "10002653",
            "txId": "927b3ea50c5bb52c6854152d305dfa1e27fc01d10464cf10825d96d69d235eb3",
            "fee": "0"
          }
        ]
        # or
        [
          {
            "timestamp": 1542967486256,
            "symbol": "BTC",
            "amount": "500",
            "address": "NL32BITV0001234567",
            "fee": "0"
          }
        ]
        ```
        """
        postfix = createPostfix(options)
        return self.privateRequest("/depositHistory", postfix, {}, "GET")

    def withdrawAssets(self, symbol: str, amount: str, address: str, body: anydict) -> anydict:
        """Withdraw a coin/token to an external crypto address or bank account.

        ---
        Args:
        ```python
        symbol="SHIB"
        amount=10
        address="BitcoinAddress",  # Wallet address or IBAN
        options={
          "paymentId": "10002653",  # For digital assets only. Should be set when withdrawing straight to another exchange or merchants that require payment id's.
          "internal": false,  # For digital assets only. Should be set to true if the withdrawal must be sent to another Bitvavo user internally
          "addWithdrawalFee": false  # If set to true, the fee will be added on top of the requested amount, otherwise the fee is part of the requested amount and subtracted from the withdrawal.
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        1
        ```

        ---
        Returns:
        ```python
        {
          "success": true,
          "symbol": "BTC",
          "amount": "1.5"
        }
        ```
        """
        body["symbol"] = symbol
        body["amount"] = amount
        body["address"] = address
        return self.privateRequest("/withdrawal", "", body, "POST")

    def withdrawalHistory(self, options: anydict) -> Union[List[anydict], anydict]:
        """Get the withdrawal history

        ---
        Args:
        ```python
        options={
            "symbol":"SHIB"
            "limit": [ 1 .. 1000 ], default 500
            "start": int timestamp in ms >= 0
            "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
        }
        ```

        ---
        Rate Limit Weight:
        ```python
        5
        ```

        ---
        Returns:
        ```python
        [
          {
            "timestamp": 1542967486256,
            "symbol": "BTC",
            "amount": "0.99994",
            "address": "BitcoinAddress",
            "paymentId": "10002653",
            "txId": "927b3ea50c5bb52c6854152d305dfa1e27fc01d10464cf10825d96d69d235eb3",
            "fee": "0.00006",
            "status": "awaiting_processing"
          }
        }
        ```
        """
        postfix = createPostfix(options)
        return self.privateRequest("/withdrawalHistory", postfix, {}, "GET")

    def newWebsocket(self) -> "Bitvavo.websocket":
        return Bitvavo.websocket(self.APIKEY, self.APISECRET, self.ACCESSWINDOW, self.wsUrl, self)

    class websocket:
        def __init__(self, APIKEY: str, APISECRET: str, ACCESSWINDOW: int, WSURL: str, bitvavo: "Bitvavo"):
            self.APIKEY = APIKEY
            self.APISECRET = APISECRET
            self.ACCESSWINDOW = ACCESSWINDOW
            self.wsUrl = WSURL
            self.open = False
            self.callbacks: anydict = {}
            self.keepAlive = True
            self.reconnect = False
            self.reconnectTimer: s_f = 0.1
            self.bitvavo = bitvavo

            self.subscribe()

        def subscribe(self) -> None:
            ws_lib.enableTrace(False)
            ws = WebSocketApp(
                self.wsUrl,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
            )
            self.ws = ws
            ws.on_open = self.on_open

            self.receiveThread = receiveThread(ws, self)
            self.receiveThread.daemon = True
            self.receiveThread.start()

            self.authenticated = False
            self.keepBookCopy = False
            self.localBook: anydict = {}

        def closeSocket(self) -> None:
            self.ws.close()
            self.keepAlive = False
            self.receiveThread.join()

        def waitForSocket(self, ws: WebSocketApp, message: str, private: bool) -> None:
            if (not private and self.open) or (private and self.authenticated and self.open):
                return
            else:
                time.sleep(0.1)
                self.waitForSocket(ws, message, private)

        def doSend(self, ws: WebSocketApp, message: str, private: bool = False) -> None:
            if private and self.APIKEY == "":
                logger.error("no-apikey", tip="set the API key to be able to make private API calls")
                return
            self.waitForSocket(ws, message, private)
            ws.send(message)
            if self.bitvavo.debugging:
                logger.debug("message-sent", message=message)

        def on_message(self, ws: WebSocketApp, msg: str) -> None:  # noqa: C901 (too-complex)
            if self.bitvavo.debugging:
                logger.debug("message-received", message=msg)
            msg_dict: anydict = json.loads(msg)
            callbacks = self.callbacks

            if "error" in msg_dict:
                if msg_dict["errorCode"] == 105:
                    self.bitvavo.updateRateLimit(msg_dict)
                if "error" in callbacks:
                    callbacks["error"](msg_dict)
                else:
                    logger.error(msg_dict)

            if "action" in msg_dict:
                if msg_dict["action"] == "getTime":
                    callbacks["time"](msg_dict["response"])
                elif msg_dict["action"] == "getMarkets":
                    callbacks["markets"](msg_dict["response"])
                elif msg_dict["action"] == "getAssets":
                    callbacks["assets"](msg_dict["response"])
                elif msg_dict["action"] == "getTrades":
                    callbacks["publicTrades"](msg_dict["response"])
                elif msg_dict["action"] == "getCandles":
                    callbacks["candles"](msg_dict["response"])
                elif msg_dict["action"] == "getTicker24h":
                    callbacks["ticker24h"](msg_dict["response"])
                elif msg_dict["action"] == "getTickerPrice":
                    callbacks["tickerPrice"](msg_dict["response"])
                elif msg_dict["action"] == "getTickerBook":
                    callbacks["tickerBook"](msg_dict["response"])
                elif msg_dict["action"] == "privateCreateOrder":
                    callbacks["placeOrder"](msg_dict["response"])
                elif msg_dict["action"] == "privateUpdateOrder":
                    callbacks["updateOrder"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetOrder":
                    callbacks["getOrder"](msg_dict["response"])
                elif msg_dict["action"] == "privateCancelOrder":
                    callbacks["cancelOrder"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetOrders":
                    callbacks["getOrders"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetOrdersOpen":
                    callbacks["ordersOpen"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetTrades":
                    callbacks["trades"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetAccount":
                    callbacks["account"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetBalance":
                    callbacks["balance"](msg_dict["response"])
                elif msg_dict["action"] == "privateDepositAssets":
                    callbacks["depositAssets"](msg_dict["response"])
                elif msg_dict["action"] == "privateWithdrawAssets":
                    callbacks["withdrawAssets"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetDepositHistory":
                    callbacks["depositHistory"](msg_dict["response"])
                elif msg_dict["action"] == "privateGetWithdrawalHistory":
                    callbacks["withdrawalHistory"](msg_dict["response"])
                elif msg_dict["action"] == "privateCancelOrders":
                    callbacks["cancelOrders"](msg_dict["response"])
                elif msg_dict["action"] == "getBook":
                    market = msg_dict["response"]["market"]
                    if "book" in callbacks:
                        callbacks["book"](msg_dict["response"])
                    if self.keepBookCopy:
                        if market in callbacks["subscriptionBook"]:
                            callbacks["subscriptionBook"][market](self, msg_dict)

            elif "event" in msg_dict:
                if msg_dict["event"] == "authenticate":
                    self.authenticated = True
                elif msg_dict["event"] == "fill":
                    market = msg_dict["market"]
                    callbacks["subscriptionAccount"][market](msg_dict)
                elif msg_dict["event"] == "order":
                    market = msg_dict["market"]
                    callbacks["subscriptionAccount"][market](msg_dict)
                elif msg_dict["event"] == "ticker":
                    market = msg_dict["market"]
                    callbacks["subscriptionTicker"][market](msg_dict)
                elif msg_dict["event"] == "ticker24h":
                    for entry in msg_dict["data"]:
                        callbacks["subscriptionTicker24h"][entry["market"]](entry)
                elif msg_dict["event"] == "candle":
                    market = msg_dict["market"]
                    interval = msg_dict["interval"]
                    callbacks["subscriptionCandles"][market][interval](msg_dict)
                elif msg_dict["event"] == "book":
                    market = msg_dict["market"]
                    if "subscriptionBookUpdate" in callbacks:
                        if market in callbacks["subscriptionBookUpdate"]:
                            callbacks["subscriptionBookUpdate"][market](msg_dict)
                    if self.keepBookCopy:
                        if market in callbacks["subscriptionBook"]:
                            callbacks["subscriptionBook"][market](self, msg_dict)
                elif msg_dict["event"] == "trade":
                    market = msg_dict["market"]
                    if "subscriptionTrades" in callbacks:
                        callbacks["subscriptionTrades"][market](msg_dict)

        def on_error(self, ws: WebSocketApp, error: Any):
            if "error" in self.callbacks:
                self.callbacks["error"](error)
            else:
                logger.error(error)

        def on_close(self, ws: WebSocketApp):
            self.receiveThread.stop()
            if self.bitvavo.debugging:
                logger.debug("websocket-closed")

        def checkReconnect(self) -> None:  # noqa: C901 (too-complex)
            if "subscriptionTicker" in self.callbacks:
                for market in self.callbacks["subscriptionTicker"]:
                    self.subscriptionTicker(market, self.callbacks["subscriptionTicker"][market])
            if "subscriptionTicker24h" in self.callbacks:
                for market in self.callbacks["subscriptionTicker24h"]:
                    self.subscriptionTicker(market, self.callbacks["subscriptionTicker24h"][market])
            if "subscriptionAccount" in self.callbacks:
                for market in self.callbacks["subscriptionAccount"]:
                    self.subscriptionAccount(market, self.callbacks["subscriptionAccount"][market])
            if "subscriptionCandles" in self.callbacks:
                for market in self.callbacks["subscriptionCandles"]:
                    for interval in self.callbacks["subscriptionCandles"][market]:
                        self.subscriptionCandles(
                            market,
                            interval,
                            self.callbacks["subscriptionCandles"][market][interval],
                        )
            if "subscriptionTrades" in self.callbacks:
                for market in self.callbacks["subscriptionTrades"]:
                    self.subscriptionTrades(market, self.callbacks["subscriptionTrades"][market])
            if "subscriptionBookUpdate" in self.callbacks:
                for market in self.callbacks["subscriptionBookUpdate"]:
                    self.subscriptionBookUpdate(market, self.callbacks["subscriptionBookUpdate"][market])
            if "subscriptionBookUser" in self.callbacks:
                for market in self.callbacks["subscriptionBookUser"]:
                    self.subscriptionBook(market, self.callbacks["subscriptionBookUser"][market])

        def on_open(self, ws: WebSocketApp):
            now = time_ms() - self.bitvavo.lag
            self.open = True
            self.reconnectTimer = 0.5
            if self.APIKEY != "":
                self.doSend(
                    self.ws,
                    json.dumps(
                        {
                            "window": str(self.ACCESSWINDOW),
                            "action": "authenticate",
                            "key": self.APIKEY,
                            "signature": createSignature(now, "GET", "/websocket", {}, self.APISECRET),
                            "timestamp": now,
                        },
                    ),
                )
            if self.reconnect:
                if self.bitvavo.debugging:
                    logger.debug("reconnecting")
                thread = Thread(target=self.checkReconnect)
                thread.start()

        def setErrorCallback(self, callback: Callable[[Any], None]) -> None:
            self.callbacks["error"] = callback

        def time(self, callback: Callable[[Any], None]) -> None:
            """Get server-time, in milliseconds, since 1970-01-01

            ---
            Non-websocket examples:
            * https://api.bitvavo.com/v2/time

            ---
            Args:
            ```python
            callback=callback_example
            ```
            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {"time": 1539180275424 }
            ```
            """
            self.callbacks["time"] = callback
            self.doSend(self.ws, json.dumps({"action": "getTime"}))

        def markets(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get all available markets with some meta-information, unless options is given a `market` key.
            Then you will get a single market, instead of a list of markets.

            ---
            Examples:
            * https://api.bitvavo.com/v2/markets
            * https://api.bitvavo.com/v2/markets?market=BTC-EUR
            * https://api.bitvavo.com/v2/markets?market=SHIB-EUR

            ---
            Args:
            ```python
            # Choose one:
            options={}  # returns all markets
            options={"market": "BTC-EUR"}  # returns only the BTC-EUR market
            # If you want multiple markets, but not all, make multiple calls
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "market": "BTC-EUR",
                "status": "trading",
                "base": "BTC",
                "quote": "EUR",
                "pricePrecision": "5",
                "minOrderInQuoteAsset": "10",
                "minOrderInBaseAsset": "0.001",
                "orderTypes": [
                "market",
                "limit",
                "stopLoss",
                "stopLossLimit",
                "takeProfit",
                "takeProfitLimit"
                ]
              }
            ]
            ```
            """
            self.callbacks["markets"] = callback
            options["action"] = "getMarkets"
            self.doSend(self.ws, json.dumps(options))

        def assets(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get all available assets, unless `options` is given a `symbol` key.
            Then you will get a single asset, instead of a list of assets.

            ---
            Examples:
            * https://api.bitvavo.com/v2/assets
            * https://api.bitvavo.com/v2/assets?symbol=BTC
            * https://api.bitvavo.com/v2/assets?symbol=SHIB
            * https://api.bitvavo.com/v2/assets?symbol=ADA
            * https://api.bitvavo.com/v2/assets?symbol=EUR

            ---
            Args:
            ```python
            # pick one
            options={}  # returns all assets
            options={"symbol": "BTC"} # returns a single asset (the one of Bitcoin)
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "symbol": "BTC",
                "name": "Bitcoin",
                "decimals": 8,
                "depositFee": "0",
                "depositConfirmations": 10,
                "depositStatus": "OK",
                "withdrawalFee": "0.2",
                "withdrawalMinAmount": "0.2",
                "withdrawalStatus": "OK",
                "networks": ["Mainnet"],
                "message": ""
              }
            ]
            ```
            """
            self.callbacks["assets"] = callback
            options["action"] = "getAssets"
            self.doSend(self.ws, json.dumps(options))

        def book(self, market: str, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get a book (with two lists: asks and bids, as they're called)

            ---
            Examples:
            * https://api.bitvavo.com/v2/BTC-EUR/book
            * https://api.bitvavo.com/v2/SHIB-EUR/book?depth=10
            * https://api.bitvavo.com/v2/ADA-EUR/book?depth=0

            ---
            Args:
            ```python
            market="ADA-EUR"
            options={"depth": 3}  # returns the best 3 asks and 3 bids
            options={}  # same as `{"depth": 0}`; returns all bids and asks for that book
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
                "market": "ADA-EUR",
                "nonce": 10378032,
                "bids": [["1.1908", "600"], ["1.1902", "4091.359809"], ["1.1898", "7563"]],
                "asks": [["1.1917", "2382.166997"], ["1.1919", "440.7"], ["1.192", "600"]],
            }

            # Notice how each bid and ask is also a list
            bid = ["1.1908", "600"]  # the first bid from the bids list
            price = bid[0] # the price for one coin/token
            size = bid[1]  # how many tokens are asked (or bidded, in this case)
            result = price * size
            assert result == 714.48  # EUR can be gained from this bid if it's sold (minus the fee)
            ```
            """
            self.callbacks["book"] = callback
            options["market"] = market
            options["action"] = "getBook"
            self.doSend(self.ws, json.dumps(options))

        def publicTrades(self, market: str, options: anydict, callback: Callable[[Any], None]) -> None:
            """Publically available trades

            ---
            Examples:
            * https://api.bitvavo.com/v2/BTC-EUR/trades
            * https://api.bitvavo.com/v2/SHIB-EUR/trades?limit=10
            * https://api.bitvavo.com/v2/ADA-EUR/trades?tradeIdFrom=532f4d4d-f545-4a2d-a175-3d37919cb73c
            * https://api.bitvavo.com/v2/NANO-EUR/trades

            ---
            Args:
            ```python
            market="NANO-EUR"
            # note that any of these `options` are optional
            # use `int(time.time() * 1000)` to get current timestamp in milliseconds
            # or `int(datetime.datetime.now().timestamp()*1000)`
            options={
                "limit": [ 1 .. 1000 ], default 500
                "start": int timestamp in ms >= 0
                "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
                "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
                "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "timestamp": 1542967486256,
                "id": "57b1159b-6bf5-4cde-9e2c-6bd6a5678baf",
                "amount": "0.1",
                "price": "5012",
                "side": "sell"
              }
            ]
            ```
            """
            self.callbacks["publicTrades"] = callback
            options["market"] = market
            options["action"] = "getTrades"
            self.doSend(self.ws, json.dumps(options))

        def candles(self, market: str, interval: str, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get up to 1440 candles for a market, with a specific interval (candle size)

            Extra reading material: https://en.wikipedia.org/wiki/Candlestick_chart

            ## WARNING: RETURN TYPE IS WEIRD - CHECK BOTTOM OF THIS TEXT FOR EXPLANATION

            ---
            Examples:
            * https://api.bitvavo.com/v2/BTC-EUR/candles?interval=1h&limit=100

            ---
            Args:
            ```python
            market="BTC-EUR"
            interval="1h"  # Choose: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d
            # use `int(time.time() * 1000)` to get current timestamp in milliseconds
            # or `int(datetime.datetime.now().timestamp()*1000)`
            options={
                "limit": [ 1 .. 1440 ], default 1440
                "start": int timestamp in ms >= 0
                "end": int timestamp in ms <= 8640000000000000
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            [
                # For whatever reason, you're getting a list of lists; no keys,
                # so here is the explanation of what's what.
                # timestamp,     open,    high,    low,     close,   volume
                [1640815200000, "41648", "41859", "41519", "41790", "12.1926685"],
                [1640811600000, "41771", "41780", "41462", "41650", "13.90917427"],
                [1640808000000, "41539", "42083", "41485", "41771", "14.39770267"],
                [1640804400000, "41937", "41955", "41449", "41540", "23.64498292"],
                [1640800800000, "41955", "42163", "41807", "41939", "10.40093845"],
            ]
            ```
            """
            self.callbacks["candles"] = callback
            options["market"] = market
            options["interval"] = interval
            options["action"] = "getCandles"
            self.doSend(self.ws, json.dumps(options))

        def tickerPrice(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get the current price for each market

            ---
            Examples:
            * https://api.bitvavo.com/v2/ticker/price
            * https://api.bitvavo.com/v2/ticker/price?market=BTC-EUR
            * https://api.bitvavo.com/v2/ticker/price?market=ADA-EUR
            * https://api.bitvavo.com/v2/ticker/price?market=SHIB-EUR
            * https://api.bitvavo.com/v2/ticker/price?market=DOGE-EUR
            * https://api.bitvavo.com/v2/ticker/price?market=NANO-EUR

            ---
            Args:
            ```python
            options={}
            options={"market": "BTC-EUR"}
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            # Note that `price` is unconverted
            [
                {"market": "1INCH-EUR", "price": "2.1594"},
                {"market": "AAVE-EUR", "price": "214.42"},
                {"market": "ADA-BTC", "price": "0.000021401"},
                {"market": "ADA-EUR", "price": "1.2011"},
                {"market": "ADX-EUR", "price": "0.50357"},
                {"market": "AE-BTC", "price": "0.0000031334"},
                {"market": "AE-EUR", "price": "0.064378"},
                {"market": "AION-BTC", "price": "0.000004433"},
                {"market": "AION-EUR", "price": "0.1258"},
                {"market": "AKRO-EUR", "price": "0.020562"},
                {"market": "ALGO-EUR", "price": "1.3942"},
                # and another 210 markets below this point
            ]
            ```
            """
            self.callbacks["tickerPrice"] = callback
            options["action"] = "getTickerPrice"
            self.doSend(self.ws, json.dumps(options))

        def tickerBook(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get current bid/ask, bidsize/asksize per market

            ---
            Examples:
            * https://api.bitvavo.com/v2/ticker/book
            * https://api.bitvavo.com/v2/ticker/book?market=BTC-EUR
            * https://api.bitvavo.com/v2/ticker/book?market=ADA-EUR
            * https://api.bitvavo.com/v2/ticker/book?market=SHIB-EUR
            * https://api.bitvavo.com/v2/ticker/book?market=DOGE-EUR
            * https://api.bitvavo.com/v2/ticker/book?market=NANO-EUR

            ---
            Args:
            ```python
            options={}
            options={"market": "BTC-EUR"}
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            [
                {"market": "1INCH-EUR", "bid": "2.1534", "ask": "2.1587", "bidSize": "194.8", "askSize": "194.8"},
                {"market": "AAVE-EUR", "bid": "213.7", "ask": "214.05", "bidSize": "212.532", "askSize": "4.77676965"},
                {"market": "ADA-EUR", "bid": "1.2", "ask": "1.2014", "bidSize": "415.627597", "askSize": "600"},
                {"market": "ADX-EUR", "bid": "0.49896", "ask": "0.50076", "bidSize": "1262.38216882", "askSize": "700.1"},
                {"market": "AION-EUR", "bid": "0.12531", "ask": "0.12578", "bidSize": "3345", "askSize": "10958.49228653"},
                # and another 215 markets below this point
            ]
            ```
            """
            self.callbacks["tickerBook"] = callback
            options["action"] = "getTickerBook"
            self.doSend(self.ws, json.dumps(options))

        def ticker24h(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get current bid/ask, bidsize/asksize per market

            ---
            Examples:
            * https://api.bitvavo.com/v2/ticker/24h
            * https://api.bitvavo.com/v2/ticker/24h?market=BTC-EUR
            * https://api.bitvavo.com/v2/ticker/24h?market=ADA-EUR
            * https://api.bitvavo.com/v2/ticker/24h?market=SHIB-EUR
            * https://api.bitvavo.com/v2/ticker/24h?market=DOGE-EUR
            * https://api.bitvavo.com/v2/ticker/24h?market=NANO-EUR

            ---
            Args:
            ```python
            options={}
            options={"market": "BTC-EUR"}
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            25  # if no market option is used
            1  # if a market option is used
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "market": "1INCH-EUR",
                "open": "2.2722",
                "high": "2.2967",
                "low": "2.1258",
                "last": "2.1552",
                "volume": "92921.3792573",
                "volumeQuote": "204118.95",
                "bid": "2.1481",
                "bidSize": "392.46514457",
                "ask": "2.1513",
                "askSize": "195.3",
                "timestamp": 1640819573777
              },
              {
                "market": "AAVE-EUR",
                "open": "224.91",
                "high": "228.89",
                "low": "210.78",
                "last": "213.83",
                "volume": "5970.52391148",
                "volumeQuote": "1307777.47",
                "bid": "213.41",
                "bidSize": "2.61115011",
                "ask": "213.85",
                "askSize": "1.864",
                "timestamp": 1640819573285
              },
              # and then 219 more markets
            ]
            ```
            """
            self.callbacks["ticker24h"] = callback
            options["action"] = "getTicker24h"
            self.doSend(self.ws, json.dumps(options))

        def placeOrder(
            self,
            market: str,
            side: str,
            orderType: str,
            body: anydict,
            callback: Callable[[Any], None],
        ) -> None:
            """Place a new order on the exchange

            ---
            Args:
            ```python
            market="SHIB-EUR"
            side="buy" # Choose: buy, sell
            # For market orders either `amount` or `amountQuote` is required
            orderType="market"  # Choose: market, limit, stopLoss, stopLossLimit, takeProfit, takeProfitLimit
            body={
              "amount": "1.567",
              "amountQuote": "5000",
              # GTC orders will remain on the order book until they are filled or canceled.
              # IOC orders will fill against existing orders, but will cancel any remaining amount after that.
              # FOK orders will fill against existing orders in its entirety, or will be canceled (if the entire order cannot be filled).
              "timeInForce": "GTC",  # Choose: GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
              # 'decrementAndCancel' decrements both orders by the amount that would have been filled, which in turn cancels the smallest of the two orders.
              # 'cancelOldest' will cancel the entire older order and places the new order.
              # 'cancelNewest' will cancel the order that is submitted.
              # 'cancelBoth' will cancel both the current and the old order.
              "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
              "disableMarketProtection": false,
              "responseRequired": true  # setting this to `false` will return only an 'acknowledged', and be faster
            }

            # For limit orders `amount` and `price` are required.
            orderType="limit"  # Choose: market, limit, stopLoss, stopLossLimit, takeProfit, takeProfitLimit
            body={
              "amount": "1.567",
              "price": "6000",
              "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
              "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
              "postOnly": false,  # Only for limit orders
              "responseRequired": True
            }

            orderType="stopLoss"
            # or
            orderType="takeProfit"
            body={
              "amount": "1.567",
              "amountQuote": "5000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
              "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
              "disableMarketProtection": false,
              "responseRequired": true
            }

            orderType="stopLossLimit"
            # or
            orderType="takeProfitLimit"
            body={
              "amount": "1.567",
              "price": "6000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "timeInForce": "GTC",  # GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
              "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
              "postOnly": false,  # Only for limit orders
              "responseRequired": true
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
              "market": "BTC-EUR",
              "created": 1542621155181,
              "updated": 1542621155181,
              "status": "new",
              "side": "buy",
              "orderType": "limit",
              "amount": "10",
              "amountRemaining": "10",
              "price": "7000",
              "amountQuote": "5000",
              "amountQuoteRemaining": "5000",
              "onHold": "9109.61",
              "onHoldCurrency": "BTC",
              "triggerPrice": "4000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "filledAmount": "0",
              "filledAmountQuote": "0",
              "feePaid": "0",
              "feeCurrency": "EUR",
              "fills": [
                {
                  "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                  "timestamp": 1542967486256,
                  "amount": "0.005",
                  "price": "5000.1",
                  "taker": true,
                  "fee": "0.03",
                  "feeCurrency": "EUR",
                  "settled": true
                }
              ],
              "selfTradePrevention": "decrementAndCancel",
              "visible": true,
              "timeInForce": "GTC",
              "postOnly": false,
              "disableMarketProtection": true
            }
            ```
            """
            self.callbacks["placeOrder"] = callback
            body["market"] = market
            body["side"] = side
            body["orderType"] = orderType
            body["action"] = "privateCreateOrder"
            self.doSend(self.ws, json.dumps(body), True)

        def updateOrder(self, market: str, orderId: str, body: anydict, callback: Callable[[Any], None]) -> None:
            """Update an existing order for a specific market. Make sure that at least one of the optional parameters is set,
            otherwise nothing will be updated.

            ---
            Args:
            ```python
            market="BTC-EUR"
            orderId="95d92d6c-ecf0-4960-a608-9953ef71652e"
            body={
              "amount": "1.567",
              "amountRemaining": "1.567",
              "price": "6000",
              "triggerAmount": "4000",  # only for stop orders
              # GTC orders will remain on the order book until they are filled or canceled.
              # IOC orders will fill against existing orders, but will cancel any remaining amount after that.
              # FOK orders will fill against existing orders in its entirety, or will be canceled (if the entire order cannot be filled).
              "timeInForce": "GTC",  # Choose: GTC, IOC, FOK. Good-Til-Canceled (GTC), Immediate-Or-Cancel (IOC), Fill-Or-Kill (FOK)
              # 'decrementAndCancel' decrements both orders by the amount that would have been filled, which in turn cancels the smallest of the two orders.
              # 'cancelOldest' will cancel the entire older order and places the new order.
              # 'cancelNewest' will cancel the order that is submitted.
              # 'cancelBoth' will cancel both the current and the old order.
              "selfTradePrevention": "decrementAndCancel",  # decrementAndCancel, cancelOldest, cancelNewest, cancelBoth
              "postOnly": false,  # Only for limit orders
              "responseRequired": true  # setting this to `false` will return only an 'acknowledged', and be faster
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
              "market": "BTC-EUR",
              "created": 1542621155181,
              "updated": 1542621155181,
              "status": "new",
              "side": "buy",
              "orderType": "limit",
              "amount": "10",
              "amountRemaining": "10",
              "price": "7000",
              "amountQuote": "5000",
              "amountQuoteRemaining": "5000",
              "onHold": "9109.61",
              "onHoldCurrency": "BTC",
              "triggerPrice": "4000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "filledAmount": "0",
              "filledAmountQuote": "0",
              "feePaid": "0",
              "feeCurrency": "EUR",
              "fills": [
                {
                  "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                  "timestamp": 1542967486256,
                  "amount": "0.005",
                  "price": "5000.1",
                  "taker": true,
                  "fee": "0.03",
                  "feeCurrency": "EUR",
                  "settled": true
                }
              ],
              "selfTradePrevention": "decrementAndCancel",
              "visible": true,
              "timeInForce": "GTC",
              "postOnly": true,
              "disableMarketProtection": true
            }
            ```
            """
            self.callbacks["updateOrder"] = callback
            body["market"] = market
            body["orderId"] = orderId
            body["action"] = "privateUpdateOrder"
            self.doSend(self.ws, json.dumps(body), True)

        def cancelOrder(self, market: str, orderId: str, callback: Callable[[Any], None]) -> None:
            """Cancel an existing order for a specific market

            ---
            Args:
            ```python
            market="BTC-EUR"
            orderId="a4a5d310-687c-486e-a3eb-1df832405ccd"
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {"orderId": "2e7ce7fc-44e2-4d80-a4a7-d079c4750b61"}
            ```
            """
            self.callbacks["cancelOrder"] = callback
            options = {
                "action": "privateCancelOrder",
                "market": market,
                "orderId": orderId,
            }
            self.doSend(self.ws, json.dumps(options), True)

        def getOrder(self, market: str, orderId: str, callback: Callable[[Any], None]) -> None:
            """Get an existing order for a specific market

            ---
            Args:
            ```python
            market="BTC-EUR"
            orderId="ff403e21-e270-4584-bc9e-9c4b18461465"
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
              "market": "BTC-EUR",
              "created": 1542621155181,
              "updated": 1542621155181,
              "status": "new",
              "side": "buy",
              "orderType": "limit",
              "amount": "10",
              "amountRemaining": "10",
              "price": "7000",
              "amountQuote": "5000",
              "amountQuoteRemaining": "5000",
              "onHold": "9109.61",
              "onHoldCurrency": "BTC",
              "triggerPrice": "4000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "filledAmount": "0",
              "filledAmountQuote": "0",
              "feePaid": "0",
              "feeCurrency": "EUR",
              "fills": [
                {
                  "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                  "timestamp": 1542967486256,
                  "amount": "0.005",
                  "price": "5000.1",
                  "taker": true,
                  "fee": "0.03",
                  "feeCurrency": "EUR",
                  "settled": true
                }
              ],
              "selfTradePrevention": "decrementAndCancel",
              "visible": true,
              "timeInForce": "GTC",
              "postOnly": true,
              "disableMarketProtection": true
            }
            ```
            """
            self.callbacks["getOrder"] = callback
            options = {
                "action": "privateGetOrder",
                "market": market,
                "orderId": orderId,
            }
            self.doSend(self.ws, json.dumps(options), True)

        def getOrders(self, market: str, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get multiple existing orders for a specific market

            ---
            Args:
            ```python
            market="BTC-EUR"
            options={
                "limit": [ 1 .. 1000 ], default 500
                "start": int timestamp in ms >= 0
                "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
                "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
                "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            # A whole list of these
            [
              {
                "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
                "market": "BTC-EUR",
                "created": 1542621155181,
                "updated": 1542621155181,
                "status": "new",
                "side": "buy",
                "orderType": "limit",
                "amount": "10",
                "amountRemaining": "10",
                "price": "7000",
                "amountQuote": "5000",
                "amountQuoteRemaining": "5000",
                "onHold": "9109.61",
                "onHoldCurrency": "BTC",
                "triggerPrice": "4000",
                "triggerAmount": "4000",
                "triggerType": "price",
                "triggerReference": "lastTrade",
                "filledAmount": "0",
                "filledAmountQuote": "0",
                "feePaid": "0",
                "feeCurrency": "EUR",
                "fills": [
                  {
                    "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                    "timestamp": 1542967486256,
                    "amount": "0.005",
                    "price": "5000.1",
                    "taker": true,
                    "fee": "0.03",
                    "feeCurrency": "EUR",
                    "settled": true
                  }
                ],
                "selfTradePrevention": "decrementAndCancel",
                "visible": true,
                "timeInForce": "GTC",
                "postOnly": true,
                "disableMarketProtection": true
              }
            ]
            ```
            """
            self.callbacks["getOrders"] = callback
            options["action"] = "privateGetOrders"
            options["market"] = market
            self.doSend(self.ws, json.dumps(options), True)

        def cancelOrders(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Cancel all existing orders for a specific market (or account)

            ---
            Args:
            ```python
            options={} # WARNING - WILL REMOVE ALL OPEN ORDERS ON YOUR ACCOUNT!
            options={"market":"BTC-EUR"}  # Removes all open orders for this market
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            # A whole list of these
            [
              {"orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6"}
            ]
            ```
            """
            self.callbacks["cancelOrders"] = callback
            options["action"] = "privateCancelOrders"
            self.doSend(self.ws, json.dumps(options), True)

        def ordersOpen(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get all open orders, either for all markets, or a single market

            ---
            Args:
            ```python
            options={} # Gets all open orders for all markets
            options={"market":"BTC-EUR"}  # Get open orders for this market
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            25  # if no market option is used
            1  # if a market option is used
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "orderId": "1be6d0df-d5dc-4b53-a250-3376f3b393e6",
                "market": "BTC-EUR",
                "created": 1542621155181,
                "updated": 1542621155181,
                "status": "new",
                "side": "buy",
                "orderType": "limit",
                "amount": "10",
                "amountRemaining": "10",
                "price": "7000",
                "amountQuote": "5000",
                "amountQuoteRemaining": "5000",
                "onHold": "9109.61",
                "onHoldCurrency": "BTC",
                "triggerPrice": "4000",
                "triggerAmount": "4000",
                "triggerType": "price",
                "triggerReference": "lastTrade",
                "filledAmount": "0",
                "filledAmountQuote": "0",
                "feePaid": "0",
                "feeCurrency": "EUR",
                "fills": [
                  {
                    "id": "371c6bd3-d06d-4573-9f15-18697cd210e5",
                    "timestamp": 1542967486256,
                    "amount": "0.005",
                    "price": "5000.1",
                    "taker": true,
                    "fee": "0.03",
                    "feeCurrency": "EUR",
                    "settled": true
                  }
                ],
                "selfTradePrevention": "decrementAndCancel",
                "visible": true,
                "timeInForce": "GTC",
                "postOnly": true,
                "disableMarketProtection": true
              }
            ]
            ```
            """
            self.callbacks["ordersOpen"] = callback
            options["action"] = "privateGetOrdersOpen"
            self.doSend(self.ws, json.dumps(options), True)

        def trades(self, market: str, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get all historic trades from this account

            ---
            Args:
            ```python
            market="BTC-EUR"
            options={
                "limit": [ 1 .. 1000 ], default 500
                "start": int timestamp in ms >= 0
                "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
                "tradeIdFrom": ""  # if you get a list and want everything AFTER a certain id, put that id here
                "tradeIdTo": ""  # if you get a list and want everything BEFORE a certain id, put that id here
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "id": "108c3633-0276-4480-a902-17a01829deae",
                "orderId": "1d671998-3d44-4df4-965f-0d48bd129a1b",
                "timestamp": 1542967486256,
                "market": "BTC-EUR",
                "side": "buy",
                "amount": "0.005",
                "price": "5000.1",
                "taker": true,
                "fee": "0.03",
                "feeCurrency": "EUR",
                "settled": true
              }
            ]
            ```
            """
            self.callbacks["trades"] = callback
            options["action"] = "privateGetTrades"
            options["market"] = market
            self.doSend(self.ws, json.dumps(options), True)

        def account(self, callback: Callable[[Any], None]) -> None:
            """Get all fees for this account

            ---
            Args:
            ```python
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "fees": {
                "taker": "0.0025",
                "maker": "0.0015",
                "volume": "10000.00"
              }
            }
            ```
            """
            self.callbacks["account"] = callback
            self.doSend(self.ws, json.dumps({"action": "privateGetAccount"}), True)

        def balance(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get the balance for this account

            ---
            Args:
            ```python
            options={}  # return all balances
            options={symbol="BTC"} # return a single balance
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "symbol": "BTC",
                "available": "1.57593193",
                "inOrder": "0.74832374"
              }
            ]
            ```
            """
            options["action"] = "privateGetBalance"
            self.callbacks["balance"] = callback
            self.doSend(self.ws, json.dumps(options), True)

        def depositAssets(self, symbol: str, callback: Callable[[Any], None]) -> None:
            """Get the deposit address (with paymentId for some assets) or bank account information to increase your balance

            ---
            Args:
            ```python
            symbol="BTC"
            symbol="SHIB"
            symbol="EUR"
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "address": "CryptoCurrencyAddress",
              "paymentId": "10002653"
            }
            # or
            {
              "iban": "NL32BUNQ2291234129",
              "bic": "BUNQNL2A",
              "description": "254D20CC94"
            }
            ```
            """
            self.callbacks["depositAssets"] = callback
            self.doSend(
                self.ws,
                json.dumps({"action": "privateDepositAssets", "symbol": symbol}),
                True,
            )

        def depositHistory(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get the deposit history of the account

            Even when you want something from a single `symbol`, you'll still receive a list with multiple deposits.

            ---
            Args:
            ```python
            options={
                "symbol":"EUR"
                "limit": [ 1 .. 1000 ], default 500
                "start": int timestamp in ms >= 0
                "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "timestamp": 1542967486256,
                "symbol": "BTC",
                "amount": "0.99994",
                "address": "BitcoinAddress",
                "paymentId": "10002653",
                "txId": "927b3ea50c5bb52c6854152d305dfa1e27fc01d10464cf10825d96d69d235eb3",
                "fee": "0"
              }
            ]
            # or
            [
              {
                "timestamp": 1542967486256,
                "symbol": "BTC",
                "amount": "500",
                "address": "NL32BITV0001234567",
                "fee": "0"
              }
            ]
            ```
            """
            self.callbacks["depositHistory"] = callback
            options["action"] = "privateGetDepositHistory"
            self.doSend(self.ws, json.dumps(options), True)

        def withdrawAssets(
            self,
            symbol: str,
            amount: str,
            address: str,
            body: anydict,
            callback: Callable[[Any], None],
        ) -> None:
            """Withdraw a coin/token to an external crypto address or bank account.

            ---
            Args:
            ```python
            symbol="SHIB"
            amount=10
            address="BitcoinAddress",  # Wallet address or IBAN
            options={
              "paymentId": "10002653",  # For digital assets only. Should be set when withdrawing straight to another exchange or merchants that require payment id's.
              "internal": false,  # For digital assets only. Should be set to true if the withdrawal must be sent to another Bitvavo user internally
              "addWithdrawalFee": false  # If set to true, the fee will be added on top of the requested amount, otherwise the fee is part of the requested amount and subtracted from the withdrawal.
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            1
            ```

            ---
            Returns this to `callback`:
            ```python
            {
              "success": true,
              "symbol": "BTC",
              "amount": "1.5"
            }
            ```
            """
            self.callbacks["withdrawAssets"] = callback
            body["action"] = "privateWithdrawAssets"
            body["symbol"] = symbol
            body["amount"] = amount
            body["address"] = address
            self.doSend(self.ws, json.dumps(body), True)

        def withdrawalHistory(self, options: anydict, callback: Callable[[Any], None]) -> None:
            """Get the withdrawal history

            ---
            Args:
            ```python
            options={
                "symbol":"SHIB"
                "limit": [ 1 .. 1000 ], default 500
                "start": int timestamp in ms >= 0
                "end": int timestamp in ms <= 8_640_000_000_000_000 # (that's somewhere in the year 2243, or near the number 2^52)
            }
            callback=callback_example
            ```

            ---
            Rate Limit Weight:
            ```python
            5
            ```

            ---
            Returns this to `callback`:
            ```python
            [
              {
                "timestamp": 1542967486256,
                "symbol": "BTC",
                "amount": "0.99994",
                "address": "BitcoinAddress",
                "paymentId": "10002653",
                "txId": "927b3ea50c5bb52c6854152d305dfa1e27fc01d10464cf10825d96d69d235eb3",
                "fee": "0.00006",
                "status": "awaiting_processing"
              }
            }
            ```
            """
            self.callbacks["withdrawalHistory"] = callback
            options["action"] = "privateGetWithdrawalHistory"
            self.doSend(self.ws, json.dumps(options), True)

        def subscriptionTicker(self, market: str, callback: Callable[[Any], None]) -> None:
            # TODO(NostraDavid) one possible improvement here is to turn `market` into a list of markets, so we can sub to all of them at once. Same goes for other `subscription*()`
            """Subscribe to the ticker channel, which means `callback` gets passed the new best bid or ask whenever they change (server-side).


            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "ticker": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that:
            {
              "event": "ticker",
              "market": "BTC-EUR",
              "bestBid": "9156.8",
              "bestBidSize": "0.12840531",
              "bestAsk": "9157.9",
              "bestAskSize": "0.1286605",
              "lastPrice": "9156.9"
            }
            ```
            """
            if "subscriptionTicker" not in self.callbacks:
                self.callbacks["subscriptionTicker"] = {}
            self.callbacks["subscriptionTicker"][market] = callback
            self.doSend(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "ticker", "markets": [market]}],
                    },
                ),
            )

        def subscriptionTicker24h(self, market: str, callback: Callable[[Any], None]) -> None:
            """Subscribe to the ticker-24-hour channel, which means `callback` gets passed the new object every second, if values have changed.

            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "ticker": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that:
            {
              "event": "ticker24h",
              "data": {
                "market": "BTC-EUR",
                "open": "9072.9",
                "high": "9263.6",
                "low": "9062.8",
                "last": "9231.8",
                "volume": "85.70530211",
                "volumeQuote": "785714.14",
                "bid": "9225",
                "bidSize": "1.14732373",
                "ask": "9225.1",
                "askSize": "0.65371786",
                "timestamp": 1566564813057
              }
            }
            ```
            """
            if "subscriptionTicker24h" not in self.callbacks:
                self.callbacks["subscriptionTicker24h"] = {}
            self.callbacks["subscriptionTicker24h"][market] = callback
            self.doSend(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "ticker24h", "markets": [market]}],
                    },
                ),
            )

        def subscriptionAccount(self, market: str, callback: Callable[[Any], None]) -> None:
            """Subscribes to the account channel, which sends an update whenever an event happens which is related to the account.
            These are 'order' events (create, update, cancel) or 'fill' events (a trade occurred).

            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "account": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that, either
            {
              "event": "order",
              "orderId": "80b5f04d-21fc-4ebe-9c5f-6d34f78ee477",
              "market": "BTC-EUR",
              "created": 1548684420771,
              "updated": 1548684420771,
              "status": "new",
              "side": "buy",
              "orderType": "limit",
              "amount": "1",
              "amountRemaining": "0.567",
              "price": "9225.1",
              "onHold": "9225.1",
              "onHoldCurrency": "EUR",
              "triggerPrice": "4000",
              "triggerAmount": "4000",
              "triggerType": "price",
              "triggerReference": "lastTrade",
              "timeInForce": "GTC",
              "postOnly": false,
              "selfTradePrevention": "decrementAndCancel",
              "visible": true
            }
            # or
            {
              "event": "fill",
              "market": "BTC-EUR",
              "orderId": "80b5f04d-21fc-4ebe-9c5f-6d34f78ee477",
              "fillId": "15d14b09-389d-4f83-9413-de9d0d8e7715",
              "timestamp": 1542967486256,
              "amount": "0.005",
              "side": "sell",
              "price": "5000.1",
              "taker": true,
              "fee": "0.03",
              "feeCurrency": "EUR"
            }
            ```
            """
            if "subscriptionAccount" not in self.callbacks:
                self.callbacks["subscriptionAccount"] = {}
            self.callbacks["subscriptionAccount"][market] = callback
            self.doSend(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "account", "markets": [market]}],
                    },
                ),
                True,
            )

        def subscriptionCandles(self, market: str, interval: str, callback: Callable[[Any], None]) -> None:
            """Subscribes to candles and returns a candle each time a new one is formed, depending on the interval

            ---
            Args:
            ```python
            market="BTC-EUR"
            interval="1h"  # Choose: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "candles": {
                  "1h": [
                    "BTC-EUR"
                  ]
                }
              }
            }
            # and after that:
            {
              "event": "candle",
              "market": "BTC-EUR",
              "interval": "1h",
              "candle": [
                [
                  1538784000000,
                  "4999",
                  "5012",
                  "4999",
                  "5012",
                  "0.45"
                ]
              ]
            }
            ```
            """
            if "subscriptionCandles" not in self.callbacks:
                self.callbacks["subscriptionCandles"] = {}
            if market not in self.callbacks["subscriptionCandles"]:
                self.callbacks["subscriptionCandles"][market] = {}
            self.callbacks["subscriptionCandles"][market][interval] = callback
            self.doSend(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [
                            {
                                "name": "candles",
                                "interval": [interval],
                                "markets": [market],
                            },
                        ],
                    },
                ),
            )

        def subscriptionTrades(self, market: str, callback: Callable[[Any], None]) -> None:
            """Subscribes to trades, which sends an object whenever a trade has occurred.

            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "trades": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that:
            {
              "event": "trade",
              "timestamp": 1566817150381,
              "market": "BTC-EUR",
              "id": "391f4d94-485f-4fb0-b11f-39da1cfcfc2d",
              "amount": "0.00096361",
              "price": "9311.2",
              "side": "sell"
            }
            ```
            """
            if "subscriptionTrades" not in self.callbacks:
                self.callbacks["subscriptionTrades"] = {}
            self.callbacks["subscriptionTrades"][market] = callback
            self.doSend(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "trades", "markets": [market]}],
                    },
                ),
            )

        def subscriptionBookUpdate(self, market: str, callback: Callable[[Any], None]) -> None:
            """Subscribes to the book and returns a delta on every change to the book.

            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "book": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that:
            {
              "event": "book",
              "market": "BTC-EUR",
              "nonce": 0,
              "bids": [
                ["9209.3", "0"],
                ["9207.7", "0"],
                ["9206.1", "0"],
                ["9204.6", "0.09173282"],
                ["9206.3", "0.08142723"],
                ["9209.5", "0.1015792"],
                ["9207.9", "0.09120002"],
              ],
              "asks": [
                ["9220.2", "0"],
                ["9223.4", "0"],
                ["9225.1", "0"],
                ["9228.1", "0"],
                ["9231.8", "0"],
                ["9233.6", "0"],
                ["9235.1", "0.51598389"],
                ["9233.1", "0.40684114"],
                ["9230.6", "0.33906266"],
                ["9227.2", "0.40078234"],
                ["9221.8", "0.30485309"],
                ["9225.4", "0.36040168"],
                ["9229", "0.36070097"],
              ],
            }
            ```
            """
            if "subscriptionBookUpdate" not in self.callbacks:
                self.callbacks["subscriptionBookUpdate"] = {}
            self.callbacks["subscriptionBookUpdate"][market] = callback
            self.doSend(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "book", "markets": [market]}],
                    },
                ),
            )

        def subscriptionBook(self, market: str, callback: Callable[[Any], None]) -> None:
            """Subscribes to the book and returns a delta on every change to the book.

            ---
            Args:
            ```python
            market="BTC-EUR"
            callback=callback_example
            ```

            ---
            Returns this to `callback`:
            ```python
            # first
            {
              "event": "subscribed",
              "subscriptions": {
                "book": [
                  "BTC-EUR"
                ]
              }
            }
            # and after that:
            {
              "event": "book",
              "market": "BTC-EUR",
              "nonce": 0,
              "bids": [
                ["9209.3", "0"],
                ["9207.7", "0"],
                ["9206.1", "0"],
                ["9204.6", "0.09173282"],
                ["9206.3", "0.08142723"],
                ["9209.5", "0.1015792"],
                ["9207.9", "0.09120002"],
              ],
              "asks": [
                ["9220.2", "0"],
                ["9223.4", "0"],
                ["9225.1", "0"],
                ["9228.1", "0"],
                ["9231.8", "0"],
                ["9233.6", "0"],
                ["9235.1", "0.51598389"],
                ["9233.1", "0.40684114"],
                ["9230.6", "0.33906266"],
                ["9227.2", "0.40078234"],
                ["9221.8", "0.30485309"],
                ["9225.4", "0.36040168"],
                ["9229", "0.36070097"],
              ],
            }
            ```
            """
            self.keepBookCopy = True
            if "subscriptionBookUser" not in self.callbacks:
                self.callbacks["subscriptionBookUser"] = {}
            self.callbacks["subscriptionBookUser"][market] = callback
            if "subscriptionBook" not in self.callbacks:
                self.callbacks["subscriptionBook"] = {}
            self.callbacks["subscriptionBook"][market] = processLocalBook
            self.doSend(
                self.ws,
                json.dumps(
                    {
                        "action": "subscribe",
                        "channels": [{"name": "book", "markets": [market]}],
                    },
                ),
            )

            self.localBook[market] = {}
            self.doSend(self.ws, json.dumps({"action": "getBook", "market": market}))
