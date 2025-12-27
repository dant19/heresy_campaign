import streamlit as st

from heresy.ui import title_plate, render_banner_once, set_banner
from heresy.auth import verify_login, create_user, set_login_cookie, clear_login_cookie
from heresy.config import REMEMBER_DAYS_DEFAULT


def render():
    title_plate("Account", "Sanctioned identity • Vox-verified email required")
    render_banner_once()

    tab_login, tab_create = st.tabs(["Log in", "Create account"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        remember = st.checkbox(f"Remember me ({REMEMBER_DAYS_DEFAULT} days)", value=True)

        if st.button("Log in", use_container_width=True):
            ok, user = verify_login(email, password)
            if ok:
                st.session_state["user"] = user
                if remember:
                    set_login_cookie(user, REMEMBER_DAYS_DEFAULT)
                set_banner(f"Welcome, {user['display_name']}.", kind="success")
                st.rerun()
            else:
                set_banner("Login failed. Check your email/password.", kind="error")
                st.rerun()

    with tab_create:
        email2 = st.text_input("Email", key="create_email")
        name2 = st.text_input("Display name", key="create_name")
        pw2 = st.text_input("Password (min 8 chars)", type="password", key="create_pw")
        if st.button("Create account", use_container_width=True):
            ok, msg = create_user(email2, name2, pw2)
            set_banner(msg, kind="success" if ok else "error")
            st.rerun()

    st.divider()

    if "user" in st.session_state:
        st.write(f"Signed in as **{st.session_state['user']['display_name']}**")
        st.caption(st.session_state["user"]["email"])
    else:
        st.caption("Not signed in.")

    if st.button("Log out"):
        if "user" in st.session_state:
            del st.session_state["user"]
        clear_login_cookie()
        set_banner("Logged out.", kind="info")
        st.rerun()
