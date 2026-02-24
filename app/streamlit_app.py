"""
Munchr — Streamlit Web App
Vancouver restaurant discovery, powered by AI.

Run with:  streamlit run app/streamlit_app.py
"""

import sys
import os

# Add the project root to the Python path so we can import sibling packages
# (scraper/ and ai/) when running from the app/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from scraper.menu_scraper import get_restaurants, is_scraping_allowed, scrape_menu_text
from ai.gemini_summarizer import summarize_restaurant


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Munchr",
    page_icon="🍜",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Munchr")
st.markdown("**Restaurant discovery, powered by AI**")
st.divider()

# ---------------------------------------------------------------------------
# User inputs
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    neighbourhood = st.text_input(
        "Neighbourhood",
        value="Mount Pleasant",
        help="Enter a Vancouver neighbourhood name (e.g. Kitsilano, Gastown, Mount Pleasant)",
    )

with col2:
    cuisine = st.text_input(
        "Cuisine type",
        value="ramen",
        help="Optional cuisine filter (e.g. ramen, italian, sushi, thai)",
    )

# Maximum restaurants to process (keeps us within Gemini free tier limits)
MAX_RESULTS = 10

search_clicked = st.button("🔍 Search", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Search logic
# ---------------------------------------------------------------------------
if search_clicked:
    # ------------------------------------------------------------------
    # Step 1: Query Overpass API for restaurants in the area
    # ------------------------------------------------------------------
    with st.spinner(f"Searching for {cuisine or 'all'} restaurants in {neighbourhood}..."):
        restaurants = get_restaurants(neighbourhood, cuisine)

    if not restaurants:
        st.warning(
            f"No restaurants found for **{cuisine or 'any cuisine'}** in **{neighbourhood}**. "
            "Try a different neighbourhood or cuisine type."
        )
        st.stop()

    # Cap results to stay within Gemini free tier rate limits
    restaurants = restaurants[:MAX_RESULTS]

    st.success(f"Found **{len(restaurants)}** restaurant(s). Analysing menus with AI...")
    st.divider()

    # ------------------------------------------------------------------
    # Step 2: Loop through each restaurant, scrape, and summarise
    # ------------------------------------------------------------------
    for i, rest in enumerate(restaurants):
        name = rest["name"]
        address = rest["address"]
        website = rest["website"]
        osm_id = rest["osm_id"]

        with st.container(border=True):
            # Restaurant header
            st.subheader(f"🍽️ {name}")

            if address:
                st.caption(f"📍 {address}")

            # Check if the restaurant has a website
            if not website:
                st.warning("No website listed on OpenStreetMap — cannot scrape menu data.")
                continue

            # ----------------------------------------------------------
            # Step 2a: Check robots.txt before scraping
            # ----------------------------------------------------------
            if not is_scraping_allowed(website):
                st.warning(f"Scraping blocked by robots.txt for {website}")
                continue

            # ----------------------------------------------------------
            # Step 2b: Scrape menu text from the website
            # ----------------------------------------------------------
            with st.spinner(f"Scraping {name}'s website..."):
                menu_text = scrape_menu_text(website)

            if not menu_text:
                st.warning("Could not extract any text from the restaurant's website.")
                continue

            # ----------------------------------------------------------
            # Step 2c: Send to Gemini for AI summarisation
            # ----------------------------------------------------------
            with st.spinner(f"Asking AI to analyse {name}'s menu..."):
                summary = summarize_restaurant(name, menu_text)

            # ----------------------------------------------------------
            # Step 2d: Display the AI summary
            # ----------------------------------------------------------
            if "error" in summary:
                st.error(f"AI analysis failed: {summary['error']}")
                continue

            # Vibe & Price Range
            vibe = summary.get("vibe", "No vibe info available.")
            price = summary.get("price_range", "?")
            st.markdown(f"**Vibe:** {vibe}")
            st.markdown(f"**Price range:** {price}")

            # Top dishes as a bullet list
            top_dishes = summary.get("top_dishes", [])
            if top_dishes:
                st.markdown("**🥢 Top 5 Dishes:**")
                for dish in top_dishes:
                    dish_name = dish.get("dish", "Unknown")
                    description = dish.get("description", "")
                    st.markdown(f"- **{dish_name}** — {description}")

            # Practical tips as a bullet list
            tips = summary.get("practical_tips", [])
            if tips:
                st.markdown("**💡 Practical Tips:**")
                for tip in tips:
                    st.markdown(f"- {tip}")

            # Link to website
            st.markdown(f"[🌐 Visit website]({website})")

    st.divider()

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    "<div style='text-align: center; color: grey; font-size: 0.85em; padding-top: 2rem;'>"
    "Data sourced from <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors "
    "| AI powered by <a href='https://ai.google.dev/'>Google Gemini</a>"
    "</div>",
    unsafe_allow_html=True,
)
