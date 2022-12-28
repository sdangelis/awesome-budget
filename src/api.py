import base64
import sqlite3
from datetime import datetime, timedelta
from os import path

import pandas as pd
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class NoSavedTokenError(Exception):
    pass


class ExpiredTokenError(Exception):
    pass


class InvalidEndpointError(Exception):
    pass


def generate_fernet(salt: bytes, password: str) -> Fernet:
    """
  Generates a Fernet cypher from a given salt and password

  :param salt: a fixed salt
  :param password: password to use
  :returns: The Fernet cypherwith base64 url

  :Note: This function is deterministic so should always
  return the same cypher from the same salt and password (at least on the same machine)
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
            """CREATE TABLE IF NOT EXISTS tokens
        (id INTEGER NOT NULL UNIQUE, access BLOB NOT NULL, access_expires TIMESTAMP NOT NULL, refresh BLOB, refresh_expires TIMESTAMP, PRIMARY KEY(id))
        """
        )
        c.execute(
            """REPLACE INTO tokens(id, access, access_expires, refresh, refresh_expires) VALUES(?,?,?,?,?)""",
            (
                1,
                cypher.encrypt(token["access"].encode("utf-8")),
                token["access_expires"],
                cypher.encrypt(token["refresh"].encode("utf-8")),
                token["refresh_expires"],
            ),
        )
        c.commit()
    return True


def load_token(cypher, db: path = path.join(".db", "awesomebudget.db")) -> dict:
    """
    Loads encrypted access and refresh token, refreshing access token as needed
    
    :params cypher: Fernet cypher object to decrypt token. Must match encryption salt and pw
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
                refresh_token(token)


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


def manage_token():
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
        headers={"accept": "application/json", "Authorization": "Bearer " + token},
        params={"country": country},
    )
    df = pd.DataFrame.from_dict(res.json())
    return df.explode("countries", ignore_index=False)


# save requisition


def save_requisition(
    username: str, requision_id: str, db: path = path.join(".db", "awesomebudget.db")
):
    """
    Saves a requisition to db 

    :param username: username associated with the given requisition
    :parm requision_id: ID of the requisition to insert in db
    :param db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :returns: True if successful 
    """
    with sqlite3.connect(db) as conn:
        c = conn.cursor()

        c.execute("SELECT id FROM users WHERE username = ?;", (username,))
        id = c.fetchone()[0]

        # insert requisiotion
        c.execute(
            """INSERT INTO  requisitions(users_id, requisition_id) VALUES(?,?)""",
            (id, requision_id),
        )
        c.commit()
        return True


# load requisition
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
             SELECT Requisition_id FROM requisitions JOIN users on users.id=requisitions.users_id WHERE username = ?
        """,
            (username,),
        )
        query = c.fetchall()
        return query


# delete requisition
def delete_requision(
    token: str,
    username: str,
    requisition_id: str,
    db: path = path.join(".db", "awesomebudget.db"),
) -> bool:
    """
    Delets a requisition 

    :param token: Nordigen API token
    :param username: username associated with the requisition to delete
    :param requisition_id: Id for the requisition to delete
    :param db: path to sqlite db, defaults to path.join(".db", "awesomebudget.db")
    :return: true
    :raises ValueError: if the cancellatkon tokens or requisitions are not valid
    """
    # delete from Nordigen backend
    json = {id: requisition_id}
    res = requests.delete(
        "https://ob.nordigen.com/api/v2/requisitions/",
        headers={
            "Authorization": "Bearer " + token["access"],
            "accept": "application/json",
            "Content-Type": "application/json",
        },
        json=json,
    )
    if not res.ok:
        raise ValueError("invalid requisition ID or token")
    else:
        # if successful delete from db too
        with sqlite3.connect(db, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            c = conn.cursor()
            c.execute(
                "DELETE from  WHERE users_id IN (SELECT user_id from users where username = ?)",
                (username),
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
    if datetime.now() < token["access_expires"]:
        raise ValueError("token expired")

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

    save_requisition(username, res.json()["id"], db)
    return f"Please go to the link {res.json()['link']} to autorize your bank"
