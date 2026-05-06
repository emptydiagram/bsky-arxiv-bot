#!/usr/bin/env bash

date

set -a
source config.env
set +a

uv run main.py cs.NE
