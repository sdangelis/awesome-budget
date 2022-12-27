from sqlite3.dbapi2 import Binary
from matplotlib import pyplot
from numpy import ceil
from numpy.core.numeric import ones_like
import pandas as pd
from requests.exceptions import RequestsDependencyWarning
import streamlit as st
import requests
from os import environ, urandom
import sqlite3
from passlib.hash import argon2
from uuid import uuid4, UUID
import json
import datetime
from random import sample
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from db import save_requisition


"""
Helper module, for functions dealing with Nordigen APIs and the web app
"""


def get_token(secrets):
  """
  Get token
  input:
  returns: the json request 
  TO-DO: need to find a way to capture if token is expired and in that 
  case ask for renewal. Need to add token and expiry date to database.
  issue here is should the token be unencrypted? 
  could encrypt it with the secrets as key as to keep everything safe
  Yes, I now have a way to encrypt this but need to actually implement it properly
  """
  json = {'secret_id' : secrets[0], 'secret_key' : secrets[1], 
    }
  res = requests.post('https://ob.nordigen.com/api/v2/token/new/',
  headers={'accept' : 'application/json', 'Content-Type': 'application/json'}, json = json)
  print(res.json())
  return res.json()


def refresh_token(secrets, token):
  pass


@st.cache
def generate_fernet(salt: bytes, password: str):
  """
  Generates a Fernet cypher from a given salt and password
  Inputa:
  salt: bytes a fixed salt
  password: str a password
  returns: Fernet 
  
  Note: This function is deterministic so should always
  return the same cypher from the same salt and password (at least on the same machine)
  """
  kdf = PBKDF2HMAC(
    algorithm = hashes.SHA256(),
    length = 32,
    salt = salt, 
    iterations = 390000)
  return Fernet(base64.urlsafe_b64encode(kdf.derive(bytes(password, encoding='utf8'))))


def logout():
  st.session_state.enduser_id = None
  st.session_state.name = None
  st.session_state.token = None
  st.session_state.uid = None


@st.cache
def get_providers(token, country):
  """
  queries the nordigen API for compatible banks
  input: token(str?), 2-letter uppercase ISO code for a country (str)
  returns exploded pd data frame with compatible financial insitutions
  """
  res = requests.get('https://ob.nordigen.com/api/v2/institutions', 
            headers={'accept' : 'application/json', 'Authorization': "Bearer " + token }, 
            params={"country" : country})
  df = pd.DataFrame.from_dict(res.json()) 
  return df.explode("countries", ignore_index=False)


def build_link(token, institution_id, db, username):
  """§
  creates a Nordigen requisition and link for the specified institution
  stores authorisation id in the session_state.uid variable
  inputs: Nordigen token (str),institution_id  
  returns: the link needed to  
  """
  json = {
    "institution_id" : institution_id, 
    "redirect" : f"http://localhost:8501/?n={st.session_state.name}&salt={st.session_state.salt}"
  }
  res = requests.post('https://ob.nordigen.com/api/v2/requisitions/',
  headers ={'Authorization': "Bearer " + token, 'accept' : 'application/json', 'Content-Type': 'application/json'}, 
  json = json)
  #print(res.json())
  if not res.ok:
    return st.error("Sorry, something went wrong")
  # save the requisition, so we can refer back to it
  # for now we are storing the agreement in plain text. in the future we will encrypt it
  save_requisition(db, username, res.json()["id"])
  return st.info(f"Please go to the link {res.json()['link']} to autorize your bank")


def initialise_state():
  if 'name' not in st.session_state:
    st.session_state.name = None
  if "token" not in st.session_state:
    st.session_state.token = None
  if "uid" not in st.session_state:
    st.session_state.uid = None 
  if "salt" not in st.session_state:
    st.session_state.salt = None
  if "accounts" not in st.session_state:
    st.session_state.accounts = set()
  if "fernet" not in st.session_state:  
    st.session_state.fernet = None
  if "budget" not in st.session_state:
    st.session_state.budget = {}
  if "obj" not in st.session_state:
    st.session_state.obj = None
  if "avail" not in st.session_state:
    st.session_state.avail = None
  if "income" not in st.session_state:
    st.session_state.income = None
  if "transactions" not in st.session_state:
    st.session_state.transactions = {}
  
  return None

# Cacheing this is incredibly dangerous
# Gotta find some control flow 
@st.cache
def list_accounts(token, id):
  id = (id[0]) # this ISN"T R - A TOUPLE OF 1 ELEMENT IS STILL A TOUPLE, NOT A SINGLE ELEMENT
  res = requests.get(f'https://ob.nordigen.com/api/v2/requisitions/{id}/', 
            headers={'accept' : 'application/json', 'Authorization': "Bearer " + token })
  print(res.json())
  return res.json()


@st.cache
def get_transasctions(token,id, date):
  """
  the date should ensure cache is invalidated daily for a given account id and token.
  """
  res = requests.get(f'https://ob.nordigen.com/api/v2/accounts/premium/{id}/transactions', 
            headers={'accept' : 'application/json', 'Authorization': "Bearer " + token })
  return res.json()

tips={
  "Bank Fees":["", "Unarranged overdrafts", ""],
  "Cash":["Cash can be good for budgeting - just make sure you save your receipts"],
  "Entertainment":["", "Keep an eye on the refreshments "],
  "Food and Drink":["Keep an eye", "- consider taking ","Think about swapping",
   "Think", "sometimes swapping meat for plants can make your favourite dish cheaper"],
  "Health":["Hope you get well soon"],
  "Insurance":["Make sure you look around for the best deals",
   "Have you considered making some changes - you can sometimes lower your premium"],
  "Loan":["Different loans have different costs - prioritise repaying those with the highest interest",
    "Struggling to repay your loan? - Think about discussing a payment plan with your debitors"],
  "Savings and Investments":["Saving for your future - just don't forget about the present too"],
  "Services":["Have you checked your statements - maybe you", "", ""],
  "Shopping":["", "Make sure you shop around - prices for the same item may vary", ],
  "Tax":["You can often deduct some expenses to reduce your tax base", "", 
   "Have you checked your tax returns - make sure you are paying the right amount of tax", "a"],
  "Transport":["Season Tickets can be cheaper than single ticket - if you travel a lot"],
  "Travel":["Travelling a lot? - Make sure you shop around for the best deals", "", "Make sure you plan a budget for your holidays - spending can accumulate fast"],
  "Utilities":["Have had the same provider for a while - make sure you shop around for the cheapest provider", 
    "keep an eye on your bills - you may be paying off estimates", "Have you considered changing your lightbulb?"],
}

def draw_tips(n, categories, tips):
  """
  """
  pass
  
"""
def reset_budget():
  st.session_state.budget = {}
  st.session_state.avail= None 
  st.session_state.income = None
  return None
"""