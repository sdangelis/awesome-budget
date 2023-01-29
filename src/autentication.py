"""
Functions to register and autenticate users
"""

import sqlite3
from os import path, urandom
from uuid import uuid4

from passlib.hash import argon2


class AuthenticationError(Exception):
    "Exception for app autentication issues"


class AlreadyRegistredError(Exception):
    """
    Exception for user already present in db
    """

    def __init__(self, username):
        self.username = username
        self.message = "user: {username} is already registred"
        super().__init__(self.message)


def login(
    username: str, password: str, db: path = path.join(".db", "awesomebudget.db")
) -> dict:
    """
    logs user in if the password matches SQLite record in the db
    """
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        query = c.execute("SELECT * FROM users WHERE username = ?", (username,))
        query = c.fetchone()
        if not query:
            raise AuthenticationError("Wrong username or password")
        if argon2.verify(password, query[3]):
            return query[0], query[2]
        raise AuthenticationError("Wrong username or password")


def register(
    username: str, password: str, db: path = path.join(".db", "awesomebudget.db")
) -> None:
    """
    registers a user to the SQLite db

    :param username: username to register in the db
    :param password: password to register in the db
    :param db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :returns : None if succesful
    :raises AlreadyRegistredError: if a given username is already present in the DB
    :raises sqlite3.IntegrityError: if there's erorrs with Sqlite data integrity
    """
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        query = c.execute("SELECT * FROM users WHERE username = ?", (username,))
        query = c.fetchall()
        if query:
            return AlreadyRegistredError(f"{username} is already registred")
        try:
            c.execute(
                """
                    INSERT INTO users
                     (user_id, username, password, salt) VALUES(?,?,?,?)
                """,
                (uuid4().bytes_le, username, argon2.hash(password), urandom(16),),
            )
            return None
        except sqlite3.IntegrityError as e:
            raise sqlite3.IntegrityError("Something has gone wrong") from e


def deregister(
    username: str, password: str, db: path = path.join(".db", "awesomebudget.db")
) -> None:
    """not implemented"""

    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        query = c.execute(
            """
        RETURN Names"""
        )
    raise NotImplementedError


def update_password(
    username: str, password: str, db: path = path.join(".db", "awesomebudget.db")
) -> None:
    """not implemented"""
    raise NotImplementedError
