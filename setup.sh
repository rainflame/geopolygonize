#!/usr/bin/env bash

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
git config --local core.hooksPath "$SCRIPT_DIR"/.githooks
