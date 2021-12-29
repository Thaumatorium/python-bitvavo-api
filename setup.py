from pathlib import Path

from setuptools import find_packages, setup

HERE = Path.cwd()

__version__ = "1.6.0"

with (HERE / "requirements" / "base.txt").open(mode="r") as requirements_file:
    requirements = requirements_file.read().splitlines()

with (HERE / "README.pypi.md").open(mode="r") as readme_file:
    readme = readme_file.read()

# TODO(NostraDavid) add a classifier after testing several versions; maybe change `python_requires`
setup(
    author="Bitvavo BV (original code) and NostraDavid (rebuild)",
    description="A unit-tested fork of the Bitvavo API",
    include_package_data=True,
    install_requires=requirements,
    license="ISC License",
    long_description_content_type="text/markdown",
    long_description=readme,
    name="bitvavo-api-upgraded",
    package_dir={"": "src"},
    packages=find_packages(where="src", exclude=["tests"]),
    python_requires=">=3.7",
    url="https://github.com/Thaumatorium/python-bitvavo-api",
    version=__version__,
)
