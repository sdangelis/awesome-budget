import sqlite3
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
import base64
import time
from calendar import timegm

"""
DB module, for functions interacting with the SQLlite database
"""


def get_categories(db):
  c = db.cursor()
  query = c.execute("SELECT category, id FROM categories")
  query = c.fetchall()
  return dict(query)

def create_tables(db):
  c = db.cursor()  
  """
  If not already present, creates all table and indices in the provided sqlite3 db 
  returns True if successfull 
  """
  c.execute("""
    CREATE TABLE IF NOT EXISTS users
    (id INTEGER, 
    username TEXT,password TEXT, salt BLOB NOT NULL UNIQUE, PRIMARY KEY(id))
  """)
  c.execute("""CREATE TABLE IF NOT EXISTS requisitions
    (id INTEGER NOT NULL UNIQUE, users_id INTEGER NOT NULL, requisition_id TEXT,
    PRIMARY KEY(id), FOREIGN KEY(users_id) REFERENCES users(id));
  """)
  c.execute("""CREATE TABLE IF NOT EXISTS categories
    (id INTEGER NOT NULL UNIQUE, category TEXT NOT NULL, PRIMARY KEY(id))
  """)
  c.execute("""CREATE TABLE IF NOT EXISTS budget
    (id INTEGER, users_id INTEGER, categories_id INTEGER, amount NUMERIC,
    PRIMARY KEY(id), FOREIGN KEY (categories_id) REFERENCES categories(id),
    FOREIGN KEY(users_id) REFERENCES users(id))  
  """)
  c.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_id on users(id)")
  return True 

categories = {
  "Bank Fees" : 1,
  "Cash" : 2,
  "Entertainment" : 3,
  "Food and Drink" : 4,
  "Health" : 5,
  "Insurance" : 6,
  "Loan" : 7,
  "Refund" : 8,
  "Salary" : 9,
  "Savings and invesetments" : 10,
  "Services" : 11,
  "Shopping" : 12,
  "Tax" : 13,
  "Transfers" : 14,
  "Transport" : 15,
  "Travel" : 16,
  "Utilities" : 17,
  "Other" : 99
}


def validate_categories(db, categories):
  """
  TBD. BASICALY MAKES SURE THE CATEGORIES IN THE SQL TABLE MATCH WITH WHAT'S
  IN THE GIVEN CATEGORIES
  """
  c = db.cursor()  
  results = get_categories(db)
  
  # validate categories
  if not results or (dict(results) != categories):
    print("categories not good")
    for label, id in categories.items():
      c.execute("INSERT INTO categories(category,id) VALUES(?,?);",
        (label, id))
    db.commit()
  return True

def login(db, username, password):
    """
    logs user in if the password matches SQLite record in the db
    """
    c = db.cursor()
    query = c.execute("SELECT * FROM users WHERE username = ?",(username,))
    query = c.fetchall()
    if not query:
        return st.error("wrong username ") 
    if argon2.verify(password, query[0][4]):
        st.session_state.enduser_id = UUID(bytes_le = query[0][1])
        st.session_state.name = query[0][3]
        st.session_state.salt = query[0][5]
        return st.success("Logged in successfully")
    else:
        return st.error("wrong password")


def register(db, username, password):
    """
    registers a user to the SQLite databse in the db 
    returns a streamlit error if the username is already taken
    """
    c = db.cursor()
    query = c.execute("SELECT * FROM users WHERE username = ?",(username,))
    query = c.fetchall()
    if query:
        return st.error(f"User: {username} has been already registered")
    else:
        try: 
            c.execute("INSERT INTO users (enduser_id, reference, username, password, salt) VALUES(?,?,?,?,?)",
                              (uuid4().bytes_le,uuid4().bytes_le,username, argon2.hash(password), urandom(16)))
            db.commit()
            st.success(f"User: {username} registred successfully ")
            return True
        except sqlite3.IntegrityError:
            return st.error("Something has gone wrong, Please try again")


def load_budget(db, username):
  """
  returns a dictonary
  """
  c = db.cursor()
  query = c.execute("""SELECT category, amount FROM budget JOIN categories 
      ON budget.categories_id=categories.id JOIN users ON budget.users_id=users.id WHERE username = ?;
      """, (username,))
  query = c.fetchall()
  st.session_state["budget"] = dict(query)
  return True


def save_budget(budget, db, username, categories):
  """
  save budget to a,
  NEED TO USE PROPER UID
  """
  c = db.cursor()     
  
  id = c.execute("SELECT id FROM users WHERE username = ?;",(username,))
  id = c.fetchall()[0][0]

  for label,amount in budget.items():
    # check if we have it in the DB already 
    query  = c.execute("SELECT * FROM budget WHERE users_id = ? AND categories_id = ?", 
      (id, categories[label])).fetchall()
    if query:
    # if so, update
      c.execute("UPDATE budget SET amount = ? WHERE users_id = ? AND categories_id = ?", 
        (amount, id, categories[label]))
    # if not insert
    else:
      c.execute("INSERT INTO budget(users_id, categories_id, amount) VALUES(?,?,?)", 
        (id, categories[label], amount))
    
    db.commit()
  st.session_state.obj = False
  st.session_state.budget = {}
  st.success(f"Your new budget has been saved successfully ")
  
  return True


def save_requisition(db, username, requision_id):
  c = db.cursor()
    
  #get id
  c.execute("SELECT id FROM users WHERE username = ?;",(username,))
  id = c.fetchall()[0][0]
  
  #insert this requisition
  c.execute("""INSERT INTO  requisitions(users_id, requisition_id) VALUES(?,?) 
  """, (id,requision_id))
  db.commit()
  return True


def load_requisitions(db, username):
  c = db.cursor()
  c.execute("""
    SELECT Requisition_id FROM requisitions JOIN users on users.id=requisitions.users_id WHERE username = ?
    """, (username,))
  query = c.fetchall()
  return query
