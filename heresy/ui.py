from datetime import datetime, timezone
import streamlit as st


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_heresy_style() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;800&family=IM+Fell+English:ital@0;1&display=swap');

        :root{
          --bg0:#07070a;
          --panel:#10111a;
          --ink:#f0eadc;
          --ink2:#d7cfbf;
          --red:#b30000;
          --gold:#b89b5e;
          --border: rgba(184,155,94,.25);
          --shadow: 0 14px 40px rgba(0,0,0,.35);
          --glow: 0 0 0.6rem rgba(179,0,0,.25);
        }

        [data-testid="stHeader"]{
          background: rgba(0,0,0,0) !important;
          box-shadow: none !important;
        }

        .stApp{
          background:
            radial-gradient(1200px 700px at 30% 10%, rgba(179,0,0,.10), transparent 55%),
            radial-gradient(900px 500px at 85% 35%, rgba(184,155,94,.08), transparent 60%),
            linear-gradient(180deg, var(--bg0), #05050a 65%, #030308);
          color: var(--ink) !important;
        }

        html, body, p, span, div, li, label,
        .stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown div,
        [data-testid="stMarkdownContainer"] *{
          color: var(--ink) !important;
        }
        .stCaption, [data-testid="stCaptionContainer"], small{
          color: var(--ink2) !important;
          opacity: 0.95 !important;
        }

        h1,h2,h3,h4,h5{
          font-family: "Cinzel", "Times New Roman", serif !important;
          letter-spacing: .6px;
          color: var(--ink) !important;
        }
        html, body, [class*="css"]{
          font-family: "IM Fell English", Georgia, serif !important;
        }

        section[data-testid="stSidebar"]{
          background: linear-gradient(180deg, #0b0c12, #07070a) !important;
          border-right: 1px solid rgba(184,155,94,.22) !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]{
          border: 1px solid rgba(184,155,94,.18) !important;
          background: linear-gradient(180deg, rgba(16,17,26,.82), rgba(10,11,16,.82)) !important;
          box-shadow: var(--shadow) !important;
          border-radius: 14px !important;
        }

        .stTextInput input, .stTextArea textarea{
          background: rgba(10,11,16,.90) !important;
          border: 1px solid var(--border) !important;
          color: var(--ink) !important;
          caret-color: var(--ink) !important;
          border-radius: 10px !important;
        }

        div[data-baseweb="select"] > div{
          background: rgba(10,11,16,.92) !important;
          border: 1px solid var(--border) !important;
          border-radius: 10px !important;
          box-shadow: 0 10px 25px rgba(0,0,0,.25) !important;
        }
        div[data-baseweb="select"] *{
          color: var(--ink) !important;
        }

        @media (pointer: fine) {
          div[data-baseweb="popover"] li[role="option"],
          div[data-baseweb="popover"] li[role="option"] *,
          ul[role="listbox"] li,
          ul[role="listbox"] li * { color: #111 !important; }
        }

        @media (pointer: coarse) {
          div[data-baseweb="popover"],
          ul[role="listbox"] { background: rgba(12,12,18,0.98) !important; }

          div[data-baseweb="popover"] li[role="option"],
          div[data-baseweb="popover"] li[role="option"] *,
          ul[role="listbox"] li,
          ul[role="listbox"] li * { color: #f0eadc !important; }
        }

        .stButton button{
          background: linear-gradient(180deg, #c20000, #7a0000) !important;
          border: 1px solid rgba(184,155,94,.35) !important;
          box-shadow: var(--glow) !important;
          border-radius: 12px !important;
          color: #fff !important;
          font-weight: 800 !important;
          letter-spacing: .4px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def title_plate(text: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div style="
          padding:14px 18px;
          border-radius:14px;
          border:1px solid rgba(184,155,94,.30);
          background: linear-gradient(90deg, rgba(179,0,0,.20), rgba(16,17,26,.65));
          box-shadow: 0 14px 40px rgba(0,0,0,.35);
          margin-bottom: 12px;">
          <div style="font-family:Cinzel, serif; font-weight:800; font-size:1.35rem; letter-spacing:.8px; color: #f0eadc;">
            {text}
          </div>
          <div style="opacity:.92; margin-top:2px; color: #d7cfbf;">
            {subtitle}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def set_banner(message: str, *, kind: str = "success") -> None:
    st.session_state["banner"] = {"message": message, "kind": kind, "ts": utc_now_iso()}


def render_banner_once() -> None:
    payload = st.session_state.get("banner")
    if not payload:
        return

    msg = payload.get("message", "")
    kind = payload.get("kind", "info")
    icon = {"success": "✅", "error": "⛔", "info": "📣"}.get(kind, "📣")

    st.markdown(
        f"""
        <style>
        .heresy-banner {{
            width: 100%;
            padding: 14px 18px;
            border-radius: 12px;
            color: #fff;
            border: 1px solid rgba(255,255,255,0.18);
            box-shadow: 0 10px 30px rgba(179,0,0,0.30);
            overflow: hidden;
            background:
              repeating-linear-gradient(
                45deg,
                #7a0000 0px,
                #7a0000 14px,
                #b30000 14px,
                #b30000 28px
              );
        }}
        .heresy-banner .txt {{
            font-size: 1.02rem;
            line-height: 1.25rem;
            font-weight: 900;
            letter-spacing: 0.4px;
            text-shadow: 0 2px 12px rgba(0,0,0,0.35);
        }}
        </style>
        <div class="heresy-banner"><div class="txt">{icon} {msg}</div></div>
        """,
        unsafe_allow_html=True,
    )

    del st.session_state["banner"]
