"""
Functions to deal with Nordigen Open Banking APIs
Includes token encryption/decryption.
"""

import base64
import sqlite3
from datetime import datetime, timedelta
from os import path

import pandas as pd
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class NoTokenError(Exception):
    "Should be raised if there's no API token"


class ExpiredTokenError(Exception):
    "should be raised if token is expired"


class InvalidEndpointError(Exception):
    "should be raised for any API error due to invalid Json values"


def generate_fernet(salt: bytes, password: str) -> Fernet:
    """
    Generates a Fernet cypher from a given salt and password

    :param salt: a fixed salt
    :param password: password to use
    :returns: The Fernet cypherwith base64 url

    :note: This function is deterministic so should always
    return the same cypher from the same salt and password
    """
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000)
    return Fernet(
        base64.urlsafe_b64encode(kdf.derive(bytes(password, encoding="utf8")))
    )


def request_token(secret_id: str, secret_key: str) -> dict:
    """
    Requests a token from Nordigen APIs

    :param secret_id: Nordigen secret ID
    :param secret_key: Nordigen secret key
    :return: Dictionary with token, renewal token and expiry dates in datetime format
    :note: see Nordigen OB API guideline at https://ob.nordigen.com/api/docs
    """
    json = {
        "secret_id": secret_id,
        "secret_key": secret_key,
    }
    res = requests.post(
        "https://ob.nordigen.com/api/v2/token/new/",
        headers={"accept": "application/json", "Content-Type": "application/json"},
        json=json,
    )
    data = res.json()
    data.update(
        {
            "access_expires": datetime.now()
            + timedelta(seconds=data["access_expires"] - 1)
        }
    )
    data.update(
        {
            "refresh_expires": datetime.now()
            + timedelta(seconds=data["refresh_expires"] - 1)
        }
    )
    return data


def save_token(
    token: dict, cypher: Fernet, db: path = path.join(".db", "awesomebudget.db")
) -> bool:
    """
    Saves encrypted access and refresh token.

    :param token: token as requested by request_token
    :param cypher: Fernet cypher object to encrypt token
    :param db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :return: True if successful
    """

    with sqlite3.connect(db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        c = conn.cursor()
        c.execute(
            """REPLACE INTO tokens(id, access, access_expires, refresh, refresh_expires)
            VALUES(?,?,?,?,?)""",
            (
                1,
                cypher.encrypt(token["access"].encode("utf-8")),
                token["access_expires"],
                cypher.encrypt(token["refresh"].encode("utf-8")),
                token["refresh_expires"],
            ),
        )
        conn.commit()
        return True


def refresh_token(token: dict) -> dict:
    """
    requests refreshed token and updates token as needed

    :params token: token dictionary
    :returns: token dict with updated refresh token
    :raise ExpiredTokenError: if refresh_token is expired
    :note: This function will possibly edit the token dictionary in place
    """
    if datetime.now() < token["refresh_expires"]:
        raise ExpiredTokenError

    json = {"refresh": token["refresh"]}
    res = requests.post(
        "https://ob.nordigen.com/api/v2/token/refresh/",
        headers={"accept": "application/json", "Content-Type": "application/json"},
        json=json,
    )
    data = res.json()
    token.update({"access": data["access"]})
    token.update(
        {
            "access_expires": datetime.now()
            + timedelta(seconds=data["access_expires"] - 1)
        }
    )
    return token


def load_token(cypher: Fernet, db: path = path.join(".db", "awesomebudget.db")) -> dict:
    """
    Loads encrypted access and refresh token, refreshing access token as needed

    :params cypher: Fernet object to decrypt token. Must match encryption salt and pw
    :params db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :returns: loaded token dict in request_token format
    :raises ValueError: If there is no token to load
    """

    with sqlite3.connect(db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
        c = conn.cursor()
        c.execute("SELECT * from tokens")
        query = c.fetchone()
        if not query:
            raise ValueError("No token to load")
        else:
            token = {
                "access": cypher.decrypt(query[1]).decode("utf-8"),
                "access_expires": query[2],
                "refresh": cypher.decrypt(query[3]).decode("utf-8"),
                "refresh_expires": query[4],
            }
            if datetime.now() < token["access_expires"]:
                return token
            else:
                return refresh_token(token)


def manage_token():
    "TBD"
    raise NotImplementedError


def get_providers(token: str, country: str) -> pd.DataFrame:
    """
    queries the nordigen API for compatible banks

    :param token: Nordigen API token
    :param country: 2-letter uppercase ISO code for a country (str)
    :returns:  exploded pd.DataFrame with compatible financial insitutions
    """
    res = requests.get(
        "https://ob.nordigen.com/api/v2/institutions",
        headers={
            "accept": "application/json",
            "Authorization": "Bearer " + token["access"],
        },
        params={"country": country},
    )
    if res.status_code != 200:
        raise RuntimeError(res.json())
    df = pd.DataFrame.from_dict(res.json())
    return df.set_index("name").drop(
        columns=["bic", "transaction_total_days", "countries", "logo"]
    )


def save_requisition(
    username: str,
    requisition_id: str,
    expiry_date: datetime,
    db: path = path.join(".db", "awesomebudget.db"),
):
    """
    Saves a requisition to db

    :param username: username associated with the given requisition
    :param requisition_id: ID of the requisition to insert in db
    :param expiry_date: requisition expiry date
    :param db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :returns: True if successful
    """
    with sqlite3.connect(db) as conn:
        c = conn.cursor()

        c.execute("SELECT id FROM users WHERE username = ?;", (username,))
        user_id = c.fetchone()[0]

        # insert requisition
        c.execute(
            "INSERT INTO requisitions(users_id, requisition_id, expiry) VALUES(?,?,?)",
            (user_id, requisition_id, expiry_date),
        )
        conn.commit()
        return True


def load_requisitions(
    username: str, db: path = path.join(".db", "awesomebudget.db")
) -> tuple:
    """
    loads all requisitions from DB associated with a given user

    :param username: username to retrieve requisitions for
    :param db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :returns: tuple of requistions associated with the given user
    """
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT Requisition_id FROM requisitions
            JOIN users on users.id=requisitions.users_id WHERE username = ?
        """,
            (username,),
        )
        query = c.fetchall()
        return query


def delete_requision(
    token: str,
    username: str,
    requisition_id: str,
    db: path = path.join(".db", "awesomebudget.db"),
    local_only: bool = False,
) -> bool:
    """
    Delets a requisition

    :param token: Nordigen API token
    :param username: username associated with the requisition to delete
    :param requisition_id: id for the requisition to delete
    :param db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :parm local_only: Whether to delete only from local db rather than Nordigen's API
    :return: true
    :raises ValueError: if the cancellatkon tokens or requisitions are not valid
    """
    # delete from Nordigen backend
    if not local_only:
        res = requests.delete(
            f"https://ob.nordigen.com/api/v2/requisitions/{requisition_id}/",
            headers={
                "Authorization": "Bearer " + token["access"],
                "accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        if not res.ok:
            raise ValueError("invalid requisition ID or token")
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute(
            """DELETE from requisitions
                WHERE users_id IN (SELECT user_id from users WHERE username = (?))""",
            (username,),
        )
    return True


def create_requisition(
    token: str,
    institution_id: str,
    username: str,
    db: path = path.join(".db", "awesomebudget.db"),
) -> str:
    """
    Creates a new nordigen requisition, saving it to db and returning the onboarding url

    :param token: Nordigen API token
    :param username: username to associate to the request
    :param institution_id:  Nordigen ID for the financial insitution of choice
    :param db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :returns: Nordigen URL for customer onboarding
    :raise ValueError: For now when token is expired
    """
    json = {
        "institution_id": institution_id,
        "redirect": f"http://localhost:8501/?token={token['access']}",
    }
    res = requests.post(
        "https://ob.nordigen.com/api/v2/requisitions/",
        headers={
            "Authorization": "Bearer " + token["access"],
            "accept": "application/json",
            "Content-Type": "application/json",
        },
        json=json,
    )
    created_at = datetime.strptime(res.json()["created"], "%Y-%m-%dT%H:%M:%S.%f%z")
    requisition = {
        "username": username,
        "requisition_id": res.json()["id"],
        "expiry_date": created_at + timedelta(days=90),
        "db": db,
    }
    save_requisition(**requisition)
    return f"Please go to the link {res.json()['link']} to autorize your bank"


def save_account(
    account_id: str,
    requisition_id: str,
    db: path = path.join(".db", "awesomebudget.db"),
):
    """
    Saves the selected account into the DB

    :param account_id: Nordigen id for the account to save
    :param requisition_id: Nordigen id for requisition associated with the accounts
    :param db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :return: True if saved successfully
    """
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO accounts(account_id, requisition_id) values
        (?, (SELECT id FROM requisitions WHERE requisition_id = (?)))""",
            (account_id, requisition_id),
        )
        conn.commit()
    return True


def load_accounts(username: str, db: path = path.join(".db", "awesomebudget.db")):
    """
    Loads all accounts for the given user

    :param username: username to retireve accounts for
    :param db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :return: list of DB rows
    """
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute(
            """
        SELECT * FROM accounts WHERE user_id IN (
            SELECT id FROM users WHERE username = (?))
        """,
            (username,),
        )
        return c.fetchall()


def get_accounts(token: dict, requisition_id: str) -> dict:
    """
    Gets all accounts associated with a given requisition

    :paramn token: Nordigen API token
    :param requisition_id: requisition_id of the requisition to query
    :returns: A dict with the accounts associated with the requisition
    """
    res = requests.get(
        f"https://ob.nordigen.com/api/v2/requisitions/{requisition_id}/",
        headers={
            "accept": "application/json",
            "Authorization": "Bearer " + token["access"],
        },
    )

    accounts = {"requisition_id": res.json()["id"], "ids": res.json()["accounts"]}
    return accounts


def get_transasctions(token: dict, account_id: str):
    """
    Get transactions for a given account

    :param token: Nordigen API token
    :param account_id: Nordigen account ID to get transactions for
    :returns: A dict with transactions as per NORDIGEN Schema
    """
    res = requests.get(
        f"https://ob.nordigen.com/api/v2/accounts/{account_id}/transactions",
        headers={
            "accept": "application/json",
            "Authorization": "Bearer " + token["access"],
        },
    )
    return _normalise_transactions(res.json())


def get_balance(token: dict, account_id: str) -> pd.DataFrame:
    """Get balance for a given account

    :param token: Nordigen API token
    :param account_id: Nordigen account ID to get transactions for
    :returns: A normalised df with balances
    """
    res = requests.get(
        f"https://ob.nordigen.com/api/v2/accounts/{account_id}/balances",
        headers={
            "accept": "application/json",
            "Authorization": "Bearer " + token["access"],
        },
    )
    # Return normalised DF
    return (
        pd.json_normalize(res.json()["balances"])
        .rename(columns=lambda x: str.replace(x, ".", "_"))
        .assign(
            referenceDate=lambda x: pd.to_datetime(x["referenceDate"]),
            balanceAmount_amount=lambda x: pd.to_numeric(x["balanceAmount_amount"]),
        )
        .set_index("referenceDate")
    )


def get_account_data(token: dict, account_id: str) -> dict:
    """TBD"""
    data = {
        "balance": get_balance(token, account_id),
        "transactions": get_transasctions(token, account_id),
        "last_updated": datetime.now(),
    }
    return data


def _normalise_transactions(transactions: dict) -> pd.DataFrame:
    """
    Normalise transactions from json

    :param transactions: transaction Json object from Nordigen APIs
    :return: a normalised pd DataFrame object
    with booked and pending transactions in a status column
    """
    tables = map(
        lambda x: pd.json_normalize(transactions["transactions"][x]).assign(status=x),
        ["pending", "booked"],
    )
    table = (
        pd.concat(tables)
        .rename(columns=lambda x: str.replace(x, ".", "_"))
        .assign(
            valueDate=lambda x: pd.to_datetime(x["valueDate"]),
            bookingDate=lambda x: pd.to_datetime(x["bookingDate"]),
            transactionAmount_amount=lambda x: pd.to_numeric(
                x["transactionAmount_amount"]
            ),
        )
        .convert_dtypes()
    )
    return table
