"""
Munchr — Bulk Recipe Seeder

Searches AllRecipes.com for a wide variety of terms and populates the
local SQLite database. Run this locally as cloud IPs could get blocked.

Usage:
    cd munchr/
    source venv/bin/activate
    python seeds/bulk_seed.py

Each search term yields ~12 recipes. Duplicates are skipped automatically.
With ~130 search terms → expect 800-1500 unique recipes.
"""

import sys
import os
import time

# Add project root to path so we can import sibling packages
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scraper.recipe_scraper import search_allrecipes_live, get_recipe_count, init_db


# ---------------------------------------------------------------------------
# Search terms — organised by category for diversity
#
# Each term is sent to AllRecipes search. Duplicates across categories
# are handled by the database (INSERT OR IGNORE on the URL).
# ---------------------------------------------------------------------------

SEARCH_TERMS = [
    # ── Proteins ──────────────────────────────────────────────────────
    "chicken breast", "chicken thigh", "ground beef", "steak",
    "pork chops", "pulled pork", "ground turkey", "lamb chops",
    "salmon", "shrimp", "cod", "tuna", "tilapia", "mahi mahi",
    "tofu", "tempeh", "seitan",

    # ── Cuisines — East Asian ─────────────────────────────────────────
    "chinese stir fry", "kung pao chicken", "mapo tofu",
    "fried rice", "lo mein", "wonton soup", "char siu pork",
    "japanese ramen", "teriyaki chicken", "miso soup",
    "tonkatsu", "japanese curry", "sushi bowl", "gyoza",
    "korean bbq", "bibimbap", "kimchi fried rice", "japchae",
    "korean fried chicken", "bulgogi", "tteokbokki",
    "pad thai", "thai green curry", "thai basil chicken",
    "tom yum soup", "massaman curry", "thai fried rice",
    "vietnamese pho", "banh mi", "spring rolls",

    # ── Cuisines — South & Central Asian ──────────────────────────────
    "butter chicken", "chicken tikka masala", "palak paneer",
    "dal", "biryani", "samosa", "tandoori chicken",
    "naan bread", "aloo gobi", "chana masala",

    # ── Cuisines — Latin American ─────────────────────────────────────
    "tacos", "chicken burrito", "enchiladas", "carnitas",
    "black bean soup", "tamales", "chilaquiles",
    "empanadas", "cuban sandwich", "arroz con pollo",
    "ceviche", "brazilian feijoada",

    # ── Cuisines — Mediterranean & Middle Eastern ─────────────────────
    "hummus", "falafel", "shawarma", "tabbouleh",
    "greek salad", "moussaka", "spanakopita",
    "shakshuka", "lamb gyro", "baklava",

    # ── Cuisines — Italian ────────────────────────────────────────────
    "spaghetti carbonara", "lasagna", "chicken parmesan",
    "risotto", "gnocchi", "minestrone", "pesto pasta",
    "margherita pizza", "osso buco", "tiramisu",

    # ── Cuisines — American & Southern ────────────────────────────────
    "mac and cheese", "fried chicken", "cornbread",
    "bbq ribs", "clam chowder", "gumbo", "jambalaya",
    "biscuits and gravy", "pot roast", "meatloaf",

    # ── Cuisines — Other ──────────────────────────────────────────────
    "jollof rice", "moroccan tagine", "pierogi",
    "french onion soup", "beef bourguignon", "ratatouille",
    "fish and chips", "shepherds pie", "bangers and mash",

    # ── Health-Conscious & Dietary ────────────────────────────────────
    "low calorie dinner", "high protein meal", "low carb dinner",
    "keto chicken", "keto beef", "keto salmon",
    "whole30 recipe", "paleo chicken", "paleo dinner",
    "low sodium recipe", "heart healthy dinner",
    "anti inflammatory recipe", "diabetic friendly dinner",
    "low fat chicken", "lean ground turkey recipe",
    "high fiber meal", "clean eating dinner",

    # ── Vegan & Vegetarian ────────────────────────────────────────────
    "vegan dinner", "vegan pasta", "vegan stir fry",
    "vegan curry", "vegan burger", "vegan soup",
    "vegetarian dinner", "vegetarian chili", "vegetarian stew",
    "plant based protein bowl", "lentil soup", "chickpea curry",
    "cauliflower steak", "stuffed peppers vegetarian",
    "vegan tacos", "mushroom stroganoff",

    # ── Gluten-Free ───────────────────────────────────────────────────
    "gluten free dinner", "gluten free pasta",
    "gluten free chicken", "gluten free dessert",

    # ── Meal Types ────────────────────────────────────────────────────
    "quick weeknight dinner", "30 minute meal",
    "one pot meal", "sheet pan dinner", "slow cooker recipe",
    "instant pot chicken", "meal prep recipe",
    "easy lunch", "healthy breakfast", "protein smoothie bowl",
    "overnight oats", "egg muffins",

    # ── Soups & Stews ─────────────────────────────────────────────────
    "chicken noodle soup", "beef stew", "tomato soup",
    "potato soup", "chili recipe", "butternut squash soup",
    "tortilla soup", "pumpkin soup",

    # ── Salads & Bowls ────────────────────────────────────────────────
    "quinoa bowl", "grain bowl", "poke bowl",
    "chicken caesar salad", "mediterranean salad",
    "southwest salad", "asian sesame salad",

    # ── Baking & Desserts ─────────────────────────────────────────────
    "banana bread", "chocolate chip cookies", "brownies",
    "apple pie", "cheesecake", "lemon bars",
    "cinnamon rolls", "blueberry muffins",

    # ── Snacks & Appetizers ───────────────────────────────────────────
    "guacamole", "bruschetta", "stuffed mushrooms",
    "chicken wings", "spinach artichoke dip", "deviled eggs",
]


def main():
    """Run the bulk seeder — search each term and populate the DB."""
    init_db()

    total_terms = len(SEARCH_TERMS)
    start_count = get_recipe_count()

    print("=" * 60)
    print(f"  Munchr Bulk Seeder — {total_terms} search terms")
    print(f"  Starting recipe count: {start_count}")
    print("=" * 60)

    for i, term in enumerate(SEARCH_TERMS, start=1):
        current = get_recipe_count()
        print(f"\n[{i}/{total_terms}] Searching: \"{term}\"  (DB: {current} recipes)")

        try:
            results = search_allrecipes_live(term, max_results=12)
            if results:
                print(f"  ✅ Found {len(results)} recipes")
            else:
                print(f"  ⚠️  No results for \"{term}\"")
        except Exception as e:
            print(f"  ❌ Error: {e}")

        # Polite delay between search pages (individual recipe delays
        # are already handled inside search_allrecipes_live)
        if i < total_terms:
            time.sleep(2)

    final_count = get_recipe_count()
    new_recipes = final_count - start_count

    print("\n" + "=" * 60)
    print(f"  Done! Added {new_recipes} new recipes.")
    print(f"  Total recipes in database: {final_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
