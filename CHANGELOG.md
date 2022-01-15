# Changelog

## $UNRELEASED

### Changed

- improve api calls by subtracting some client-server lag; This should make calls more stable
- simplify Bitvavo constructor (doesn't change anything about the external API)
- fix time_to_wait by checking whether curr_time > rateLimitResetAt

### Removed

- rateLimitThread, because it has been a pain in my ass. Using a regular `sleep()` is much better, I noticed.

## v1.8.2 - 2022-01-15

### Changed

- `time_to_wait` now _always_ returns a positive number. I'm getting sick of sleep getting a negative number

## v1.8.1 - 2022-01-15

### Added

- type aliases! You can now use `s`, `ms`, `us`, instead of slapping `int` on everything! float versions `s_f`, `ms_f` and `us_f` are also available. You'll likely use `ms` and `s_f` most of the time :)
- helper functions! I added `time_ms` and `time_to_wait` to hide some weird calculations behind functions.

### Changed

- improved the timing calculation and typing of certain values a bit

## v1.8.0 - 2022-01-11

### Changed

- fixed getRemainingLimit - This explains why it NEVER changed from 1000...

## v1.7.0 - 2021-12-31

Documentation now comes built-in! :D

I'll probably find some typo/minor error right after creating this version, but I think for users this is one of the more important updates, so out it does!

PS: Happy new year! I write this as it's 2021-12-31 23:15. Almost stopping, so I can stuff my face with Oliebollen and celebrate new year! :D

### Added

- documentation/docstrings for almost every function and method!
- type aliases: `anydict`,`strdict`,`intdict`,`errordict`
- types for `caplog` and `capsys` in all `test_*` function

### Changed

- `candle` wasn't the only wrongly named method. `book` was too. Changed `symbol` argument to `market`
- string concatenation converted to f-strings
- a ton of improvements to unit tests, checking for types, and conversion possibilities, though most of them for `Bitvavo`, not for `Bitvavo.websocket`
- simplified a few functions; though I wrote tests for them to confirm behavior before changing them
- improved type hints for several functions - for example: replaced some `Any`'s with `Union[List[anydict], anydict]`; in other words: reduced the use of `Any`

### Removed

- the old non-documentation above each function (it usually started with `# options:`)

## v1.6.0 - 2021-12-29

Bugfix round! All found bugs in the original code should now be fixed.

### Changed

- fixed ["Negative sleep time length"](https://github.com/bitvavo/python-bitvavo-api/pull/22)
- fixed ["API response error when calling depositAssets()"](https://github.com/bitvavo/python-bitvavo-api/pull/18)
- in `Bitvavo.candles()` renamed the `symbol` argument to `market`, because candles expects a market, and not a symbol... The only API break I've done so far, but it's super minor.

## v1.5.0 - 2021-12-29

### Added

- separate README for pypi; now I can keep that separate from the one on Github; they can share *some* information, but don't need to share all
- guides on how to get started as either a users or a developer (who wants to work on this lib)
- test support for Python 3.7 - 3.10

### Changed

- dependencies are now loosened so users of this lib get more freedom to choose their versions

## v1.4.1 - 2021-12-29

### Changed

- nothing, I just need to push a new commit to Github so I can trigger a new publish

## v1.4.0 - 2021-12-29

### Changed

- set the `mypy` settings to something sane (as per some rando internet articles)
- `pre-commit` `flake8` support; this was initially disabled due to too a lack of sane settings
- reduced pyupgrade from `--py39-plus` to `--py38-plus`, due to `39` changing `Dict` to `dict` and `List` to `list`, but `mypy` not being able to handle those new types yet.
- added types to *all* functions, methods and classes

## v1.3.3 - 2021-12-29

### Changed

- fix the workflow (hopefully) - if I did, then this is the last you'll see about that

## v1.3.2 - 2021-12-29

### Changed

- fix requirements; 1.3.1 is *broken*

## v1.3.1 - 2021-12-29

### Changed

- easy fix to enable publishing to PyPi: disable the `if` that checks for tags 😅

## v1.3.0 - 2021-12-28

### Changed

- when there's a version bump, Github should push to PyPi now (not only to https://test.pypi.org)

## v1.1.1 - 2021-12-28

### Changed

- improved description

## v1.1.0 - 2021-12-28

### Added

- a metric fuckton of tests to check if everything works as expected. said tests are a bit... rough, but it's better than nothing, as I already found two bugs that showed that the original code *did not work!*
- two fixtures: `bitvavo` and `websocket`, each used to test each category of methods (REST vs websockets)

### Changed

- renamed the `python_bitvavo_api` folder to `bitvavo_api_upgraded`
- replaced `websocket` lib with `websocket-client`; I picked the wrong lib, initially, due to a lack of requirements in the original repo
- the `*ToConsole` functions now use the logging library from Python, as the print statement raised an exception when it received a exception object, instead of a string message...... (the `+` symbol was sorta the culprit, but not really - the lack of tests was the true culprit)
- the `on_*` methods now have either an extra `self` or `ws` argument, needed to unfuck the websocket code

### Removed

...

## v1.0.2 - 2021-12-27

Everything from since NostraDavid started this project; version `1.0.0` and `1.0.1` did not have `bump2version` working well yet, which is why they do not have separate entries

### Added

- autopublishing to pypi
- capability to use a `.env` file to hold `BITVAVO_APIKEY` and `BITVAVO_APISECRET` variables
- `setup.py`; it was missing as _someone_ added it to .gitignore
- `__init__.py` to turn the code into a package (for `setup.py`)
- `MANIFEST.in` to include certain files in the source distribution of the app (needed for tox)
- `scripts/bootstrap.sh` to get newbies up and running faster
- ton of tools (`pre-commit`, `tox`, `pytest`, `flake8`, etc; see `requirements/dev.txt` for more information)
- ton of settings (either in `tox.ini`, `pyproject.toml`, or in a dedicated file like `.pre-commit-config` or `.bumpversion.cfg`)
- stub test to `test_bitvavo.py` to make tox happy
- added `# type: ignore` in `bitvavo.py` to shush mypy

### Changed

- moved `python_bitvavo_api` into the `src` folders
- moved and renamed `src/python_bitvavo_api/testApi.py` to `tests/test_bitvavo.py` (for `pytest` compatibility)

### Removed

- Nothing yet; I kept code changes to a minimum, until I got `bump2version` working with a `CHANGELOG.md` to prevent changing things without noting it down.
