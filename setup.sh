#!/usr/bin/env bash

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
git config --local core.hooksPath "$SCRIPT_DIR"/.githooks
