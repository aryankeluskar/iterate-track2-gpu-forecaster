#!/bin/zsh
cd /Users/aryank/Developer/iterate_hackathon/track_2
run() { PYTHONPATH=src .venv/bin/python -m gpuf.run --method gbm --split dev --universe rental_headline --params "$2" > runs/gbm/$1.json 2>&1 & }
run full '{"mode":"full","train":"all"}'
run io '{"mode":"interval_only","train":"all"}'
run hl '{"mode":"full","train":"headline_like"}'
run iohl '{"mode":"interval_only","train":"headline_like"}'
wait
