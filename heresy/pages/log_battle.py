import streamlit as st
import pandas as pd
from typing import Dict, Any, List

from heresy.ui import title_plate, render_banner_once, set_banner, utc_now_iso
from heresy.auth import require_login_stop
from heresy.db import conn
from heresy.campaigns import ensure_campaign_status, get_active_campaign, campaign_time_banner
from heresy.data import df_territories, campaign_score
from heresy.config import BATTLE_TYPES
from heresy.rules import territory_neighbors, resolve_battle


def render():
    title_plate("Log a Battle", "Submit results • Cogitator updates control immediately")
    render_banner_once()
    require_login_stop()

    c = conn()
    try:
        ensure_campaign_status(c)
        camp = get_active_campaign(c)
    finally:
        c.close()

    st.info(campaign_time_banner(camp))
    if camp["status"] != "active":
        st.warning("This campaign has ended. Logging is locked until an admin starts the next campaign.")
        st.stop()

    df = df_territories()

    battle_type = st.selectbox("Battle type", list(BATTLE_TYPES.keys()), format_func=lambda k: BATTLE_TYPES[k])

    if battle_type == "gothic_armada":
        st.info("Gothic Armada battles must be logged in a **space** tile.")
        choices = df[df["is_planet"] == 0]
    else:
        st.info("Planetary battles (30k/LI/AT) must be logged on a **planet** tile.")
        choices = df[df["is_planet"] == 1]

    location_name = st.selectbox("Location", choices["name"].tolist())
    loc = choices[choices["name"] == location_name].iloc[0]
    location_id = int(loc["id"])
    loc_q, loc_r = int(loc["q"]), int(loc["r"])

    winning_side = st.radio("Result", ["loyalist", "traitor", "draw"], horizontal=True)
    is_crushing = st.checkbox("Crushing win (major victory)", value=False, disabled=(winning_side == "draw"))
    notes = st.text_area("Notes (optional)")

    # adjacency targets
    c = conn()
    try:
        cur = c.cursor()
        neighbor_rows: List[Dict[str, Any]] = []
        for nq, nr in territory_neighbors(loc_q, loc_r):
            row = cur.execute("SELECT id,name,is_planet FROM territories WHERE q=? AND r=?", (nq, nr)).fetchone()
            if row:
                neighbor_rows.append(dict(row))
    finally:
        c.close()

    splash_space_id = None
    pressure_planet_id = None

    if winning_side != "draw":
        if battle_type == "gothic_armada":
            adj_planets = [t for t in neighbor_rows if int(t["is_planet"]) == 1]
            if adj_planets:
                pick = st.selectbox(
                    "Void pressure target (optional): pick an adjacent planet to apply +1 pressure IP",
                    ["(none)"] + [t["name"] for t in adj_planets],
                )
                if pick != "(none)":
                    pressure_planet_id = int([t for t in adj_planets if t["name"] == pick][0]["id"])
            else:
                st.caption("No adjacent planets → no pressure IP available.")
        else:
            adj_space = [t for t in neighbor_rows if int(t["is_planet"]) == 0]
            if adj_space:
                pick = st.selectbox(
                    "Orbital splash target (optional): pick an adjacent space tile to apply +1 splash IP",
                    ["(none)"] + [t["name"] for t in adj_space],
                )
                if pick != "(none)":
                    splash_space_id = int([t for t in adj_space if t["name"] == pick][0]["id"])
            else:
                st.caption("No adjacent space tiles → no splash IP available.")
    else:
        st.caption("Draw selected → no CP movement, so no splash/pressure applies.")

    st.divider()

    if st.button("Log result", type="primary", use_container_width=True):
        user = st.session_state["user"]
        c = conn()
        try:
            c.execute("BEGIN")

            before_df = pd.read_sql_query("SELECT * FROM territories", c)
            before_score = campaign_score(before_df)

            c.execute(
                """
                INSERT INTO battles(
                    created_at, created_by_user_id, created_by_email,
                    battle_type, location_territory_id,
                    winning_side, is_crushing,
                    splash_target_territory_id, pressure_target_territory_id,
                    notes, status, campaign_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    utc_now_iso(),
                    int(user["id"]),
                    str(user["email"]),
                    battle_type,
                    location_id,
                    winning_side,
                    1 if is_crushing else 0,
                    splash_space_id,
                    pressure_planet_id,
                    notes,
                    "approved",
                    int(camp["id"]),
                ),
            )

            resolve_battle(
                c,
                battle_type=battle_type,
                location_id=location_id,
                winning_side=winning_side,
                is_crushing=is_crushing,
                splash_space_id=splash_space_id,
                pressure_planet_id=pressure_planet_id,
                utc_now_iso_fn=utc_now_iso,
            )

            after_df = pd.read_sql_query("SELECT * FROM territories", c)
            after_score = campaign_score(after_df)
            c.commit()

            def fmt_delta(x: int) -> str:
                return f"{x:+d}"

            set_banner(
                f"Battle logged. Loyalist {fmt_delta(after_score['loyalist']-before_score['loyalist'])} / "
                f"Traitor {fmt_delta(after_score['traitor']-before_score['traitor'])} "
                f"(Lead {fmt_delta(after_score['lead']-before_score['lead'])}). "
                f"New score: L{after_score['loyalist']}–T{after_score['traitor']}.",
                kind="success",
            )
            st.rerun()

        except Exception as e:
            c.rollback()
            set_banner(f"Could not log battle: {e}", kind="error")
            st.rerun()
        finally:
            c.close()
