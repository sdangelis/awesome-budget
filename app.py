from matplotlib import pyplot
from numpy import ceil
from numpy.core.numeric import ones_like
import pandas as pd
from requests.exceptions import RequestsDependencyWarning
import streamlit as st
import requests
from helpers import create_tables
from os import environ
import sqlite3
from passlib.hash import argon2
from uuid import uuid4, UUID

# initialise user state 
if 'name' not in st.session_state:
    st.session_state.name = None
if "enduser_id" not in st.session_state:
    st.session_state.enduser_id = None
if "reference" not in st.session_state:
    st.session_state.reference = None
# In theory this should really be a CONSTANT.
if "token" not in st.session_state:
    st.session_state.token = None
if "id" not in st.session_state:
  st.session_state.id = None


# import api token 
TOKEN = environ.get("NG_TOKEN")
SECRETS = (environ.get("NG_ID"),environ.get("NG_KEY") )

if not SECRETS:
  st.error("API KEY NOT FOUND, THIS IS A SYSTEM ERROR")
  st.stop()
  
# connect DB 
conn = sqlite3.connect("awesomebudget.db",  check_same_thread=False)
create_tables(conn)

@st.cache
def get_token(secrets):
  """
  Get token
  input:
  returns: the json request 
  TO-DO: need to find a way to capture if token is expired and in that 
  case ask for renewal. Need to add token and expiry date to databse.
  issue here is should the token be unencrypted? 
  could encript it with the secrets as key as to keep everything safe
  As in theory secrets should only be accessible in RAM (bash history disagrees) 
  """
  json = {'secret_id' : secrets[0], 'secret_key' : secrets[1], 
    }
  res = requests.post('https://ob.nordigen.com/api/v2/token/new/',
  headers={'accept' : 'application/json', 'Content-Type': 'application/json'}, 
  json = json )
  return res.json()

st.session_state.token = (get_token(SECRETS)["access"])

st.title("Awesome Budget \U0001F680 \U0001F4B0")


# autentication functions

def register(connection, username, password):
    """
    registers a user to the SQLite databse in the connection 
    returns a streamlit error if the username is already taken
    """
    c = connection.cursor()
    query = c.execute("SELECT * FROM users WHERE username = ?",(username,))
    query = c.fetchall()
    if query:
        return st.error(f"User: {user} has been already registered")
    else:
        try: 
            c.execute("INSERT INTO users (enduser_id, reference, username, password) VALUES(?,?,?,?)",
                              (uuid4().bytes_le,uuid4().bytes_le,username, argon2.hash(password)))
            connection.commit()
            st.success(f"User: {user} registred successfully ")
            return 
        except sqlite3.IntegrityError:
            return st.error("Something has gone wrong, Please try again")

def login(connection, username, password):
    """
    logs user in if the password matches SQLite record in the connection
    """
    c = connection.cursor()
    query = c.execute("SELECT * FROM users WHERE username = ?",(username,))
    query = c.fetchall()
    if not query:
        return st.error("wrong username ") 
    if argon2.verify(password, query[0][4]):
        st.session_state.enduser_id = UUID(bytes_le = query[0][1])
        st.session_state.reference = UUID(bytes_le = query[0][2])
        st.session_state.name = query[0][3]
        return st.success("Logged in successfully")
    else:
        return st.error("wrong password")

def logout():
  st.session_state.enduser_id = None
  st.session_state.reference = None
  st.session_state.name = None
  st.session_state.token = None
  st.session_state.id = None

logged = None

# if the user is not logged in, allow user to log in or register
if not st.session_state.name:
  with st.form(key='login', clear_on_submit=False):
    user = st.text_input(label='Username')
    password = st.text_input(label='password', type="password")
    logging_in = st.form_submit_button(label='login') #, on_click=login, args=(conn, user, password),   )
    register_sub = st.form_submit_button(label='register') #, on_click=register, args=(conn, user, password))
  
  # NOTE: it looks like this is the way to work around the need for sumbitting 
  # the form twice when using callbacks 
  if logging_in:
    loggged = login(conn, user, password)
  elif register_sub:
    register(conn, user, password)

if st.session_state.name:
  st.subheader(f"Welcome {st.session_state.name}!")
  st.button(label='logout',on_click=logout)

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

def build_link(token, institution_id):
  """
  creates a Nordigen requisition and link for the specified institution
  stores autorisation id in the session_state.id variable
  inputs: Nordigen token (str),institution_id  
  returns: the link needed to  
  """
  json = {
    "institution_id" : institution_id, 
    "redirect" : "http://localhost:8501"
    }
  res = requests.post('https://ob.nordigen.com/api/v2/requisitions/',
  headers ={'Authorization': "Bearer " + token, 'accept' : 'application/json', 'Content-Type': 'application/json'}, 
  json = json)
  print(res.json())
  if not res.ok:
    return st.error("Sorry, something went wrong")
  st.session_state.id = res.json()["id"]
  return st.info(f"Please go to the link {res.json()['link']} to autorize your bank")


# If the user is logged in, run the rest of app

if st.session_state.name:
  
  country = st.selectbox('Pick your country', ["GB"])
  providers = get_providers(st.session_state.token, country)

  banks = providers[providers['countries'] == country].name

  bank = st.selectbox("choose your bank or financial provider", list(banks))
  print(providers[(providers.countries == country) & (providers.name == bank)].id.to_list()[0])
  
  # At the moment this step is stuck here. 
  # need to find a way to create unique 
  st.button("connect your bank", on_click=build_link, args=(st.session_state.token, 
    providers[(providers.countries == country) & (providers.name == bank)].id.to_list()[0])
  )

  
