from matplotlib import pyplot
from numpy import ceil
import pandas as pd
import streamlit as st
import requests
from helpers import create_tables
from os import environ
import sqlite3
from passlib.hash import argon2
from uuid import uuid4, UUID



# import api token 
TOKEN = environ.get("NG_TOKEN")

if not TOKEN:
  st.error("API KEY NOT FOUND, THIS IS A SYSTEM ERROR")
  st.stop()
  
# initialise user state 
if 'user' not in st.session_state:
    st.session_state.user = None
if "enduser_id" not in st.session_state:
    st.session_state.enduser_id = None

# connect DB 
conn = sqlite3.connect("awesomebudget.db",  check_same_thread=False)
create_tables(conn)

st.title("Awesome Budget \U0001F680 \U0001F4B0")

# initialise user state 
if 'name' not in st.session_state:
    st.session_state.name = None
if "enduser_id" not in st.session_state:
    st.session_state.enduser_id = None
if "reference" not in st.session_state:
    st.session_state.reference = None


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
    logs user in
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

logged = None

# if the user is not logged in, allow user to log in or register
if not st.session_state.name:
  with st.form(key='login', clear_on_submit=False):
    user = st.text_input(label='Username')
    password = st.text_input(label='password', type="password")
    logging_in = st.form_submit_button(label='login') #, on_click=login, args=(conn, user, password),   )
    register_sub = st.form_submit_button(label='register') #, on_click=register, args=(conn, user, password))
  
  if logging_in:
    loggged = login(conn, user, password)
  elif register_sub:
    register(conn, user, password)

if st.session_state.name:
  st.subheader(f"Welcome {st.session_state.name}!")
  st.button(label='logout',on_click=logout)

@st.cache
def get_providers(token):
  res = requests.get('https://ob.nordigen.com/api/aspsps/', 
             headers={'Authorization': "token " + token, 'accept' : 'application/json'}, 
            params="")
  df = pd.DataFrame.from_dict(res.json()) 
  return df.explode("countries", ignore_index=False)

@st.cache
def create_requisition(token, enduser_id, reference, country):
  json = {'reference' : reference.hex, 'enduser_id' : enduser_id.hex, 
    "user_language" : country,
    "redirect" : "http://localhost:8502"
    }
  res = requests.post('https://ob.nordigen.com/api/requisitions/',
  headers={'Authorization': "token " + token, 'accept' : 'application/json', 'Content-Type': 'application/json'}, 
  json = json )
  return res.json()

@st.cache
def delete_requisition(token, requsition):
  json = {'reference' : reference.hex, 'enduser_id' : enduser_id.hex, 
    "user_language" : country,
    "redirect" : "http://localhost:8502"
    }
  res = requests.post('https://ob.nordigen.com/api/requisitions/',
  headers={'Authorization': "token " + token, 'accept' : 'application/json', 'Content-Type': 'application/json'}, 
  json = json )
  return res.json()

if st.session_state.name:
  
  providers = get_providers(TOKEN)
  country = st.selectbox('Pick your country', list(providers.countries.unique()))

  banks = providers[providers['countries'] == country].name

  bank = st.selectbox("choose your bank or financial provider", list(banks))
  if not bank:
    requisition = create_requisition(TOKEN, st.session_state.enduser_id, st.session_state.reference, country)
    st.text(requisition["detail"])

