#!/bin/sh

my_dir="$(dirname "$0")"
cd "${my_dir}"

cd ..
. ./venv/bin/activate

python ./server/smsgate.py

