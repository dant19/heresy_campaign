import streamlit as st

from heresy.ui import title_plate, render_banner_once
from heresy.db import conn
from heresy.campaigns import ensure_campaign_status, get_active_campaign, campaign_time_banner
from heresy.data import df_territories, campaign_score
from heresy.rules import side_from_cp, status_from_cp
from heresy.map_viz import HexGeom, make_map


def render():
    title_plate("Campaign Dashboard", "Vox-verified control tallies • Planets & void lanes")
    render_banner_once()

    c = conn()
    try:
        ensure_campaign_status(c)
        camp = get_active_campaign(c)
    finally:
        c.close()

    st.info(campaign_time_banner(camp))

    df = df_territories()
    score = campaign_score(df)

    c1, c2, c3 = st.columns(3)
    c1.metric("Loyalist Score", score["loyalist"])
    c2.metric("Traitor Score", score["traitor"])
    lead = score["lead"]
    c3.metric("Lead", lead, delta=("Loyalist" if lead > 0 else "Traitor" if lead < 0 else "Tied"))

    st.caption("Score weights planets higher than space. Control counts when Held/Secure (|CP| ≥ 3).")

    fig = make_map(df, HexGeom(size=1.0, pointy_top=True))
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": False, "doubleClick": False, "displayModeBar": False, "responsive": True})

    with st.expander("Territories table"):
        show = df.copy()
        show["side"] = show["cp"].apply(side_from_cp)
        show["status"] = show["cp"].apply(status_from_cp)
        st.dataframe(show[["name", "is_planet", "cp", "side", "status", "q", "r"]], use_container_width=True)
