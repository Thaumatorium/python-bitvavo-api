#!/usr/bin/env bash

echo "installing latest uv"
curl -LsSf https://astral.sh/uv/install.sh | sh

echo "prepare the program for... programming"
uv sync

echo "setup local git settings"
git config pull.rebase true  # rebase on pulls, in case of conflicts
git config remote.origin.tagopt --tags  # pull all tags

echo "install pre-commit hooks to prevent you from pushing broken code"
pre-commit install

echo "set global 'git lg' alias"
git config --global alias.lg "log --color --graph --abbrev-commit --pretty=format:'%Cred%h %C(bold blue)%an%Creset %Cgreen%ad -%C(yellow)%d%Creset %s' --date=format:'%Y-%m-%d %H:%M'"
