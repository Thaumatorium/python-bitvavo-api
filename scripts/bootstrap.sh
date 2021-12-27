#!/usr/bin/env bash

echo "installing tox dependencies"
sudo apt-get install python3-distutils python3-apt --yes

echo "prepare the program for... programming"
pip install -r requirements/dev.txt
pip install -e .

echo "setup local git settings"
git config pull.rebase true  # rebase on pulls, in case of conflicts
git config remote.origin.tagopt --tags  # pull all tags

echo "install pre-commit hooks to prevent you from pushing broken code"
pre-commit install

echo "set global 'git lg' alias"
git config --global alias.lg "log --color --graph --abbrev-commit --pretty=format:'%Cred%h %C(bold blue)%an%Creset %Cgreen%ad -%C(yellow)%d%Creset %s' --date=format:'%Y-%m-%d %H:%M'"
