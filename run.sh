#!/usr/bin/env bash

date

set -a
source config.env
set +a

python bot.py cs.NE
