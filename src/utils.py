"""
Common Helper functions
"""

import sqlite3
from os import path


def create_tables(db: path = path.join(".db", "awesomebudget.db")):
    """
    If not already present, creates all table and indices in the provided sqlite3 db

    :params db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :returns: True if successful
    """
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users
            (id INTEGER, user_id BLOB NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE, password TEXT,
            salt BLOB NOT NULL UNIQUE, PRIMARY KEY(id))
            """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS requisitions
            (id INTEGER NOT NULL UNIQUE, users_id INTEGER NOT NULL, requisition_id TEXT,
            expiry TIMESTAMP NOT NULL,
            PRIMARY KEY(id), FOREIGN KEY(users_id) REFERENCES users(id));
            """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS accounts
            (id INTEGER NOT NULL UNIQUE, account_id NOT NULL UNIQUE,
            requisition_id INTEGER NOT NULL UNIQUE,
            PRIMARY KEY(id), FOREIGN KEY(requisition_id) REFERENCES requisitions(id));
            """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS balance
            (id INTEGER NOT NULL, account_id NOT NULL, balance INTEGER,
            last_checked TIMESTAMP NOT NULL,
            PRIMARY KEY(id), FOREIGN KEY(account_id) REFERENCES accounts(id))
            """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS categories
            (id INTEGER NOT NULL UNIQUE, category TEXT NOT NULL, PRIMARY KEY(id))
            """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS budget
            (id INTEGER, users_id INTEGER, categories_id INTEGER, amount NUMERIC,
            PRIMARY KEY(id), FOREIGN KEY (categories_id) REFERENCES categories(id),
            FOREIGN KEY(users_id) REFERENCES users(id))
            """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS tokens (id INTEGER NOT NULL UNIQUE,
            access BLOB NOT NULL, access_expires TIMESTAMP NOT NULL, refresh BLOB,
            refresh_expires TIMESTAMP, PRIMARY KEY(id))
            """
        )
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_id on users(id)")
        return True
