import os
import psycopg

def connect(autocommit: Bool = False) -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPOTR", "5433"),
        dbname=os.getenv("PGDATABASE", "study"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
        autocommit=autocommit,
    )

