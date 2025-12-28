# Heresy Campaign Tracker – Main App Page

This document describes the main Streamlit entrypoint for the Heresy campaign tracker UI.  
It covers how the page is structured, how navigation works, and what configuration is required.

---

## Overview

This module is responsible for:

- Initialising core services (DB, auth, styling).
- Rendering the top-level layout (title + sidebar navigation).
- Handling user session display (signed-in state, admin badge).
- Routing to one of the registered sub-pages.

Key imports:

- `APP_TITLE` – application title string.
- `init_db()` – initialises the database connection/schema.
- `load_user_from_cookie()` – loads the current user into `st.session_state`.
- `apply_heresy_style()` – applies custom theming to the Streamlit app.
- `page_*` render functions – one per logical page of the app.
- `is_admin_user()` – returns `True` if the active user is an admin.
- `AUTH_SECRET` – secret used for secure authentication cookies.

---

## Page Registry

All navigable pages are defined in a simple dictionary:

PAGES = {
"Dashboard": page_dashboard,
"Log Battle": page_log_battle,
"Recent Battles": page_recent_battles,
"Rules": page_rules,
"Campaign Admin": page_campaign_admin,
"Account": page_account,
}

sql
Copy code

- **Keys** are the page names shown in the UI.
- **Values** are callables (render functions) imported from `heresy.pages.*`.

When the user selects a page in the sidebar, the associated function is called:

PAGESpage # render selected page

markdown
Copy code

### Adding a New Page

1. Implement a `render()` function in a module under `heresy.pages`.
2. Import it here:

from heresy.pages.my_new_page import render as page_my_new_page


3. Register it in the `PAGES` dict:

PAGES["My New Page"] = page_my_new_page

yaml
Copy code

The page will then appear automatically in the sidebar navigation.

---

## Application Lifecycle (`main()`)

def main():
st.set_page_config(page_title=APP_TITLE, layout="wide")
apply_heresy_style()
init_db()
load_user_from_cookie()

python-repl
Copy code
st.title(APP_TITLE)
...
markdown
Copy code

The `main()` function performs the following steps:

1. **Page config**  
   - Sets the browser tab title to `APP_TITLE`.
   - Uses a `"wide"` layout for more horizontal space.

2. **Styling**  
   - Calls `apply_heresy_style()` to inject the custom Heresy theme (fonts, colours, CSS overrides, etc.).

3. **Database initialisation**  
   - Calls `init_db()` to ensure the database is ready before any page logic runs.

4. **Authentication loading**  
   - Calls `load_user_from_cookie()` to:
     - Read auth cookies.
     - Look up the user.
     - Populate `st.session_state["user"]` if a user is logged in.

5. **Main title**  
   - Displays the app title at the top of the main content area via `st.title(APP_TITLE)`.

---

## Sidebar & Navigation

The sidebar is responsible for:

- Showing navigation controls.
- Displaying current user information.
- Exposing admin/environment hints.

with st.sidebar:
st.subheader("Navigation")
page = st.radio("Go to", list(PAGES.keys()), label_visibility="collapsed")
...

vbnet
Copy code

### Navigation Control

- A `st.radio` widget is used to select one of the available pages.
- The label `"Go to"` is hidden (`label_visibility="collapsed"`) for a cleaner UI.
- The options are generated from `PAGES.keys()`, so any new page appears automatically.

The selected page name is stored in `page`, which is then used to call the appropriate render function:

PAGESpage

yaml
Copy code

---

## Authentication & Session Display

After navigation, the sidebar shows current user status:

if "user" in st.session_state:
st.write(f"Signed in: {st.session_state['user']['display_name']}")
st.caption(st.session_state["user"]["email"])
if is_admin_user():
st.caption("Role: Admin")
else:
st.write("Signed in: (not yet)")
st.caption("Create an account to log results.")

markdown
Copy code

- If `st.session_state["user"]` exists (set by `load_user_from_cookie()`):
  - Shows the user’s display name in bold.
  - Shows their email as a caption.
  - If `is_admin_user()` returns `True`, an additional `"Role: Admin"` caption is shown.
- If no user is present:
  - Indicates the user is not yet signed in.
  - Prompts them to create an account to log results.

### Admin Hint

Below the user info, a small admin tip is displayed:

st.caption("Tip: Set ADMIN_EMAILS to allow campaign admins to delete any battle.")

yaml
Copy code

- The environment/config value `ADMIN_EMAILS` is used elsewhere in the codebase.
- It determines which users have campaign admin permissions (for actions like deleting any battle).

---

## Security Configuration (`AUTH_SECRET`)

The app checks whether `AUTH_SECRET` is configured:

if not AUTH_SECRET:
st.warning("AUTH_SECRET is not set (cookies will be insecure).")

yaml
Copy code

- `AUTH_SECRET` should be set to a strong, random secret value in your environment/config.
- It is used for signing or encrypting authentication cookies.
- If not set, the app warns that cookies will be insecure.

**Recommended:**

- Set `AUTH_SECRET` in your environment (e.g. `.env` file or deployment configuration).
- Keep this value secret and stable between restarts during a campaign so existing sessions remain valid.

---

## Environment / Configuration Summary

The main app page expects several configuration values:

- `APP_TITLE`  
  String, used for both the page title and top-level UI title.

- `AUTH_SECRET`  
  String, required for secure auth cookies.  
  If missing, a warning is shown in the sidebar.

- `ADMIN_EMAILS` (mentioned in the UI tip, configured elsewhere)  
  Typically a comma-separated list of admin email addresses.  
  Used to grant campaign admin capabilities (e.g. delete any battle).  
  Ensure that the email used to log in exactly matches one of these entries.

---

## Running the App

Assuming this module is your Streamlit entrypoint, you can run it with:

streamlit run <this_file>.py

markdown
Copy code

Make sure you have:

- Installed all dependencies (including `streamlit` and the `heresy` package).
- Set the relevant environment variables, for example:

export APP_TITLE="Heresy Campaign Tracker"
export AUTH_SECRET="a-strong-random-secret"
export ADMIN_EMAILS="admin1@example.com,admin2@example.com"

graphql
Copy code

On Windows (PowerShell):

$env:APP_TITLE = "Heresy Campaign Tracker"
$env:AUTH_SECRET = "a-strong-random-secret"
$env:ADMIN_EMAILS = "admin1@example.com,admin2@example.com"
streamlit run .<this_file>.py

markdown
Copy code

---

## Control Flow Summary

1. `main()` sets up the page, styles, DB, and user session.
2. The app title is rendered in the main content area.
3. The sidebar:
   - Shows navigation options based on `PAGES`.
   - Displays signed-in user info (if any).
   - Marks admin users.
   - Provides configuration hints/warnings.
4. The selected page’s render function is called from `PAGES[page]`.
5. If run directly (`__name__ == "__main__"`), `main()` is executed.

This structure keeps the top-level app simple and centralises navigation and shared initialisation logic in a single place.






