import streamlit as st

from heresy.config import APP_TITLE
from heresy.db import init_db
from heresy.auth import load_user_from_cookie
from heresy.ui import apply_heresy_style
from heresy.pages.dashboard import render as page_dashboard
from heresy.pages.log_battle import render as page_log_battle
from heresy.pages.recent_battles import render as page_recent_battles
from heresy.pages.rules_page import render as page_rules
from heresy.pages.campaign_admin import render as page_campaign_admin
from heresy.pages.account import render as page_account
from heresy.auth import is_admin_user
from heresy.config import AUTH_SECRET


PAGES = {
    "Dashboard": page_dashboard,
    "Log Battle": page_log_battle,
    "Recent Battles": page_recent_battles,
    "Rules": page_rules,
    "Campaign Admin": page_campaign_admin,
    "Account": page_account,
}


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    apply_heresy_style()
    init_db()
    load_user_from_cookie()

    st.title(APP_TITLE)
    st.caption("A narrative campaign for the Horus Heresy, by Hutton Hearthguards")

    with st.sidebar:
        st.subheader("Navigation")
        page = st.radio("Go to", list(PAGES.keys()), label_visibility="collapsed")

        st.divider()
        if "user" in st.session_state:
            st.write(f"**Signed in:** {st.session_state['user']['display_name']}")
            st.caption(st.session_state["user"]["email"])
            if is_admin_user():
                st.caption("Role: Admin")
        else:
            st.write("**Signed in:** (not yet)")
            st.caption("Create an account to log results.")

        st.divider()
        st.caption("Tip: Set ADMIN_EMAILS to allow campaign admins to delete any battle.")
        if not AUTH_SECRET:
            st.warning("AUTH_SECRET is not set (cookies will be insecure).")

    PAGES[page]()  # render selected page


if __name__ == "__main__":
    main()
