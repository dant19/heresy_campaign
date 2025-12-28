import streamlit as st
from datetime import date, timedelta

from heresy.ui import title_plate, render_banner_once, set_banner
from heresy.auth import require_login_stop, is_admin_user
from heresy.db import conn
from heresy.campaigns import ensure_campaign_status, get_active_campaign, campaign_time_banner, admin_reset_campaign

from heresy.auth import is_admin
from heresy.ui import title_plate, set_banner, render_banner_once
from heresy.db import conn
from heresy.campaigns import (
    ensure_campaign_status,
    get_active_campaign,
    campaign_time_banner,
    admin_reset_campaign,
)

def render():
    title_plate("Campaign Admin", "Start/End campaign windows • Reset map • Admin only")
    render_banner_once()
    require_login_stop()

    if not is_admin_user():
        st.error("Admins only.")
        st.stop()

    c = conn()
    try:
        ensure_campaign_status(c)
        camp = get_active_campaign(c)
    finally:
        c.close()

    st.info(campaign_time_banner(camp))

    st.subheader("Start a new campaign (resets map CP)")
    new_name = st.text_input("New campaign name", value="Campaign Season 2")
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start date", value=date.today())
    with col2:
        end = st.date_input("End date", value=date.today() + timedelta(days=90))

    if st.button("Start new campaign (reset map)", type="primary"):
        if end < start:
            st.error("End date must be after start date.")
        else:
            admin_reset_campaign(new_name, start.isoformat(), end.isoformat())
            set_banner(f"New campaign started: {new_name} ({start} → {end}). Map reset.", kind="success")
            st.rerun()

import streamlit as st


def page_admin_campaign_control():
    if not is_admin():
        st.warning("Admins only.")
        st.stop()

    title_plate("Admin: Campaign Control", "Start/End campaign seasons • Reset map when ready")
    render_banner_once()

    c = conn()
    try:
        ensure_campaign_status(c)
        camp = get_active_campaign(c)
    finally:
        c.close()

    st.info(campaign_time_banner(camp))

    if camp["status"] == "active":
        st.warning("Campaign is active. Starting a new one will reset the map CP.")
    else:
        st.success("Campaign ended. You can start the next season when ready.")

    new_name = st.text_input("New campaign name", value="Campaign Season 2")
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start date")
    with col2:
        end = st.date_input("End date")

    if st.button("Start new campaign (reset map)", type="primary"):
        if end < start:
            st.error("End date must be after start date.")
            return

        admin_reset_campaign(new_name, start.isoformat(), end.isoformat())
        set_banner(f"New campaign started: {new_name} ({start} → {end}). Map reset.", kind="success")
        st.rerun()
