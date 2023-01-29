import streamlit as st
from os import environ, path
from src.utils import create_tables
from src.st_helpers import auth_wrapper, init_state, cache_wrapper
from src.open_banking import (
    generate_fernet,
    load_token,
    request_token,
    save_token,
    load_requisitions,
    create_requisition,
    save_requisition,
)

from src.autentication import (
    AlreadyRegistredError,
    AuthenticationError,
    login,
    register,
)

SECRETS = (environ.get("NG_ID"), environ.get("NG_KEY"))

st.title("Awesome Budget \U0001F680 \U0001F4B0")

create_tables()
init_state(SECRETS)
auth_wrapper()

try:
    st.session_state.token = load_token(
        generate_fernet(SECRETS[0].encode("UTF-8"), SECRETS[1],)
    )
except:
    st.session_state.token = request_token(*SECRETS)
    save_token(
        st.session_state.token, generate_fernet(SECRETS[0].encode("UTF-8"), SECRETS[1])
    )

