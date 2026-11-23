#!/bin/zsh

# запускать через -- source ./setup-env.sh 
export PGPASSWORD="postgres"
export PGHOST="localhost"
export PGPORT="5433"
export PGDATABASE="study"
export PGUSER="postgres"

python3 -m venv .venv
source .venv/bin/activate
pip install "psycopg[binary]"
