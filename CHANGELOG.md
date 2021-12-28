# Changelog

## [v1.2.0] - 2021-12-28

### Changed

- when there's a version bump, Github should push to PyPi now (not only to https://test.pypi.org)

## [v1.1.1] - 2021-12-28

### Changed

- improved description

## [v1.1.0] - 2021-12-28

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

## \[v1.0.2\] - 2021-12-27

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
