import hashlib
import hmac
import json
import logging
from threading import Thread
from time import sleep, time
from typing import Any, Callable, Dict, List, Union

import websocket as ws_lib  # type: ignore
from requests import delete, get, post, put  # type: ignore
from websocket import WebSocketApp  # missing stubs for WebSocketApp

debugging: bool = False

logger = logging.getLogger("bitvavo-api-upgraded")


def debugToConsole(message: Any) -> None:
    if debugging:
        print(message)
        logger.info(message)


def errorToConsole(message: Any) -> None:
    print(message)
    logger.error(message)


def createSignature(timestamp: int, method: str, url: str, body: dict, APISECRET: str) -> str:
    string = str(timestamp) + method + "/v2" + url
    if len(body.keys()) != 0:
        string += json.dumps(body, separators=(",", ":"))
    signature = hmac.new(APISECRET.encode("utf-8"), string.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature


def createPostfix(options: dict) -> str:
    params = []
    for key in options:
        params.append(key + "=" + str(options[key]))
    postfix = "&".join(params)
    if len(options) > 0:
        postfix = "?" + postfix
    return postfix


def asksCompare(a: float, b: float) -> bool:
    if a < b:
        return True
    return False


def bidsCompare(a: float, b: float) -> bool:
    if a > b:
        return True
    return False


def sortAndInsert(
    book: List[List[str]],
    update: List[List[str]],
    compareFunc: Callable[[float, float], bool],
) -> List[List[str]]:
    for updateEntry in update:
        entrySet: bool = False
        for j in range(len(book)):
            bookItem = book[j]
            if compareFunc(float(updateEntry[0]), float(bookItem[0])):
                book.insert(j, updateEntry)
                entrySet = True
                break
            if float(updateEntry[0]) == float(bookItem[0]):
                if float(updateEntry[1]) > 0.0:
                    book[j] = updateEntry
                    entrySet = True
                    break
                else:
                    book.pop(j)
                    entrySet = True
                    break
        if not entrySet:
            book.append(updateEntry)
    return book


def processLocalBook(ws: "Bitvavo.websocket", message: Dict[str, Any]) -> None:
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


class rateLimitThread(Thread):
    def __init__(self, reset: float, bitvavo: "Bitvavo"):
        self.timeToWait = reset
        self.bitvavo = bitvavo
        Thread.__init__(self)

    def waitForReset(self, waitTime: float) -> None:
        sleep(waitTime)
        if time() < self.bitvavo.rateLimitReset:
            self.bitvavo.rateLimitRemaining = 1000
            debugToConsole("Ban should have been lifted, resetting rate limit to 1000.")
        else:
            timeToWait = (self.bitvavo.rateLimitReset / 1000) - time()
            debugToConsole(f"Ban took longer than expected, sleeping again for {timeToWait} seconds.")
            self.waitForReset(timeToWait)

    def run(self) -> None:
        if self.timeToWait < 0:
            self.timeToWait = 0.001  # 1ms

        self.waitForReset(self.timeToWait)


class receiveThread(Thread):
    def __init__(self, ws: WebSocketApp, wsObject: "Bitvavo.websocket"):  # type: ignore
        self.ws = ws
        self.wsObject = wsObject
        Thread.__init__(self)

    def run(self) -> None:
        try:
            while self.wsObject.keepAlive:
                self.ws.run_forever()
                self.wsObject.reconnect = True
                self.wsObject.authenticated = False
                sleep(self.wsObject.reconnectTimer)
                debugToConsole(f"we have just set reconnect to true and have waited for {self.wsObject.reconnectTimer}")
                self.wsObject.reconnectTimer = self.wsObject.reconnectTimer * 2
        except KeyboardInterrupt:
            debugToConsole("We caught keyboard interrupt in the websocket thread.")

    def stop(self) -> None:
        self.wsObject.keepAlive = False


class Bitvavo:
    def __init__(self, options: Dict = {}):
        self.base: str = "https://api.bitvavo.com/v2"
        self.wsUrl: str = "wss://ws.bitvavo.com/v2/"
        self.ACCESSWINDOW: int = 0
        self.APIKEY: str = ""
        self.APISECRET: str = ""
        self.rateLimitRemaining: int = 1000
        self.rateLimitReset: int = 0
        global debugging
        debugging = False
        for key in options:
            if key.lower() == "apikey":
                self.APIKEY = options[key]
            elif key.lower() == "apisecret":
                self.APISECRET = options[key]
            elif key.lower() == "accesswindow":
                self.ACCESSWINDOW = options[key]
            elif key.lower() == "debugging":
                debugging = options[key]
            elif key.lower() == "resturl":
                self.base = options[key]
            elif key.lower() == "wsurl":
                self.wsUrl = options[key]
        if self.ACCESSWINDOW == 0:
            self.ACCESSWINDOW = 10000

    def getRemainingLimit(self) -> int:
        return self.rateLimitRemaining

    def updateRateLimit(self, response: Union[Dict[str, Any], Any]) -> None:
        # The response: Any is for a CaseInsensitiveDict that's inserted, but mypy was complaining about
        if "errorCode" in response:
            if response["errorCode"] == 105:
                self.rateLimitRemaining = 0
                self.rateLimitReset = int(response["error"].split(" at ")[1].split(".")[0])
                timeToWait = (self.rateLimitReset / 1000) - time()
                if not hasattr(self, "rateLimitThread"):
                    self.rateLimitThread = rateLimitThread(timeToWait, self)
                    self.rateLimitThread.daemon = True
                    self.rateLimitThread.start()
            # setTimeout(checkLimit, timeToWait)
        if "bitvavo-ratelimit-remaining" in response:
            self.rateLimitRemaining = int(response["bitvavo-ratelimit-remaining"])
        if "bitvavo-ratelimit-resetat" in response:
            self.rateLimitReset = int(response["bitvavo-ratelimit-resetat"])
            timeToWait = (self.rateLimitReset / 1000) - time()
            if not hasattr(self, "rateLimitThread"):
                self.rateLimitThread = rateLimitThread(timeToWait, self)
                self.rateLimitThread.daemon = True
                self.rateLimitThread.start()

    def publicRequest(self, url: str) -> Any:
        debugToConsole(f"REQUEST: {url}")
        if self.APIKEY != "":
            now = int(time() * 1000)
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
            self.updateRateLimit(r.headers)
        return r.json()

    def privateRequest(self, endpoint: str, postfix: str, body: Dict, method: str = "GET") -> Any:
        # if this method breaks: add `= {}` after `body:Dict``
        now = int(time() * 1000)
        sig = createSignature(now, method, (endpoint + postfix), body, self.APISECRET)
        url = self.base + endpoint + postfix
        headers = {
            "Bitvavo-Access-Key": self.APIKEY,
            "Bitvavo-Access-Signature": sig,
            "Bitvavo-Access-Timestamp": str(now),
            "Bitvavo-Access-Window": str(self.ACCESSWINDOW),
        }
        debugToConsole("REQUEST: " + url)
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
            self.updateRateLimit(r.headers)
        return r.json()

    def time(self) -> Any:
        return self.publicRequest(self.base + "/time")

    # options: market
    def markets(self, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.publicRequest(self.base + "/markets" + postfix)

    # options: symbol
    def assets(self, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.publicRequest(self.base + "/assets" + postfix)

    # options: depth
    def book(self, symbol: str, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.publicRequest(self.base + "/" + symbol + "/book" + postfix)

    # options: limit, start, end, tradeIdFrom, tradeIdTo
    def publicTrades(self, symbol: str, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.publicRequest(self.base + "/" + symbol + "/trades" + postfix)

    # options: limit, start, end
    def candles(self, market: str, interval: str, options: Dict) -> Any:
        options["interval"] = interval
        postfix = createPostfix(options)
        return self.publicRequest(self.base + "/" + market + "/candles" + postfix)

    # options: market
    def tickerPrice(self, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.publicRequest(self.base + "/ticker/price" + postfix)

    # options: market
    def tickerBook(self, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.publicRequest(self.base + "/ticker/book" + postfix)

    # options: market
    def ticker24h(self, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.publicRequest(self.base + "/ticker/24h" + postfix)

    # optional body parameters: limit:(amount, price, postOnly), market:(amount, amountQuote, disableMarketProtection)
    #                           stopLoss/takeProfit:(amount, amountQuote, disableMarketProtection, triggerType, triggerReference, triggerAmount)
    #                           stopLossLimit/takeProfitLimit:(amount, price, postOnly, triggerType, triggerReference, triggerAmount)
    #                           all orderTypes: timeInForce, selfTradePrevention, responseRequired
    def placeOrder(self, market: str, side: str, orderType: str, body: Dict) -> Any:
        body["market"] = market
        body["side"] = side
        body["orderType"] = orderType
        return self.privateRequest("/order", "", body, "POST")

    def getOrder(self, market: str, orderId: str) -> Any:
        postfix = createPostfix({"market": market, "orderId": orderId})
        return self.privateRequest("/order", postfix, {}, "GET")

    # Optional parameters: limit:(amount, amountRemaining, price, timeInForce, selfTradePrevention, postOnly)
    #          untriggered stopLoss/takeProfit:(amount, amountQuote, disableMarketProtection, triggerType, triggerReference, triggerAmount)
    #                      stopLossLimit/takeProfitLimit: (amount, price, postOnly, triggerType, triggerReference, triggerAmount)
    def updateOrder(self, market: str, orderId: str, body: Dict) -> Any:
        body["market"] = market
        body["orderId"] = orderId
        return self.privateRequest("/order", "", body, "PUT")

    def cancelOrder(self, market: str, orderId: str) -> Any:
        postfix = createPostfix({"market": market, "orderId": orderId})
        return self.privateRequest("/order", postfix, {}, "DELETE")

    # options: limit, start, end, orderIdFrom, orderIdTo
    def getOrders(self, market: str, options: Dict) -> Any:
        options["market"] = market
        postfix = createPostfix(options)
        return self.privateRequest("/orders", postfix, {}, "GET")

    # options: market
    def cancelOrders(self, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.privateRequest("/orders", postfix, {}, "DELETE")

    # options: market
    def ordersOpen(self, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.privateRequest("/ordersOpen", postfix, {}, "GET")

    # options: limit, start, end, tradeIdFrom, tradeIdTo
    def trades(self, market: str, options: Dict) -> Any:
        options["market"] = market
        postfix = createPostfix(options)
        return self.privateRequest("/trades", postfix, {}, "GET")

    def account(self) -> Any:
        return self.privateRequest("/account", "", {}, "GET")

    # options: symbol
    def balance(self, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.privateRequest("/balance", postfix, {}, "GET")

    def depositAssets(self, symbol: str) -> Any:
        postfix = createPostfix({"symbol": symbol})
        return self.privateRequest("/deposit", postfix, {}, "GET")

    # optional body parameters: paymentId, internal, addWithdrawalFee
    def withdrawAssets(self, symbol: str, amount: str, address: str, body: Dict) -> Any:
        body["symbol"] = symbol
        body["amount"] = amount
        body["address"] = address
        return self.privateRequest("/withdrawal", "", body, "POST")

    # options: symbol, limit, start, end
    def depositHistory(self, options: Dict) -> Any:
        postfix = createPostfix(options)
        return self.privateRequest("/depositHistory", postfix, {}, "GET")

    # options: symbol, limit, start, end
    def withdrawalHistory(self, options: Dict) -> Any:
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
            self.callbacks: Dict[str, Any] = {}
            self.keepAlive = True
            self.reconnect = False
            self.reconnectTimer = 0.1
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
            self.localBook: Dict = {}

        def closeSocket(self) -> None:
            self.ws.close()
            self.keepAlive = False
            self.receiveThread.join()

        def waitForSocket(self, ws: WebSocketApp, message: str, private: bool) -> None:  # type: ignore
            if (not private and self.open) or (private and self.authenticated and self.open):
                return
            else:
                sleep(0.1)
                self.waitForSocket(ws, message, private)

        def doSend(self, ws: WebSocketApp, message: str, private: bool = False) -> None:  # type: ignore
            if private and self.APIKEY == "":
                errorToConsole("You did not set the API key, but requested a private function.")
                return
            self.waitForSocket(ws, message, private)
            ws.send(message)
            debugToConsole("SENT: " + message)

        def on_message(self, ws: WebSocketApp, msg: str) -> None:  # type: ignore # noqa: C901 (too-complex)
            debugToConsole(f"RECEIVED: {msg}")
            msg_dict: Dict[str, Any] = json.loads(msg)
            callbacks = self.callbacks

            if "error" in msg_dict:
                if msg_dict["errorCode"] == 105:
                    self.bitvavo.updateRateLimit(msg_dict)
                if "error" in callbacks:
                    callbacks["error"](msg_dict)
                else:
                    errorToConsole(msg_dict)

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

        def on_error(self, ws: WebSocketApp, error: Any):  # type: ignore
            if "error" in self.callbacks:
                self.callbacks["error"](error)
            else:
                errorToConsole(error)

        def on_close(self, ws: WebSocketApp):  # type: ignore
            self.receiveThread.stop()
            debugToConsole("Closed Websocket.")

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

        def on_open(self, ws: WebSocketApp):  # type: ignore
            now = int(time() * 1000)
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
                debugToConsole("we started reconnecting")
                thread = Thread(target=self.checkReconnect)
                thread.start()

        def setErrorCallback(self, callback: Callable) -> None:
            self.callbacks["error"] = callback

        def time(self, callback: Callable) -> None:
            self.callbacks["time"] = callback
            self.doSend(self.ws, json.dumps({"action": "getTime"}))

        # options: market
        def markets(self, options: Dict, callback: Callable) -> None:
            self.callbacks["markets"] = callback
            options["action"] = "getMarkets"
            self.doSend(self.ws, json.dumps(options))

        # options: symbol
        def assets(self, options: Dict, callback: Callable) -> None:
            self.callbacks["assets"] = callback
            options["action"] = "getAssets"
            self.doSend(self.ws, json.dumps(options))

        # options: depth
        def book(self, market: str, options: Dict, callback: Callable) -> None:
            self.callbacks["book"] = callback
            options["market"] = market
            options["action"] = "getBook"
            self.doSend(self.ws, json.dumps(options))

        # options: limit, start, end, tradeIdFrom, tradeIdTo
        def publicTrades(self, market: str, options: Dict, callback: Callable) -> None:
            self.callbacks["publicTrades"] = callback
            options["market"] = market
            options["action"] = "getTrades"
            self.doSend(self.ws, json.dumps(options))

        # options: limit
        def candles(self, market: str, interval: str, options: Dict, callback: Callable) -> None:
            self.callbacks["candles"] = callback
            options["market"] = market
            options["interval"] = interval
            options["action"] = "getCandles"
            self.doSend(self.ws, json.dumps(options))

        # options: market
        def ticker24h(self, options: Dict, callback: Callable) -> None:
            self.callbacks["ticker24h"] = callback
            options["action"] = "getTicker24h"
            self.doSend(self.ws, json.dumps(options))

        # options: market
        def tickerPrice(self, options: Dict, callback: Callable) -> None:
            self.callbacks["tickerPrice"] = callback
            options["action"] = "getTickerPrice"
            self.doSend(self.ws, json.dumps(options))

        # options: market
        def tickerBook(self, options: Dict, callback: Callable) -> None:
            self.callbacks["tickerBook"] = callback
            options["action"] = "getTickerBook"
            self.doSend(self.ws, json.dumps(options))

        # optional body parameters: limit:(amount, price, postOnly), market:(amount, amountQuote, disableMarketProtection)
        #                           stopLoss/takeProfit:(amount, amountQuote, disableMarketProtection, triggerType, triggerReference, triggerAmount)
        #                           stopLossLimit/takeProfitLimit:(amount, price, postOnly, triggerType, triggerReference, triggerAmount)
        #                           all orderTypes: timeInForce, selfTradePrevention, responseRequired
        def placeOrder(self, market: str, side: str, orderType: str, body: Dict, callback: Callable) -> None:
            self.callbacks["placeOrder"] = callback
            body["market"] = market
            body["side"] = side
            body["orderType"] = orderType
            body["action"] = "privateCreateOrder"
            self.doSend(self.ws, json.dumps(body), True)

        def getOrder(self, market: str, orderId: str, callback: Callable) -> None:
            self.callbacks["getOrder"] = callback
            options = {
                "action": "privateGetOrder",
                "market": market,
                "orderId": orderId,
            }
            self.doSend(self.ws, json.dumps(options), True)

        # Optional parameters: limit:(amount, amountRemaining, price, timeInForce, selfTradePrevention, postOnly)
        #          untriggered stopLoss/takeProfit:(amount, amountQuote, disableMarketProtection, triggerType, triggerReference, triggerAmount)
        #                      stopLossLimit/takeProfitLimit: (amount, price, postOnly, triggerType, triggerReference, triggerAmount)
        def updateOrder(self, market: str, orderId: str, body: Dict, callback: Callable) -> None:
            self.callbacks["updateOrder"] = callback
            body["market"] = market
            body["orderId"] = orderId
            body["action"] = "privateUpdateOrder"
            self.doSend(self.ws, json.dumps(body), True)

        def cancelOrder(self, market: str, orderId: str, callback: Callable) -> None:
            self.callbacks["cancelOrder"] = callback
            options = {
                "action": "privateCancelOrder",
                "market": market,
                "orderId": orderId,
            }
            self.doSend(self.ws, json.dumps(options), True)

        # options: limit, start, end, orderIdFrom, orderIdTo
        def getOrders(self, market: str, options: Dict, callback: Callable) -> None:
            self.callbacks["getOrders"] = callback
            options["action"] = "privateGetOrders"
            options["market"] = market
            self.doSend(self.ws, json.dumps(options), True)

        # options: market
        def cancelOrders(self, options: Dict, callback: Callable) -> None:
            self.callbacks["cancelOrders"] = callback
            options["action"] = "privateCancelOrders"
            self.doSend(self.ws, json.dumps(options), True)

        # options: market
        def ordersOpen(self, options: Dict, callback: Callable) -> None:
            self.callbacks["ordersOpen"] = callback
            options["action"] = "privateGetOrdersOpen"
            self.doSend(self.ws, json.dumps(options), True)

        # options: limit, start, end, tradeIdFrom, tradeIdTo
        def trades(self, market: str, options: Dict, callback: Callable) -> None:
            self.callbacks["trades"] = callback
            options["action"] = "privateGetTrades"
            options["market"] = market
            self.doSend(self.ws, json.dumps(options), True)

        def account(self, callback: Callable) -> None:
            self.callbacks["account"] = callback
            self.doSend(self.ws, json.dumps({"action": "privateGetAccount"}), True)

        # options: symbol
        def balance(self, options: Dict, callback: Callable) -> None:
            options["action"] = "privateGetBalance"
            self.callbacks["balance"] = callback
            self.doSend(self.ws, json.dumps(options), True)

        def depositAssets(self, symbol: str, callback: Callable) -> None:
            self.callbacks["depositAssets"] = callback
            self.doSend(
                self.ws,
                json.dumps({"action": "privateDepositAssets", "symbol": symbol}),
                True,
            )

        # optional body parameters: paymentId, internal, addWithdrawalFee
        def withdrawAssets(self, symbol: str, amount: str, address: str, body: Dict, callback: Callable) -> None:
            self.callbacks["withdrawAssets"] = callback
            body["action"] = "privateWithdrawAssets"
            body["symbol"] = symbol
            body["amount"] = amount
            body["address"] = address
            self.doSend(self.ws, json.dumps(body), True)

        # options: symbol, limit, start, end
        def depositHistory(self, options: Dict, callback: Callable) -> None:
            self.callbacks["depositHistory"] = callback
            options["action"] = "privateGetDepositHistory"
            self.doSend(self.ws, json.dumps(options), True)

        # options: symbol, limit, start, end
        def withdrawalHistory(self, options: Dict, callback: Callable) -> None:
            self.callbacks["withdrawalHistory"] = callback
            options["action"] = "privateGetWithdrawalHistory"
            self.doSend(self.ws, json.dumps(options), True)

        def subscriptionTicker(self, market: str, callback: Callable) -> None:
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

        def subscriptionTicker24h(self, market: str, callback: Callable) -> None:
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

        def subscriptionAccount(self, market: str, callback: Callable) -> None:
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

        def subscriptionCandles(self, market: str, interval: str, callback: Callable) -> None:
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

        def subscriptionTrades(self, market: str, callback: Callable) -> None:
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

        def subscriptionBookUpdate(self, market: str, callback: Callable) -> None:
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

        def subscriptionBook(self, market: str, callback: Callable) -> None:
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
