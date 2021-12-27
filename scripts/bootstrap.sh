#!/usr/bin/env bash

echo "installing tox dependencies"
sudo apt-get install python3-distutils python3-apt --yes

echo "prepare the program for... programming"
pip install -r requirements/dev.txt
pip install -e .