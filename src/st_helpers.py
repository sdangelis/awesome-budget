import streamlit as st
from typing import Callable
from src.autentication import (
    AlreadyRegistredError,
    AuthenticationError,
    login,
    register,
)
from src.open_banking import generate_fernet


def auth_wrapper():
    if st.session_state.auth:
        if st.button(
            "Logout",
            on_click=st.warning,
            args=(f"User: {st.session_state.auth[1]} has been logged out. Goodbye!",),
        ):
            reset_state()
            st.experimental_rerun()
        return
    credentials = login_form()
    try:
        if st.session_state["FormSubmitter:login-login"]:
            # If we have asked for login
            st.session_state.auth = login(*credentials)
            st.experimental_rerun()
        elif st.session_state["FormSubmitter:login-register"]:
            register(*credentials)
    except (AuthenticationError, AlreadyRegistredError, ValueError) as e:
        st.error(e)


def init_state(SECRETS):
    if "auth" not in st.session_state:
        st.session_state["auth"] = None
    if "token" not in st.session_state:
        st.session_state["token"] = None
    if "fernet" not in st.session_state:
        st.session_state.fernet = generate_fernet(
            SECRETS[0].encode("UTF-8"), SECRETS[1],
        )


def reset_state():
    st.session_state.auth = None


@st.cache()
def cache_wrapper(f, *args, **kwargs):
    return f(*args, **kwargs)


def login_form() -> tuple:
    with st.form(key="login", clear_on_submit=False):
        user = st.text_input(label="Username")
        password = st.text_input(label="password", type="password")
        st.form_submit_button(label="login")
        st.form_submit_button(label="register")
    return (user, password)

