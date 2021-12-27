# Changelog

## [v1.0.2] - 2021-12-27

Everything from since NostraDavid started this project; version `1.0.0` and `1.0.1` did not have `bump2version` working well yet, which is why they do not have separate entries

### Added

- autopublishing to pypi
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
- renamed the `python_bitvavo_api` folder to `bitvavo_api_upgraded`

### Removed

- Nothing yet; I kept code changes to a minimum, until I got `bump2version` working with a `CHANGELOG.md` to prevent changing things without noting it down.
