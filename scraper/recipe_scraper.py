"""
Munchr — Recipe Scraper & Database Module
Scrapes recipes from AllRecipes.com using the recipe-scrapers library,
stores them in a local SQLite database, and provides search/retrieval functions.
"""

import json
import os
import sqlite3
import time

import requests
from recipe_scrapers import scrape_html


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Realistic User-Agent header to avoid being blocked by AllRecipes
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Database path — stored in data/recipes.db relative to project root
# ---------------------------------------------------------------------------
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "recipes.db")


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    """
    Create the SQLite database and recipes table if they don't already exist.

    Returns:
        A sqlite3.Connection object to the database.
    """
    # Ensure the data/ directory exists
    os.makedirs(DB_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    # Enable dict-like row access
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
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
        # Fetch the recipe page HTML with a proper User-Agent header
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        # Use recipe-scrapers to parse the HTML (reads structured schema data)
        scraper = scrape_html(html=response.text, org_url=url)

        title = scraper.title()
        ingredients = json.dumps(scraper.ingredients())       # list → JSON string
        instructions = json.dumps(scraper.instructions_list())  # list → JSON string
        image_url = scraper.image() if scraper.image() else None
        total_time = str(scraper.total_time()) if scraper.total_time() else None

        # Try to get cuisine from the schema (not always available)
        try:
            cuisine = scraper.cuisine() if hasattr(scraper, "cuisine") else None
        except Exception:
            cuisine = None

        # Store in SQLite — INSERT OR IGNORE skips duplicates (unique URL constraint)
        conn = init_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO recipes
            (title, url, ingredients, instructions, image_url, cuisine, total_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, url, ingredients, instructions, image_url, cuisine, total_time))
        conn.commit()

        # Check if a row was actually inserted (vs. skipped duplicate)
        inserted = cursor.rowcount > 0
        conn.close()

        if inserted:
            print(f"  ✅ Stored: {title}")
        else:
            print(f"  ⏭️  Skipped (duplicate): {title}")

        return inserted

    except Exception as e:
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
    Search recipes by title or ingredients using a case-insensitive LIKE query.

    Args:
        query: The search term (e.g. "chicken", "pasta", "tomato soup").

    Returns:
        A list of matching recipe dicts.
    """
    conn = init_db()
    cursor = conn.cursor()
    # Search both title and ingredients columns
    like_pattern = f"%{query}%"
    cursor.execute("""
        SELECT * FROM recipes
        WHERE title LIKE ? COLLATE NOCASE
          OR ingredients LIKE ? COLLATE NOCASE
        ORDER BY title
    """, (like_pattern, like_pattern))
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


def get_random_recipe() -> dict | None:
    """
    Retrieve one random recipe from the database.

    Returns:
        A recipe dict, or None if the database is empty.
    """
    conn = init_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recipes ORDER BY RANDOM() LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    return _row_to_dict(row) if row else None


def get_recipe_count() -> int:
    """
    Return the total number of recipes in the database.
    """
    conn = init_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM recipes")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Helper — Convert a sqlite3.Row to a clean dict
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict:
    """
    Convert a sqlite3.Row into a plain dict, parsing JSON fields
    (ingredients, instructions) back into Python lists.
    """
    d = dict(row)
    # Decode JSON strings back to Python lists
    d["ingredients"] = json.loads(d["ingredients"]) if d["ingredients"] else []
    d["instructions"] = json.loads(d["instructions"]) if d["instructions"] else []
    return d


# ---------------------------------------------------------------------------
# CLI entry point — run this file directly to seed the database
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Import seed URLs and run bulk scraper
    from seeds.seed_urls import SEED_URLS

    print("Munchr — Recipe Database Seeder")
    print("=" * 40)
    init_db()
    bulk_scrape(SEED_URLS)
