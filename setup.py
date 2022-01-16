from pathlib import Path

from setuptools import find_packages, setup

HERE = Path.cwd()

__version__ = "1.11.2"

with (HERE / "requirements" / "base.txt").open(mode="r") as requirements_file:
    requirements = requirements_file.read().splitlines()

with (HERE / "README.pypi.md").open(mode="r") as readme_file:
    readme = readme_file.read()

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
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Framework :: Pytest",
        "Framework :: tox",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: ISC License (ISCL)",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python",
        "Typing :: Typed",
    ],
    url="https://github.com/Thaumatorium/python-bitvavo-api",
    version=__version__,
)
