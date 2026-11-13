"""
Shared database access for the API process.

Split out of main.py so the embed/widget routes can query without importing
the app (which would be circular). One pool, one cursor helper, one `q`.
"""

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2 import pool

DSN = os.environ["DATABASE_URL"]

# Data changes once a day. A tiny pool is plenty and keeps us inside the
# connection limit of Render's smallest Postgres plan.
# statement_timeout: a request that would scan `sales` through firsts_subject()
# used to sit open for ~50s and return zero bytes until it finished. WordPress
# gives up at its own timeout and used to publish that as a 404. Fail the
# query instead, so the plugin can serve a cached copy or a 503.
POOL = pool.ThreadedConnectionPool(1, 6, DSN, options="-c statement_timeout=10000")


@contextmanager
def cursor():
    conn = POOL.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
    finally:
        # A timed-out statement aborts the transaction. Roll back on the way
        # out or the next borrower inherits an unusable connection.
        try:
            conn.rollback()          # read-only: never leave a transaction open
        finally:
            POOL.putconn(conn)


def q(sql, params=()):
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()
