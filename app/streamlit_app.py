"""
Munchr — Streamlit Web App
Your AI-powered cooking companion.

This is the main entry point of the Munchr app. It uses Streamlit to
render a single-page web app with two views:
  1. Search View (default) — hero title, search bar, recipe card grid
  2. Recipe Detail View    — full recipe with ingredients, instructions, and AI assistant

The app uses custom CSS to override Streamlit’s default styling with:
  - Roboto Mono font (Google Fonts)
  - A custom colour palette: crimson, gold, cream, and charcoal
  - Styled buttons, cards, inputs, and success bars

Run with:  streamlit run app/streamlit_app.py
"""

import sys
import os

# --- Path Setup ---
# Streamlit runs this file from the app/ directory, but we need to import
# modules from sibling directories (scraper/ and ai/). This adds the project
# root to Python’s module search path so those imports work.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

# Import functions from our custom modules:
# - recipe_scraper: handles database queries and live AllRecipes scraping
# - gemini_assistant: handles AI-powered ingredient substitution suggestions
from scraper.recipe_scraper import (
    search_recipes,           # Search the local SQLite database
    search_allrecipes_live,   # Search AllRecipes.com live and cache results
    get_random_recipe,        # Get one random recipe from the database
    get_recipe_count,         # Count total recipes in the database
    init_db,                  # Ensure the database and table exist
)
from ai.gemini_assistant import suggest_substitutes  # AI substitution suggestions


# ---------------------------------------------------------------------------
# Colour palette
# These are used both in the CSS block below and in some inline HTML.
# ---------------------------------------------------------------------------
CRIMSON  = "#AF1B3F"   # Primary accent — headings, primary buttons
GOLD     = "#EC9A29"   # Secondary accent — hover states, cook time, dividers
CREAM    = "#E8EDDF"   # Background colour for the entire app
CHARCOAL = "#242423"   # Text colour + recipe card backgrounds


# ---------------------------------------------------------------------------
# Page configuration
# This must be the first Streamlit command (before any other st.* calls).
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Munchr",                  # Browser tab title
    layout="wide",                         # Use full screen width
    initial_sidebar_state="collapsed",     # Hide sidebar (we don’t use one)
)

# Ensure the SQLite database file and table exist before any queries.
# This is safe to call multiple times (CREATE TABLE IF NOT EXISTS).
init_db()


# ---------------------------------------------------------------------------
# Custom CSS — Roboto Mono + colour palette
#
# This large block injects custom CSS into the Streamlit app to override
# default styles. It covers:
#   - Global font (Roboto Mono) and background colour
#   - Styled text inputs with charcoal background and cream text
#   - Primary/secondary button colours matching the palette
#   - Recipe cards (charcoal background, rounded corners, hover shadow)
#   - Hero title and subtitle sizing/alignment
#   - Custom green success bar
#   - Footer styling
#
# The f-string lets us use Python colour constants (CRIMSON, GOLD, etc.)
# directly inside the CSS so the palette is defined in one place.
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
    /* ---- Google Font ---- */
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap');

    /* ---- Global ---- */
    html, body, [class*="css"] {{
        font-family: 'Roboto Mono', monospace;
        color: {CHARCOAL};
    }}
    .stApp {{
        background-color: {CREAM};
    }}

    /* ---- Force body text colour on all Streamlit elements ---- */
    .stMarkdown, .stMarkdown p, .stMarkdown li,
    .stMarkdown em, .stMarkdown strong,
    .stCheckbox label, .stCheckbox label span,
    [data-testid="stText"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] em,
    [data-testid="stMarkdownContainer"] li {{
        color: {CHARCOAL} !important;
        font-family: 'Roboto Mono', monospace !important;
    }}

    /* ---- Keep button text colours intact ---- */
    .stButton > button,
    .stButton > button span,
    .stButton > button p {{
        color: inherit !important;
    }}
    .stButton > button[kind="primary"] span,
    .stButton > button[data-testid="stBaseButton-primary"] span {{
        color: {CREAM} !important;
    }}
    .stButton > button[kind="secondary"] span,
    .stButton > button[data-testid="stBaseButton-secondary"] span {{
        color: {CREAM} !important;
    }}

    /* ---- Hide default sidebar toggle ---- */
    [data-testid="stSidebarCollapsedControl"] {{
        display: none;
    }}

    /* ---- Headings ---- */
    h1 {{
        color: {CRIMSON} !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }}
    h2, h3 {{
        color: {CHARCOAL} !important;
        font-weight: 600 !important;
    }}

    /* ---- Primary buttons (Search) ---- */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {{
        background-color: {CRIMSON} !important;
        color: {CREAM} !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Roboto Mono', monospace !important;
        font-weight: 600 !important;
        transition: all 0.2s ease;
    }}
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {{
        background-color: {CHARCOAL} !important;
        color: {GOLD} !important;
    }}

    /* ---- Secondary buttons (View Recipe, Back, Feeling Hungry) ---- */
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="stBaseButton-secondary"] {{
        background-color: {GOLD} !important;
        color: {CREAM} !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Roboto Mono', monospace !important;
        font-weight: 500 !important;
        transition: all 0.2s ease;
    }}
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="stBaseButton-secondary"]:hover {{
        background-color: {CHARCOAL} !important;
        color: {GOLD} !important;
    }}

    /* ---- Text inputs ---- */
    .stTextInput input {{
        background-color: #ffffff !important;
        border: 2px solid {CHARCOAL} !important;
        border-radius: 8px !important;
        font-family: 'Roboto Mono', monospace !important;
        color: {CHARCOAL} !important;
    }}
    .stTextInput input:focus {{
        border-color: {CRIMSON} !important;
        box-shadow: 0 0 0 2px rgba(175, 27, 63, 0.15) !important;
    }}

    /* ---- Recipe cards ---- */
    [data-testid="stVerticalBlock"] > div[data-testid="stExpander"],
    div[data-testid="stContainer"] {{
        border-color: {CHARCOAL} !important;
        border-radius: 12px !important;
    }}

    /* ---- Dividers ---- */
    hr {{
        border-color: {GOLD} !important;
        opacity: 0.4;
    }}

    /* ---- Captions ---- */
    .stCaption, small {{
        color: #6b6b6b !important;
        font-family: 'Roboto Mono', monospace !important;
    }}

    /* ---- Info / Success / Warning boxes ---- */
    .stAlert {{
        border-radius: 8px !important;
        font-family: 'Roboto Mono', monospace !important;
    }}

    /* ---- Custom success bar ---- */
    .success-bar {{
        background-color: #698F3F;
        color: #ffffff;
        font-family: 'Roboto Mono', monospace;
        font-weight: 600;
        font-size: 0.95rem;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }}

    /* ---- Recipe result card ---- */
    .recipe-card {{
        background-color: {CHARCOAL};
        color: {CREAM};
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        display: flex;
        flex-direction: column;
        height: 420px;
        overflow: hidden;
    }}
    .recipe-card .card-img-wrap {{
        width: 100%;
        height: 200px;
        border-radius: 10px;
        overflow: hidden;
        flex-shrink: 0;
    }}
    .recipe-card .card-img-wrap img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }}
    .recipe-card .card-body {{
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}
    .recipe-card .card-title {{
        font-family: 'Roboto Mono', monospace;
        font-weight: 600;
        font-size: 0.95rem;
        color: {CREAM} !important;
        margin: 0.6rem 0 0.25rem 0;
        line-height: 1.3;
    }}
    .recipe-card .card-time {{
        font-family: 'Roboto Mono', monospace;
        font-size: 0.8rem;
        color: {GOLD} !important;
        margin-bottom: 0.5rem;
    }}

    /* ---- View Recipe button inside card (Streamlit button override) ---- */
    .card-btn-wrap .stButton > button {{
        background-color: {CRIMSON} !important;
        color: {CREAM} !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Roboto Mono', monospace !important;
        font-weight: 600 !important;
        width: 100%;
        transition: all 0.2s ease;
    }}
    .card-btn-wrap .stButton > button:hover {{
        background-color: {GOLD} !important;
        color: {CHARCOAL} !important;
    }}

    /* ---- Checkboxes ---- */
    .stCheckbox label span {{
        font-family: 'Roboto Mono', monospace !important;
    }}

    /* ---- Hero section styling ---- */
    .hero-title {{
        font-family: 'Roboto Mono', monospace;
        font-size: 5rem;
        font-weight: 700;
        color: {CRIMSON};
        margin-bottom: 0;
        letter-spacing: -1px;
        text-align: center;
    }}
    .hero-subtitle {{
        font-family: 'Roboto Mono', monospace;
        font-size: 1.1rem;
        color: {CHARCOAL};
        opacity: 0.7;
        margin-top: 0;
        text-align: center;
    }}
    .recipe-count {{
        font-family: 'Roboto Mono', monospace;
        font-size: 0.85rem;
        color: {GOLD};
        font-weight: 600;
    }}
    .footer {{
        text-align: center;
        color: #6b6b6b;
        font-size: 0.8rem;
        padding-top: 3rem;
        font-family: 'Roboto Mono', monospace;
    }}
    .footer a {{
        color: {CRIMSON};
        text-decoration: none;
    }}
    .footer a:hover {{
        text-decoration: underline;
    }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state — tracks which recipe the user is currently viewing
#
# Streamlit reruns the entire script on every interaction (button click,
# text input, etc.). Session state persists data across those reruns.
# We use it to track whether the user is on the search page or viewing
# a specific recipe.
#
# selected_recipe = None  → show the search view
# selected_recipe = {...} → show the recipe detail view
# ---------------------------------------------------------------------------
if "selected_recipe" not in st.session_state:
    st.session_state.selected_recipe = None


def select_recipe(recipe: dict):
    """Store the clicked recipe in session state to navigate to the detail view."""
    st.session_state.selected_recipe = recipe


def clear_selection():
    """Clear the selected recipe to return to the search view."""
    st.session_state.selected_recipe = None


# ---------------------------------------------------------------------------
# Recipe Detail View
#
# This view is shown when the user clicks "View Recipe" on a card.
# It displays the full recipe: title, image, cook time, ingredient
# checkboxes, numbered instructions, and the AI substitution assistant.
# ---------------------------------------------------------------------------
if st.session_state.selected_recipe is not None:
    recipe = st.session_state.selected_recipe

    # Back button — clears the selection and reruns the app to show search view
    if st.button("← Back to Search"):
        clear_selection()
        st.rerun()

    # --- Recipe header ---
    st.title(recipe["title"])

    # Recipe image — displayed in a 2:1 column layout so it doesn’t stretch
    # across the full wide layout (looks better with capped width)
    if recipe.get("image_url"):
        col_img, _ = st.columns([2, 1])
        with col_img:
            st.image(recipe["image_url"], use_container_width=True)

    # Cook time (if available in the scraped data)
    if recipe.get("total_time"):
        st.caption(f"⏱️ Total time: {recipe['total_time']} minutes")

    st.divider()

    # --- Two-column layout: ingredients on the left, instructions on the right ---
    # The [1, 2] ratio makes instructions take up 2/3 of the width since
    # they contain more text than the ingredient list.
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.subheader("Ingredients")
        # Each ingredient is rendered as a checkbox so users can tick them
        # off as they cook. The key must be unique per ingredient per recipe
        # to avoid Streamlit duplicate key errors.
        for i, ingredient in enumerate(recipe.get("ingredients", [])):
            st.checkbox(ingredient, key=f"ing_{recipe['id']}_{i}")

    with col_right:
        st.subheader("Instructions")
        # Numbered steps — rendered as bold numbers followed by step text
        for i, step in enumerate(recipe.get("instructions", []), start=1):
            st.markdown(f"**{i}.** {step}")

    st.divider()

    # ------------------------------------------------------------------
    # AI Assistant section
    #
    # This section lets users ask about ingredient substitutions.
    # It sends the recipe context + user question to Gemini AI and
    # displays the structured response as cards.
    # ------------------------------------------------------------------
    st.subheader("Ask Munchr AI")
    st.markdown("*Missing an ingredient? Ask for a substitute.*")

    # Text input for the user’s substitution question
    user_query = st.text_input(
        "Your question",
        placeholder="e.g. I don't have heavy cream, what can I use?",
        label_visibility="collapsed",  # Hide the label, placeholder is enough
        key="ai_query",
    )

    if st.button("Get Substitute", type="primary"):
        if not user_query:
            st.warning("Type a question first!")
        else:
            # Show a spinner while waiting for the Gemini API response
            with st.spinner("Asking Munchr AI..."):
                result = suggest_substitutes(
                    recipe_title=recipe["title"],
                    ingredients=recipe.get("ingredients", []),
                    user_query=user_query,
                )

            # suggest_substitutes() returns either:
            #   - A list of dicts (success) — one per ingredient substitution
            #   - A single dict with "error" key (failure)
            if isinstance(result, dict) and "error" in result:
                st.error(f"AI error: {result['error']}")
            else:
                # Display each substitution as a bordered card
                for sub in result:
                    with st.container(border=True):
                        # Show "ingredient → substitute" if the original ingredient is known
                        label = sub.get("ingredient", "")
                        heading = sub.get("substitute", "N/A")
                        if label:
                            st.markdown(f"### {label} → {heading}")
                        else:
                            st.markdown(f"### {heading}")
                        st.markdown(f"**How much:** {sub.get('ratio', 'N/A')}")
                        st.markdown(f"**Flavour note:** {sub.get('flavour_note', 'N/A')}")
                        st.markdown(f"**Tip:** {sub.get('tip', 'N/A')}")

    # Link back to the original AllRecipes page
    if recipe.get("url"):
        st.markdown(f"[View original on AllRecipes →]({recipe['url']})")


# ---------------------------------------------------------------------------
# Search View (default)
#
# This is the landing page — shown when no recipe is selected.
# It displays the hero title, search bar, and two action buttons.
# When the user searches, it first checks the local SQLite database
# for instant results. If nothing is found, it falls back to a live
# search on AllRecipes.com (which also caches the results locally).
# ---------------------------------------------------------------------------
else:
    # --- Hero header ---
    st.markdown('<p class="hero-title">Munchr</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-subtitle">your ai-powered cooking companion</p>',
        unsafe_allow_html=True,
    )

    st.markdown("")  # Visual spacer

    # --- Search bar ---
    # label_visibility="collapsed" hides the label but keeps it accessible
    # for screen readers. The placeholder text guides the user.
    search_query = st.text_input(
        "Search recipes",
        placeholder="search anything... chicken tikka, szechuan beef, banana bread",
        label_visibility="collapsed",
        key="search_bar",
    )

    # --- Action buttons: Search + I'm Feeling Hungry side by side ---
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        search_clicked = st.button(
            "Search", type="primary", use_container_width=True
        )
    with btn_col2:
        # "I'm Feeling Hungry" picks a random recipe from the local database
        feeling_hungry = st.button(
            "I'm Feeling Hungry", use_container_width=True
        )

    # --- Handle "I'm Feeling Hungry" button ---
    # Picks a random recipe from SQLite and navigates to its detail view
    if feeling_hungry:
        random_recipe = get_random_recipe()
        if random_recipe:
            select_recipe(random_recipe)
            st.rerun()  # Rerun the script to switch to the detail view
        else:
            st.warning("No recipes yet — try searching for something first!")

    # --- Handle search ---
    if search_clicked and search_query:
        # First, check the local SQLite database for instant results.
        # This is fast because it’s just a local SQL query.
        results = search_recipes(search_query)

        # If nothing found locally, search AllRecipes.com live.
        # This scrapes the search results page, extracts recipe URLs,
        # scrapes each one, stores them in SQLite, and returns them.
        # NOTE: Live scraping may fail on cloud hosts (e.g. Streamlit Cloud)
        # because AllRecipes blocks data-centre IPs. In that case, the app
        # falls back to showing the "not found" message below.
        if not results:
            with st.spinner(f"Searching AllRecipes.com for \"{search_query}\"..."):
                results = search_allrecipes_live(search_query)

        if not results:
            st.info(
                f"No recipes found for **\"{search_query}\"**. "
                "Try a broader keyword like \"chicken\", \"pasta\", or \"soup\"."
            )
            st.caption(
                "💡 Live scraping may be limited on cloud-hosted deployments. "
                "The app includes a pre-loaded collection of 75+ recipes — "
                "try searching within those!"
            )
        else:
            # Custom styled success bar (green #698F3F with white text)
            st.markdown(
                f'<div class="success-bar">Found {len(results)} recipe(s)</div>',
                unsafe_allow_html=True,
            )

            # --- 3-column recipe card grid ---
            # Each recipe is rendered as a styled charcoal card with:
            # - Cropped thumbnail image (fixed 200px height)
            # - Recipe title in cream
            # - Cook time in gold
            # - "View Recipe" button underneath
            cols = st.columns(3)
            for i, recipe in enumerate(results):
                # i % 3 distributes cards across 3 columns evenly
                with cols[i % 3]:
                    # Build the card HTML with conditional image and time
                    img_html = ""
                    if recipe.get("image_url"):
                        img_html = (
                            f'<div class="card-img-wrap">'
                            f'<img src="{recipe["image_url"]}" alt="{recipe["title"]}" />'
                            f'</div>'
                        )

                    time_html = ""
                    if recipe.get("total_time"):
                        time_html = f'<div class="card-time">⏱️ {recipe["total_time"]} min</div>'

                    # Render the styled card as raw HTML
                    st.markdown(
                        f'<div class="recipe-card">'
                        f'{img_html}'
                        f'<div class="card-body">'
                        f'<div><div class="card-title">{recipe["title"]}</div>'
                        f'{time_html}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

                    # "View Recipe" button — uses on_click callback to store
                    # the recipe in session state, then Streamlit reruns and
                    # switches to the detail view.
                    with st.container():
                        st.markdown('<div class="card-btn-wrap">', unsafe_allow_html=True)
                        st.button(
                            "View Recipe",
                            key=f"view_{recipe['id']}",  # Unique key per recipe
                            on_click=select_recipe,
                            args=(recipe,),
                            use_container_width=True,
                        )
                        st.markdown('</div>', unsafe_allow_html=True)

    elif search_clicked and not search_query:
        st.warning("Enter a search term first!")


# ---------------------------------------------------------------------------
# Footer
# Attribution for data sources and AI model used.
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="footer">'
    'Recipes sourced from <a href="https://www.allrecipes.com">AllRecipes.com</a> '
    '| AI powered by <a href="https://ai.google.dev/">Google Gemini</a>'
    "</div>",
    unsafe_allow_html=True,
)
