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
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Munchr 🍜",
    page_icon="🍜",
    layout="wide",
)

# Ensure the database exists
init_db()


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
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("# 🍜 Munchr")
    st.markdown("*Your AI-powered cooking companion*")
    st.divider()

    # "I'm Feeling Hungry" button — loads a random recipe
    if st.button("🎲 I'm Feeling Hungry", use_container_width=True):
        random_recipe = get_random_recipe()
        if random_recipe:
            select_recipe(random_recipe)
            st.rerun()
        else:
            st.warning("Database is empty! Run the seeder first.")

    st.divider()

    # Live recipe count from the database
    count = get_recipe_count()
    st.caption(f"📚 Database contains **{count}** recipes")


# ---------------------------------------------------------------------------
# Main area — Recipe Detail View
# ---------------------------------------------------------------------------
if st.session_state.selected_recipe is not None:
    recipe = st.session_state.selected_recipe

    # Back button
    if st.button("← Back to Search"):
        clear_selection()
        st.rerun()

    # Recipe title
    st.title(f"🍽️ {recipe['title']}")

    # Recipe image
    if recipe.get("image_url"):
        st.image(recipe["image_url"], use_container_width=True)

    # Cook time
    if recipe.get("total_time"):
        st.caption(f"⏱️ Total time: {recipe['total_time']} minutes")

    st.divider()

    # Two-column layout: ingredients (left) + instructions (right)
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.subheader("🛒 Ingredients")
        # Checklist — users can tick off ingredients as they cook
        for i, ingredient in enumerate(recipe.get("ingredients", [])):
            st.checkbox(ingredient, key=f"ing_{recipe['id']}_{i}")

    with col_right:
        st.subheader("📝 Instructions")
        # Numbered list of steps
        for i, step in enumerate(recipe.get("instructions", []), start=1):
            st.markdown(f"**Step {i}.** {step}")

    st.divider()

    # ------------------------------------------------------------------
    # AI Assistant section
    # ------------------------------------------------------------------
    st.subheader("🤖 Ask Munchr AI")
    st.markdown("Missing an ingredient? Ask me for a substitute...")

    user_query = st.text_input(
        "Your question",
        placeholder="e.g. I don't have heavy cream, what can I use?",
        label_visibility="collapsed",
        key="ai_query",
    )

    if st.button("💡 Get Substitute", type="primary"):
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
                # Display the substitution as a clean card
                with st.container(border=True):
                    st.markdown(f"### ✅ {result.get('substitute', 'N/A')}")
                    st.markdown(f"**How much:** {result.get('ratio', 'N/A')}")
                    st.markdown(f"**Flavour note:** {result.get('flavour_note', 'N/A')}")
                    st.markdown(f"**💡 Tip:** {result.get('tip', 'N/A')}")

    # Source link
    if recipe.get("url"):
        st.markdown(f"[🔗 View original recipe on AllRecipes]({recipe['url']})")


# ---------------------------------------------------------------------------
# Main area — Search View (default)
# ---------------------------------------------------------------------------
else:
    st.title("Munchr 🍜")
    st.markdown("**Search a recipe or get a random one**")

    # Search bar
    search_query = st.text_input(
        "Search recipes",
        placeholder="e.g. chicken pasta, tomato soup, stir fry...",
        label_visibility="collapsed",
        key="search_bar",
    )

    search_clicked = st.button("🔍 Search AllRecipes", type="primary", use_container_width=True)

    if search_clicked and search_query:
        # First check local DB for instant results
        results = search_recipes(search_query)

        # If nothing local, search AllRecipes.com live
        if not results:
            with st.spinner(f"Searching AllRecipes.com for \"{search_query}\"..."):
                results = search_allrecipes_live(search_query)

        if not results:
            st.info(
                f"No recipes found for **\"{search_query}\"** on AllRecipes.com. "
                "Try different keywords or hit 🎲 in the sidebar for a random pick!"
            )
        else:
            st.success(f"Found **{len(results)}** recipe(s)")
            st.divider()

            # Display results as a grid of recipe cards (3 columns)
            cols = st.columns(3)
            for i, recipe in enumerate(results):
                with cols[i % 3]:
                    with st.container(border=True):
                        # Thumbnail image
                        if recipe.get("image_url"):
                            st.image(recipe["image_url"], use_container_width=True)

                        # Recipe title
                        st.markdown(f"**{recipe['title']}**")

                        # Cook time
                        if recipe.get("total_time"):
                            st.caption(f"⏱️ {recipe['total_time']} min")

                        # View Recipe button
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
    "<div style='text-align: center; color: grey; font-size: 0.85em; padding-top: 2rem;'>"
    "Recipes sourced from <a href='https://www.allrecipes.com'>AllRecipes.com</a> "
    "| AI powered by <a href='https://ai.google.dev/'>Google Gemini 2.0 Flash</a>"
    "</div>",
    unsafe_allow_html=True,
)
