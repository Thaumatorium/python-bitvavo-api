#!/usr/bin/env bash

echo "installing tox dependencies"
sudo apt-get install python3-distutils python3-apt --yes

echo "prepare the program for... programming"
pip install -r requirements/dev.txt
pip install -e .

echo "setup local git settings"
git config pull.rebase true  # rebase on pulls, in case of conflicts
git config remote.origin.tagopt --tags  # pull all tags