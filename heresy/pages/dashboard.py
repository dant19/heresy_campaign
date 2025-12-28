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

    loyalist_score = score["loyalist"]
    traitor_score = score["traitor"]
    lead = score["lead"]          # +ve = Loyalists ahead, -ve = Traitors ahead
    total = loyalist_score + traitor_score
    max_range = max(total, 1)

    # ---------- STYLE: Make slider visual ----------
    st.markdown(
        """
        <style>
        /* Larger label text */
        .campaign-label {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 6px;
        }

        /* Streamlit slider track styling */
        div[data-baseweb="slider"] > div {
            background: linear-gradient(
                90deg,
                #a00000 0%,
                #5e0000 20%,
                #333333 50%,
                #1f3fff 80%,
                #0044ff 100%
            ) !important;
            height: 12px !important;
            border-radius: 6px !important;
        }

        /* Hide numeric popover */
        div[data-baseweb="slider"] span {
            font-size: 1.1rem !important;
            font-weight: 700 !important;
        }

        /* Thumb styling */
        div[data-baseweb="slider"] div[role="slider"] {
            background: #ffffff !important;
            border: 3px solid #000000 !important;
            width: 22px !important;
            height: 22px !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

    # ---------- READ-ONLY BALANCE SLIDER ----------
    st.markdown(
        '<div class="campaign-label">Campaign Balance — Traitor  vs  Loyalist ⟶</div>',
        unsafe_allow_html=True,
    )

    slider_key = f"campaign_balance_{lead}"

    st.slider(
        "",
        min_value=-max_range,
        max_value=max_range,
        value=lead,
        step=1,
        disabled=True,
        key=slider_key,
    )

    st.caption(
        f"Loyalist: {loyalist_score} • "
        f"Traitor: {traitor_score} • "
        f"Lead: {abs(lead)} "
        f"({ 'Loyalist' if lead > 0 else 'Traitor' if lead < 0 else 'Tied' })"
    )

    st.caption("Score weights planets higher than space. Control counts when Held/Secure (|CP| ≥ 3).")

    fig = make_map(df, HexGeom(size=1.0, pointy_top=True))
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": False,
            "doubleClick": False,
            "displayModeBar": False,
            "responsive": True,
        },
    )

    with st.expander("Territories table"):
        show = df.copy()
        show["side"] = show["cp"].apply(side_from_cp)
        show["status"] = show["cp"].apply(status_from_cp)
        st.dataframe(
            show[["name", "is_planet", "cp", "side", "status", "q", "r"]],
            use_container_width=True,
        )
