"""
Munchr — Recipe Scraper & Database Module

This is the core data layer of the Munchr app. It handles three main jobs:
  1. Scraping individual recipe pages from AllRecipes.com
  2. Storing scraped recipes in a local SQLite database (data/recipes.db)
  3. Querying the database — search, random pick, count, etc.

It also provides a "live search" feature that hits the AllRecipes search
page in real-time, scrapes the results, and caches them locally so future
searches for the same term are instant.

Key libraries used:
  - requests         → HTTP client for fetching web pages
  - BeautifulSoup4   → HTML parser for extracting recipe URLs from search pages
  - recipe-scrapers  → Open-source library that parses recipe structured data
  - sqlite3          → Built-in Python module for the local database
"""

import json       # For serializing/deserializing ingredient & instruction lists
import os         # For file path construction and directory creation
import re         # For regex matching of AllRecipes URL patterns
import sqlite3    # For local SQLite database operations
import time       # For adding polite delays between web requests

import requests                    # HTTP client for fetching web pages
from bs4 import BeautifulSoup      # HTML parser for AllRecipes search results
from recipe_scrapers import scrape_html  # Parses recipe schema from raw HTML


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# A realistic browser User-Agent header. AllRecipes.com blocks requests that
# don't look like they come from a real browser, so we mimic Chrome on macOS.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Database path — stored in data/recipes.db relative to project root
# We use os.path to build the path dynamically so it works regardless of
# where the script is run from (e.g. from app/ or from the project root).
# ---------------------------------------------------------------------------
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "recipes.db")


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    """
    Create the SQLite database and recipes table if they don't already exist.

    This is called at the start of almost every other function to ensure
    the database is always available. SQLite is file-based, so "creating"
    the database just means creating a file if it doesn't exist yet.

    The table schema stores:
      - id:           Auto-incrementing primary key
      - title:        Recipe name (e.g. "Gigi Hadid Pasta")
      - url:          Original AllRecipes URL (UNIQUE to prevent duplicates)
      - ingredients:  JSON-encoded list of ingredient strings
      - instructions: JSON-encoded list of step strings
      - image_url:    URL to the recipe's hero image (nullable)
      - cuisine:      Cuisine type if available (nullable)
      - total_time:   Cook time in minutes as a string (nullable)

    Returns:
        A sqlite3.Connection object to the database.
    """
    # Ensure the data/ directory exists (creates it on first run)
    os.makedirs(DB_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    # row_factory = sqlite3.Row lets us access columns by name (row["title"])
    # instead of by index (row[1]), which makes the code much more readable.
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    # CREATE TABLE IF NOT EXISTS is idempotent — safe to call every time.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            url         TEXT UNIQUE NOT NULL,
            ingredients TEXT NOT NULL,       -- JSON array of ingredient strings
            instructions TEXT NOT NULL,      -- JSON array of instruction steps
            image_url   TEXT,
            cuisine     TEXT,
            total_time  TEXT
        )
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Single Recipe Scraper
# ---------------------------------------------------------------------------

def scrape_and_store(url: str) -> bool:
    """
    Scrape a single recipe from AllRecipes.com and store it in the database.

    Uses the recipe-scrapers library which handles parsing recipe schema
    cleanly and legally (reads structured data from the page).

    Args:
        url: A full AllRecipes.com recipe URL.

    Returns:
        True if the recipe was stored successfully, False if it was a
        duplicate or if scraping failed.
    """
    try:
        # --- Step A: Fetch the raw HTML from AllRecipes ---
        # We pass a realistic User-Agent header so AllRecipes doesn't block us.
        # timeout=15 prevents the app from hanging if the server is slow.
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()  # Raises an exception for 4xx/5xx status codes

        # --- Step B: Parse the HTML using recipe-scrapers ---
        # The recipe-scrapers library reads structured JSON-LD / schema.org data
        # embedded in the page. This is the same data Google uses for rich results.
        # We pass the raw HTML + URL so recipe-scrapers knows which site parser to use.
        scraper = scrape_html(html=response.text, org_url=url)

        # --- Step C: Extract recipe fields ---
        title = scraper.title()                                  # e.g. "Gigi Hadid Pasta"
        ingredients = json.dumps(scraper.ingredients())           # list → JSON string for DB storage
        instructions = json.dumps(scraper.instructions_list())   # list → JSON string for DB storage
        image_url = scraper.image() if scraper.image() else None # Hero image URL (may be None)
        total_time = str(scraper.total_time()) if scraper.total_time() else None  # Cook time in minutes

        # Cuisine is not always available in the recipe schema, so we wrap it
        # in a try/except to avoid crashing on recipes that don't have it.
        try:
            cuisine = scraper.cuisine() if hasattr(scraper, "cuisine") else None
        except Exception:
            cuisine = None

        # --- Step D: Store in SQLite ---
        # INSERT OR IGNORE means if a recipe with the same URL already exists
        # (UNIQUE constraint), it silently skips instead of raising an error.
        # This makes the function safe to call repeatedly with the same URL.
        conn = init_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO recipes
            (title, url, ingredients, instructions, image_url, cuisine, total_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, url, ingredients, instructions, image_url, cuisine, total_time))
        conn.commit()

        # cursor.rowcount tells us if a row was actually inserted (1) or skipped (0)
        inserted = cursor.rowcount > 0
        conn.close()

        if inserted:
            print(f"  ✅ Stored: {title}")
        else:
            print(f"  ⏭️  Skipped (duplicate): {title}")

        return inserted

    except Exception as e:
        # Catch any error (network timeout, 404, parsing failure, etc.)
        # and return False so bulk_scrape can continue with the next URL.
        print(f"  ❌ Failed to scrape {url}: {e}")
        return False


# ---------------------------------------------------------------------------
# Bulk Scraper
# ---------------------------------------------------------------------------

def bulk_scrape(url_list: list[str]) -> int:
    """
    Scrape multiple AllRecipes URLs and store them in the database.

    Includes a 2-second delay between requests to be respectful of
    AllRecipes.com servers.

    Args:
        url_list: A list of AllRecipes.com recipe URLs.

    Returns:
        The number of new recipes successfully stored.
    """
    print(f"🍳 Starting bulk scrape of {len(url_list)} recipes...\n")
    stored_count = 0

    for i, url in enumerate(url_list, start=1):
        print(f"[{i}/{len(url_list)}] Scraping: {url}")
        success = scrape_and_store(url)
        if success:
            stored_count += 1

        # Be respectful — wait 2 seconds between requests
        if i < len(url_list):
            time.sleep(2)

    print(f"\n✅ Done! Stored {stored_count} new recipes out of {len(url_list)} URLs.")
    return stored_count


# ---------------------------------------------------------------------------
# Live AllRecipes Search
# ---------------------------------------------------------------------------

def search_allrecipes_live(query: str, max_results: int = 12) -> list[dict]:
    """
    Search AllRecipes.com in real-time, scrape the results, store them
    in the local database, and return them.

    This is the key function that makes Munchr feel like a real recipe
    search engine. Instead of being limited to pre-seeded recipes, users
    can search for anything and get live results from AllRecipes.com.

    How it works:
      1. Build the AllRecipes search URL (e.g. /search?q=szechuan+chicken)
      2. Fetch the search results page HTML
      3. Parse the HTML with BeautifulSoup to find recipe links
      4. Scrape each recipe page and store it in SQLite
      5. Query the local DB to return the freshly-stored recipes

    Every recipe discovered this way is cached permanently in the local
    SQLite database, so searching the same term again is instant.

    Args:
        query: The search term (e.g. "szechuan chicken").
        max_results: Maximum number of recipes to scrape (default 12).

    Returns:
        A list of recipe dicts (same format as search_recipes).
    """
    # Build the search URL — requests.utils.quote handles URL encoding
    # (e.g. spaces become %20, special chars are escaped)
    search_url = f"https://www.allrecipes.com/search?q={requests.utils.quote(query)}"

    # --- Step 1: Fetch the search results page ---
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ❌ AllRecipes search request failed: {e}")
        return []

    # --- Step 2: Parse the HTML to extract recipe URLs ---
    # We use BeautifulSoup with lxml (fast C-based parser) to find all
    # <a> tags that link to recipe pages.
    soup = BeautifulSoup(resp.text, "lxml")

    # AllRecipes uses two URL formats:
    #   New format: /gigi-hadid-pasta-recipe-11900468  (slug ending in -recipe-DIGITS)
    #   Old format: /recipe/12345/slug-name/           (path starting with /recipe/)
    # We use regex to match both patterns.
    recipe_urls = []
    seen = set()  # Track URLs we've already found to avoid duplicates
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href in seen:
            continue
        # Check if the link matches either AllRecipes URL pattern
        if re.search(r"allrecipes\.com/[\w-]+-recipe-\d+", href) or \
           re.search(r"allrecipes\.com/recipe/\d+/", href):
            seen.add(href)
            recipe_urls.append(href)
        # Stop once we have enough results
        if len(recipe_urls) >= max_results:
            break

    if not recipe_urls:
        return []

    # --- Step 3: Scrape each recipe and store in the database ---
    # scrape_and_store() handles duplicates automatically (INSERT OR IGNORE),
    # so re-scraping an already-cached recipe is safe and just skips it.
    for i, url in enumerate(recipe_urls):
        scrape_and_store(url)
        # Be polite — 1 second delay between requests to avoid hammering the server
        if i < len(recipe_urls) - 1:
            time.sleep(1)

    # --- Step 4: Query the local DB to return the full recipe data ---
    # We query by URL (not by search term) to get exactly the recipes we
    # just scraped, with all their fields properly parsed.
    conn = init_db()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in recipe_urls)  # Build "?,?,?" for SQL IN clause
    cursor.execute(
        f"SELECT * FROM recipes WHERE url IN ({placeholders}) ORDER BY title",
        recipe_urls,
    )
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Database Query Functions
# ---------------------------------------------------------------------------

def get_all_recipes() -> list[dict]:
    """
    Retrieve all recipes from the database.

    Returns:
        A list of dicts, each representing a recipe with decoded
        ingredients and instructions (from JSON strings back to lists).
    """
    conn = init_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recipes ORDER BY title")
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def search_recipes(query: str) -> list[dict]:
    """
    Search the LOCAL database for recipes matching the given query.

    This is the fast, offline-first search. It checks the SQLite database
    for recipes that have already been scraped and cached. If nothing is
    found here, the Streamlit app falls back to search_allrecipes_live().

    Search strategy:
      - The query is split into individual keywords (e.g. "cajun soup" → ["cajun", "soup"])
      - Each keyword is matched with LIKE (case-insensitive) against ALL text columns:
        title, ingredients, instructions, and cuisine
      - All keywords must match (AND logic), but each can match in a different column
      - Example: "chicken stir" matches a recipe titled "Chicken Cabbage Stir Fry"

    Args:
        query: The search term (e.g. "chicken", "pasta", "cajun soup").

    Returns:
        A list of matching recipe dicts, sorted alphabetically by title.
    """
    conn = init_db()
    cursor = conn.cursor()

    # Split the query into individual words.
    # "cajun soup" becomes ["cajun", "soup"] — both must appear somewhere.
    keywords = query.strip().split()
    if not keywords:
        conn.close()
        return []

    # Build a WHERE clause for each keyword. Each keyword gets its own
    # group of OR conditions (can match in any column), and all groups
    # are joined with AND (every keyword must match somewhere).
    where_clauses = []
    params = []
    for kw in keywords:
        like = f"%{kw}%"  # SQL LIKE wildcard pattern
        where_clauses.append(
            "(title LIKE ? COLLATE NOCASE "
            "OR ingredients LIKE ? COLLATE NOCASE "
            "OR instructions LIKE ? COLLATE NOCASE "
            "OR cuisine LIKE ? COLLATE NOCASE)"
        )
        # Each LIKE clause needs its own copy of the pattern
        params.extend([like, like, like, like])

    # Combine all keyword clauses with AND and execute
    sql = f"SELECT * FROM recipes WHERE {' AND '.join(where_clauses)} ORDER BY title"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def get_random_recipe() -> dict | None:
    """
    Retrieve one random recipe from the database.

    Uses SQLite's built-in RANDOM() function to pick a random row.
    This powers the "I'm Feeling Hungry" button in the Streamlit app.

    Returns:
        A recipe dict, or None if the database is empty.
    """
    conn = init_db()
    cursor = conn.cursor()
    # ORDER BY RANDOM() LIMIT 1 is the standard SQLite way to get a random row
    cursor.execute("SELECT * FROM recipes ORDER BY RANDOM() LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    return _row_to_dict(row) if row else None


def get_recipe_count() -> int:
    """
    Return the total number of recipes in the database.

    Used by the Streamlit app to display how many recipes are cached.
    """
    conn = init_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM recipes")
    count = cursor.fetchone()[0]  # fetchone() returns a tuple; [0] gets the count
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Helper — Convert a sqlite3.Row to a clean dict
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict:
    """
    Convert a sqlite3.Row into a plain Python dict, parsing JSON fields
    (ingredients, instructions) back into Python lists.

    This is a helper used by every query function. In the database,
    ingredients and instructions are stored as JSON strings (e.g.
    '["1 cup flour", "2 eggs"]') because SQLite doesn't have an array
    type. This function converts them back to real Python lists so the
    rest of the app can work with them naturally.

    Args:
        row: A sqlite3.Row object from a database query.

    Returns:
        A plain dict with all recipe fields, where ingredients and
        instructions are Python lists instead of JSON strings.
    """
    d = dict(row)  # Convert sqlite3.Row → regular dict
    # json.loads() turns the JSON string back into a Python list
    d["ingredients"] = json.loads(d["ingredients"]) if d["ingredients"] else []
    d["instructions"] = json.loads(d["instructions"]) if d["instructions"] else []
    return d


# ---------------------------------------------------------------------------
# CLI entry point — run this file directly to seed the database
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CLI entry point — run this file directly to seed the database
#
# Usage:  python scraper/recipe_scraper.py
#
# This imports the list of starter URLs from seeds/seed_urls.py and
# scrapes all of them into the local SQLite database. It's useful for
# pre-populating the database before first launch, but it's optional
# since the live search feature also populates the database automatically.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    # Add project root to path so we can import the seeds/ package
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from seeds.seed_urls import SEED_URLS

    print("Munchr — Recipe Database Seeder")
    print("=" * 40)
    init_db()
    bulk_scrape(SEED_URLS)
