# Bitvavo API (upgraded)

Hi, this is *not* the official API, but this one has:

- build-in documentation
- typing for *all* functions and classes
- unit tests (I already found ~~three~~ ~~four~~ five bugs that I fixed, because the original code wasn't tested, at all)
- a changelog, so you can track of the changes that I make
- compatible with Python 3.7 and newer ([3.6 isn't supported as of 2021-12-23](https://endoflife.date/python))
- a working version of `getRemainingLimit()`
- will actually wait until the ban has been lifted (in case you get banned)
- more stable api-calls, due to calculating lag between client and server
- fancy logging via `structlog`, including external loggers like from the urllib3 and websocket libs!

Version `1.*` is guaranteed compatible\* with the original API.

\*: Except for `Bitvavo.candles`. I had to renamed the `symbol` argument to `market`, because the `candles` call actually excpects a `market`. So that's more of a bugfix.

\*\*: Same goes for `Bitvavo.book`; it had the same problem as `candles`.

\*\*\*: And I removed the `rateLimitThread` class, but that should've been used internally only anyway

## Links

- [Official API Documentation](https://docs.bitvavo.com/)
- [Official Trading Rules](https://bitvavo.com/en/trading-rules) (recommended read, as it explains a lot of jargon; It's OK to not understand this document if you're just starting out - I don't fully understand the document either)
- [Github for this lib](https://github.com/Thaumatorium/bitvavo-api-upgraded)
