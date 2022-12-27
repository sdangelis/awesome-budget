from re import L
from matplotlib import pyplot
import numpy as np
from numpy import ceil
from numpy.core.numeric import ones_like
import pandas as pd
from requests.exceptions import RequestsDependencyWarning
import streamlit as st
import requests
from os import environ
import sqlite3
from passlib.hash import argon2
from uuid import uuid4, UUID
import json
import copy
from functools import partial


# Load modules as needed

from db import *
from helpers import *

# what is going on? 

initialise_state()

"Debug feature"
st.session_state

logged = False
# get paramters from URL
params = st.experimental_get_query_params()  
if params:
  st.session_state.name = params["n"][0]
  st.session_state.salt = params["salt"][0]
params

# import api token 
SECRETS = (environ.get("NG_ID"),environ.get("NG_KEY") )

if not SECRETS:
  st.error("API KEY NOT FOUND, THIS IS A SYSTEM ERROR")
  st.stop()

if st.session_state.token == None:
  st.session_state.token = (get_token(SECRETS)["access"])

# connect DB 
conn = sqlite3.connect("awesomebudget.db",  check_same_thread=False)
create_tables(conn)

st.title("Awesome Budget \U0001F680 \U0001F4B0")

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
  st.session_state.fernet = generate_fernet(st.session_state.salt, st.session_state.token)

  # loading your accounts should happen automatically
  for requisition in load_requisitions(conn, st.session_state.name):
    for account in list_accounts(st.session_state.token, requisition)["accounts"]:
      st.session_state.accounts.add(account)
    
  if st.session_state.accounts:
    with st.expander("Your accounts:"):
      st.write(st.session_state.accounts)

  with st.expander("add a new provider:"):
    country = st.selectbox('Pick your country', ["GB", "IT", "ES", "IE"])
    providers = get_providers(st.session_state.token, country)

    banks = providers[providers['countries'] == country].name
    bank = st.selectbox("choose your bank or financial provider", list(banks))

    st.button("connect your bank", on_click = build_link, args = (st.session_state.token, 
    providers[(providers.countries == country) & (providers.name == bank)].id.to_list()[0], conn, st.session_state.name)
  )
    st.button("connect the sandbox bank (RECOMMENDED)",
      on_click = build_link, args = (st.session_state.token, "SANDBOXFINANCE_SFIN0000", conn, st.session_state.name)
    )


  st.header("your budget")

  # are the SQL categories up to date 
  validate_categories(conn, categories)
  # Load User Budget
  

  """
  NEED TO REWORK THIS TO SET WHETHER YOU ARE SETTING THE BUDGET 
  AND WHETHER YOU HAVE UNSUCCESSFULLY LOADED THE BUDGET
  """
  if st.session_state.obj:
    pass
  elif not st.session_state.budget:
    st.session_state.obj = st.button("Load your budget", on_click=load_budget, args = (conn, st.session_state.name)) 
  else:
    st.session_state.obj = st.button("Set a Budget", key = None)

  if st.session_state.obj:
    st.session_state.income = st.session_state.avail = st.number_input("what is your monthly income?", 0, step = 1)
    "your monthly income is " + str(st.session_state.avail)

    for category in categories:
      if category == "Other":
        amount = st.number_input(f"{category}",min_value = 0, value = st.session_state.avail, max_value = st.session_state.avail, step = 1, key = None)
      elif category in ["Refunds", "Salary"]:
        continue
      else:
        amount = st.number_input(f"{category}", min_value = 0, max_value = st.session_state.avail, step = 1, key = None)
      st.session_state.budget.update({category : amount})
      st.session_state.avail -= amount
    st.button("Save budget", on_click = save_budget, args = (st.session_state.budget, conn, st.session_state.name, categories))
    st.button("reset budget")
    st.button("reload budget")
  # Display budget to user 
  budget = pd.DataFrame.from_dict(st.session_state.budget, orient = "index", columns = ["Amount"])
  
  def func(pct, allvals):
    absolute = int(pct / 100. * np.sum(allvals))
    return "{:.1f}%\n({:d})".format(pct, absolute)

  budget.index.names = ['Category']
  budget.rename(columns={"index" : "amount"}, inplace=True)
  budget = budget[budget['Amount'] > 0]
  budget.sort_values("Category")

  if not budget.empty:
    budget
    plot = budget.plot.pie(y='Amount', figsize=(5, 10), subplots=False,  legend = False, autopct=lambda p: func(p,budget.iloc[:].values)).figure
    plot.legend(loc='center left', bbox_to_anchor=(1.0, 0.5)).figure

  st.header("Your Transactions")  
  

  def wrap_transactions(ids):
    with st.spinner("Loading transactions, Please wait"):
      for id in ids:
        st.session_state.transactions.update({id : get_transasctions(st.session_state.token, id, datetime.datetime.today().strftime('%Y-%m-%d'))})
      return True

  st.session_state.accounts
  st.button("Load Your Transactions", 
    on_click = wrap_transactions,
    args = (st.session_state.accounts,))
  
  transactions = []
  if st.session_state.transactions:  

    for account in st.session_state.transactions:
      frame = pd.json_normalize(st.session_state.transactions[account]["transactions"]["booked"])
      frame.rename(columns = {
        'bankTransactionCode': 'Type',
        "bookingDate" : "Date",
        "debtorName" : "Destination",
        "transactionAmount.amount" : "Amount",
        "remittanceInformationUnstructured" : "Info",
        "categorisation.categoryTitle" : "Category"
        },
        inplace=True
      )
      transactions.append(frame)
    for data in transactions: 
      st.dataframe(data[['Type', "Date", "Amount", "Category", "Destination", "Info"]], width=4000)

  if transactions:
    st.header("Your Spending and income")
    transactions = pd.concat(transactions)
    transactions["Amount"] = pd.to_numeric(transactions["Amount"], )
    income = transactions[transactions["Amount"] > 0][["Amount", "Category"]] 
    losses = transactions[transactions["Amount"] < 0][["Amount", "Category"]] 

    
    st.subheader("your income")
    income = income.groupby("Category").agg({"Amount":"sum"})
    income 
    st.subheader("your spending")
    losses = losses.groupby("Category").agg({"Amount":"sum"})
    losses
    st.header("Tips")

    #draw_tips()

  # For now this is disabled
  if False:
    # get transactions
    with st.spinner('Loading transactions - This might take some time'):
      for account in accounts.accounts: 
        raw_transactions = get_transasctions(st.session_state.token, account)
        transactions = pd.json_normalize(raw_transactions["transactions"]["booked"])
        st.dataframe(transactions)
    st.success("Transactions successfully loaded")
