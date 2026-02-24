"""
Munchr — Streamlit Web App
Your AI-powered cooking companion.

Run with:  streamlit run app/streamlit_app.py
"""

import sys
import os

# Add the project root to the Python path so we can import sibling packages
# (scraper/ and ai/) when running from the app/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from scraper.recipe_scraper import (
    search_recipes,
    search_allrecipes_live,
    get_random_recipe,
    get_recipe_count,
    init_db,
)
from ai.gemini_assistant import suggest_substitutes


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
CRIMSON = "#AF1B3F"
GOLD = "#EC9A29"
CREAM = "#E8EDDF"
CHARCOAL = "#242423"


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Munchr",
    page_icon="🍜",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Ensure the database exists
init_db()


# ---------------------------------------------------------------------------
# Custom CSS — Roboto Mono + colour palette
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
        background-color: {CHARCOAL} !important;
        color: {CREAM} !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Roboto Mono', monospace !important;
        font-weight: 500 !important;
        transition: all 0.2s ease;
    }}
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="stBaseButton-secondary"]:hover {{
        background-color: {GOLD} !important;
        color: {CHARCOAL} !important;
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

    /* ---- Checkboxes ---- */
    .stCheckbox label span {{
        font-family: 'Roboto Mono', monospace !important;
    }}

    /* ---- Hero title styling ---- */
    .hero-title {{
        font-family: 'Roboto Mono', monospace;
        font-size: 3.2rem;
        font-weight: 700;
        color: {CRIMSON};
        margin-bottom: 0;
        letter-spacing: -1px;
    }}
    .hero-subtitle {{
        font-family: 'Roboto Mono', monospace;
        font-size: 1.1rem;
        color: {CHARCOAL};
        opacity: 0.7;
        margin-top: 0;
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
# Session state — tracks which recipe is being viewed
# ---------------------------------------------------------------------------
if "selected_recipe" not in st.session_state:
    st.session_state.selected_recipe = None


def select_recipe(recipe: dict):
    """Set the selected recipe in session state."""
    st.session_state.selected_recipe = recipe


def clear_selection():
    """Return to the search view."""
    st.session_state.selected_recipe = None


# ---------------------------------------------------------------------------
# Recipe Detail View
# ---------------------------------------------------------------------------
if st.session_state.selected_recipe is not None:
    recipe = st.session_state.selected_recipe

    # Back button
    if st.button("← Back to Search"):
        clear_selection()
        st.rerun()

    # Recipe title
    st.title(recipe["title"])

    # Recipe image — capped width for readability
    if recipe.get("image_url"):
        col_img, _ = st.columns([2, 1])
        with col_img:
            st.image(recipe["image_url"], use_container_width=True)

    # Cook time
    if recipe.get("total_time"):
        st.caption(f"⏱️ Total time: {recipe['total_time']} minutes")

    st.divider()

    # Two-column layout: ingredients (left) + instructions (right)
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.subheader("Ingredients")
        for i, ingredient in enumerate(recipe.get("ingredients", [])):
            st.checkbox(ingredient, key=f"ing_{recipe['id']}_{i}")

    with col_right:
        st.subheader("Instructions")
        for i, step in enumerate(recipe.get("instructions", []), start=1):
            st.markdown(f"**{i}.** {step}")

    st.divider()

    # ------------------------------------------------------------------
    # AI Assistant section
    # ------------------------------------------------------------------
    st.subheader("Ask Munchr AI")
    st.markdown("*Missing an ingredient? Ask for a substitute.*")

    user_query = st.text_input(
        "Your question",
        placeholder="e.g. I don't have heavy cream, what can I use?",
        label_visibility="collapsed",
        key="ai_query",
    )

    if st.button("Get Substitute", type="primary"):
        if not user_query:
            st.warning("Type a question first!")
        else:
            with st.spinner("Asking Munchr AI..."):
                result = suggest_substitutes(
                    recipe_title=recipe["title"],
                    ingredients=recipe.get("ingredients", []),
                    user_query=user_query,
                )

            if "error" in result:
                st.error(f"AI error: {result['error']}")
            else:
                with st.container(border=True):
                    st.markdown(f"### {result.get('substitute', 'N/A')}")
                    st.markdown(f"**How much:** {result.get('ratio', 'N/A')}")
                    st.markdown(f"**Flavour note:** {result.get('flavour_note', 'N/A')}")
                    st.markdown(f"**Tip:** {result.get('tip', 'N/A')}")

    # Source link
    if recipe.get("url"):
        st.markdown(f"[View original on AllRecipes →]({recipe['url']})")


# ---------------------------------------------------------------------------
# Search View (default)
# ---------------------------------------------------------------------------
else:
    # Hero header
    st.markdown('<p class="hero-title">Munchr</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-subtitle">your ai-powered cooking companion</p>',
        unsafe_allow_html=True,
    )

    # Live recipe count
    count = get_recipe_count()
    st.markdown(
        f'<p class="recipe-count">{count} recipes cached locally</p>',
        unsafe_allow_html=True,
    )

    st.markdown("")  # spacer

    # Search bar
    search_query = st.text_input(
        "Search recipes",
        placeholder="search anything... chicken tikka, szechuan beef, banana bread",
        label_visibility="collapsed",
        key="search_bar",
    )

    # Buttons: Search + I'm Feeling Hungry side by side
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        search_clicked = st.button(
            "Search", type="primary", use_container_width=True
        )
    with btn_col2:
        feeling_hungry = st.button(
            "I'm Feeling Hungry", use_container_width=True
        )

    # Handle "I'm Feeling Hungry"
    if feeling_hungry:
        random_recipe = get_random_recipe()
        if random_recipe:
            select_recipe(random_recipe)
            st.rerun()
        else:
            st.warning("No recipes yet — try searching for something first!")

    # Handle search
    if search_clicked and search_query:
        # Check local DB first
        results = search_recipes(search_query)

        # If nothing local, search AllRecipes.com live
        if not results:
            with st.spinner(f"Searching AllRecipes.com for \"{search_query}\"..."):
                results = search_allrecipes_live(search_query)

        if not results:
            st.info(
                f"No recipes found for **\"{search_query}\"** on AllRecipes. "
                "Try different keywords!"
            )
        else:
            st.success(f"Found **{len(results)}** recipe(s)")
            st.divider()

            # 3-column recipe card grid
            cols = st.columns(3)
            for i, recipe in enumerate(results):
                with cols[i % 3]:
                    with st.container(border=True):
                        if recipe.get("image_url"):
                            st.image(
                                recipe["image_url"], use_container_width=True
                            )

                        st.markdown(f"**{recipe['title']}**")

                        if recipe.get("total_time"):
                            st.caption(f"⏱️ {recipe['total_time']} min")

                        st.button(
                            "View Recipe",
                            key=f"view_{recipe['id']}",
                            on_click=select_recipe,
                            args=(recipe,),
                            use_container_width=True,
                        )

    elif search_clicked and not search_query:
        st.warning("Enter a search term first!")


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="footer">'
    'Recipes sourced from <a href="https://www.allrecipes.com">AllRecipes.com</a> '
    '| AI powered by <a href="https://ai.google.dev/">Google Gemini</a>'
    "</div>",
    unsafe_allow_html=True,
)
