import streamlit as st
import pandas as pd
from typing import List

from heresy.ui import title_plate, render_banner_once, set_banner
from heresy.auth import require_login_stop
from heresy.db import conn
from heresy.campaigns import ensure_campaign_status, get_active_campaign, campaign_time_banner
from heresy.data import df_battles, reset_all_cp
from heresy.config import BATTLE_TYPES, SIDE_LABELS, admin_emails
from heresy.rules import resolve_battle
from heresy.ui import utc_now_iso


def can_delete_battle(current_user_email: str, battle_created_by_email: str) -> bool:
    cu = (current_user_email or "").strip().lower()
    owner = (battle_created_by_email or "").strip().lower()
    if cu and cu == owner:
        return True
    return cu in admin_emails()


def render():
    title_plate("Recent Battles", "Audit trail • Editable removals with full recalculation")
    render_banner_once()
    require_login_stop()

    c = conn()
    try:
        ensure_campaign_status(c)
        camp = get_active_campaign(c)
    finally:
        c.close()

    st.info(campaign_time_banner(camp))

    df = df_battles(campaign_id=int(camp["id"]), limit=400)
    if df.empty:
        st.info("No battles logged yet for this campaign.")
        return

    show = df.copy()
    show["created_at"] = pd.to_datetime(show["created_at"], errors="coerce")
    show["battle_type"] = show["battle_type"].map(BATTLE_TYPES).fillna(show["battle_type"])
    show["winning_side"] = show["winning_side"].map(SIDE_LABELS).fillna(show["winning_side"])
    show["is_crushing"] = show["is_crushing"].astype(int).astype(bool)
    show.insert(0, "Delete?", False)

    st.caption(
        "To remove battles: tick rows → click **Delete selected & recalculate**. "
        "Only creators can delete their own entries unless you’re listed in ADMIN_EMAILS."
    )

    edited = st.data_editor(
        show[["Delete?", "id", "created_at", "created_by_email", "battle_type", "location_name", "winning_side", "is_crushing", "notes"]],
        use_container_width=True,
        hide_index=True,
        disabled=["id", "created_at", "created_by_email", "battle_type", "location_name", "winning_side", "is_crushing", "notes"],
        column_config={
            "Delete?": st.column_config.CheckboxColumn("Delete?", help="Mark battle for deletion", default=False),
            "id": st.column_config.NumberColumn("ID", format="%d"),
        },
        key="battles_editor",
    )

    to_delete = edited[edited["Delete?"] == True]["id"].tolist()  # noqa: E712
    colA, colB = st.columns([1, 1])
    with colA:
        st.write(f"Marked for deletion: **{len(to_delete)}**")
    with colB:
        confirm = st.checkbox("I understand this will recalculate all CP from remaining battles.", value=False)

    current_email = st.session_state["user"]["email"]

    if st.button("Delete selected & recalculate", type="primary", use_container_width=True, disabled=(not to_delete or not confirm)):
        c = conn()
        try:
            c.execute("BEGIN")

            qmarks = ",".join(["?"] * len(to_delete))
            rows = c.execute(
                f"SELECT id, created_by_email FROM battles WHERE id IN ({qmarks}) AND campaign_id=?",
                tuple(to_delete) + (int(camp["id"]),),
            ).fetchall()

            denied: List[int] = []
            allowed_ids: List[int] = []
            for r in rows:
                if can_delete_battle(current_email, r["created_by_email"]):
                    allowed_ids.append(int(r["id"]))
                else:
                    denied.append(int(r["id"]))

            if denied and not allowed_ids:
                c.rollback()
                set_banner(f"Deletion denied for battle IDs: {denied}. You can only delete your own battles.", kind="error")
                st.rerun()

            if denied and allowed_ids:
                set_banner(f"Some deletions denied (IDs: {denied}). Deleting allowed selections and recalculating.", kind="info")

            if allowed_ids:
                qmarks2 = ",".join(["?"] * len(allowed_ids))
                c.execute(f"DELETE FROM battles WHERE id IN ({qmarks2}) AND campaign_id=?", tuple(allowed_ids) + (int(camp["id"]),))

                # Recompute for this campaign only
                reset_all_cp(c)
                rows2 = c.execute(
                    """
                    SELECT
                      battle_type, location_territory_id, winning_side, is_crushing,
                      splash_target_territory_id, pressure_target_territory_id
                    FROM battles
                    WHERE status='approved' AND campaign_id=?
                    ORDER BY id ASC
                    """,
                    (int(camp["id"]),),
                ).fetchall()

                for r2 in rows2:
                    resolve_battle(
                        c,
                        battle_type=r2["battle_type"],
                        location_id=r2["location_territory_id"],
                        winning_side=r2["winning_side"],
                        is_crushing=bool(int(r2["is_crushing"])),
                        splash_space_id=r2["splash_target_territory_id"],
                        pressure_planet_id=r2["pressure_target_territory_id"],
                        utc_now_iso_fn=utc_now_iso,
                    )

                c.commit()
                set_banner(f"Deleted {len(allowed_ids)} battle(s) and recalculated.", kind="success")
                st.rerun()

        except Exception as e:
            c.rollback()
            set_banner(f"Delete/recalc failed: {e}", kind="error")
            st.rerun()
        finally:
            c.close()
