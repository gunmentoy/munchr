"""
Munchr — Menu Scraper Module
Queries OpenStreetMap via Overpass API for Vancouver restaurants,
then scrapes their websites for menu text using BeautifulSoup.

For JavaScript-heavy restaurant sites that don't render with requests
alone, Playwright is used as an automatic fallback headless browser.

First-time setup requires:  playwright install chromium
"""

import asyncio
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser


# ---------------------------------------------------------------------------
# Overpass API — Restaurant Discovery
# ---------------------------------------------------------------------------

# Overpass API endpoints (public, no API key required)
# We use a primary + fallback server in case one is overloaded or rate-limited.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Maximum number of retry attempts per Overpass server
MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# Vancouver neighbourhood bounding boxes (south, west, north, east)
# These are approximate lat/lon rectangles covering each neighbourhood.
# Using bounding boxes is much faster and more reliable than OSM area queries,
# because Vancouver neighbourhoods are not consistently tagged in OSM.
# ---------------------------------------------------------------------------
NEIGHBOURHOOD_BBOXES = {
    "downtown":         (49.2760, -123.1350, 49.2920, -123.1050),
    "gastown":          (49.2820, -123.1120, 49.2870, -123.0970),
    "chinatown":        (49.2770, -123.1060, 49.2820, -123.0950),
    "yaletown":         (49.2700, -123.1250, 49.2780, -123.1100),
    "west end":         (49.2800, -123.1450, 49.2920, -123.1250),
    "mount pleasant":   (49.2530, -123.1150, 49.2700, -123.0850),
    "kitsilano":        (49.2600, -123.1750, 49.2750, -123.1350),
    "commercial drive": (49.2560, -123.0740, 49.2750, -123.0630),
    "main street":      (49.2430, -123.1050, 49.2650, -123.0900),
    "hastings-sunrise": (49.2750, -123.0550, 49.2850, -123.0150),
    "strathcona":       (49.2700, -123.0900, 49.2780, -123.0720),
    "grandview-woodland": (49.2700, -123.0750, 49.2820, -123.0500),
    "fairview":         (49.2600, -123.1400, 49.2720, -123.1150),
    "south granville":  (49.2500, -123.1500, 49.2630, -123.1350),
    "kerrisdale":       (49.2270, -123.1600, 49.2420, -123.1400),
    "dunbar":           (49.2350, -123.1900, 49.2550, -123.1650),
    "point grey":       (49.2600, -123.2100, 49.2750, -123.1850),
    "riley park":       (49.2400, -123.1050, 49.2540, -123.0850),
    "cambie":           (49.2370, -123.1250, 49.2530, -123.1050),
    "marpole":          (49.2050, -123.1400, 49.2250, -123.1200),
    "coal harbour":     (49.2870, -123.1300, 49.2950, -123.1100),
    "olympic village":  (49.2660, -123.1120, 49.2730, -123.1000),
    # Fallback: all of Vancouver
    "vancouver":        (49.2000, -123.2500, 49.3200, -123.0200),
}


def _get_bbox(neighbourhood: str) -> tuple:
    """
    Look up the bounding box for a Vancouver neighbourhood.

    Uses fuzzy matching: if the user types "mt pleasant" or "Mount Pleasant",
    we'll match "mount pleasant" from our lookup table. Falls back to all of
    Vancouver if no match is found.

    Args:
        neighbourhood: User-entered neighbourhood name.

    Returns:
        Tuple of (south, west, north, east) lat/lon coordinates.
    """
    key = neighbourhood.strip().lower()

    # Exact match
    if key in NEIGHBOURHOOD_BBOXES:
        return NEIGHBOURHOOD_BBOXES[key]

    # Partial / fuzzy match — check if the input is contained in any key or vice versa
    for name, bbox in NEIGHBOURHOOD_BBOXES.items():
        if key in name or name in key:
            return bbox

    # Common abbreviations
    abbreviations = {"mt": "mount", "comm": "commercial", "e van": "hastings", "kits": "kitsilano"}
    for abbrev, full in abbreviations.items():
        if abbrev in key:
            for name, bbox in NEIGHBOURHOOD_BBOXES.items():
                if full in name:
                    return bbox

    # No match — search all of Vancouver
    print(f"[Overpass] Neighbourhood '{neighbourhood}' not recognized, searching all of Vancouver.")
    return NEIGHBOURHOOD_BBOXES["vancouver"]


def get_restaurants(neighbourhood: str, cuisine: str = "") -> list[dict]:
    """
    Query the Overpass API for restaurants in a Vancouver neighbourhood.

    Uses a bounding-box approach (much faster and more reliable than OSM area
    queries, since Vancouver neighbourhoods aren't consistently tagged in OSM).

    Args:
        neighbourhood: Name of the Vancouver neighbourhood (e.g. "Mount Pleasant").
        cuisine: Optional cuisine type filter (e.g. "ramen", "italian").

    Returns:
        A list of dicts, each containing:
            - name (str): Restaurant name
            - address (str): Street address (if available)
            - website (str | None): Restaurant website URL (or None)
            - osm_id (int): OpenStreetMap node/way ID
    """

    # Look up the bounding box for the neighbourhood
    south, west, north, east = _get_bbox(neighbourhood)
    bbox = f"({south},{west},{north},{east})"

    # Build the cuisine filter for the Overpass query.
    # If a cuisine is provided, we add a tag filter like ["cuisine"~"ramen",i]
    # The ",i" flag makes the match case-insensitive.
    cuisine_filter = f'["cuisine"~"{cuisine}",i]' if cuisine else ""

    # Overpass QL query using a bounding box:
    # 1. Search for nodes and ways tagged amenity=restaurant within the bbox
    # 2. Optionally filter by cuisine tag
    # 3. Output body + geometry in JSON format
    query = f"""
[out:json][timeout:25];
(
  node["amenity"="restaurant"]{cuisine_filter}{bbox};
  way["amenity"="restaurant"]{cuisine_filter}{bbox};
);
out body center;
"""

    # Try each Overpass server with retries (POST is recommended for longer queries)
    import time
    data = None
    for server_url in OVERPASS_URLS:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # POST is preferred by Overpass for complex queries (avoids URL length issues)
                response = requests.post(
                    server_url,
                    data={"data": query},
                    timeout=60,  # generous timeout for slow servers
                )
                response.raise_for_status()
                data = response.json()
                break  # success — exit retry loop
            except requests.RequestException as e:
                print(f"[Overpass API Error] {server_url} (attempt {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)  # brief backoff before retry
        if data is not None:
            break  # got data — no need to try the fallback server

    if data is None:
        print("[Overpass API Error] All servers failed.")
        return []

    restaurants = []

    # Parse each element returned by Overpass
    for element in data.get("elements", []):
        tags = element.get("tags", {})

        # Skip entries without a name (unlabeled POIs)
        name = tags.get("name")
        if not name:
            continue

        # Build a human-readable address from OSM addr:* tags
        street = tags.get("addr:street", "")
        housenumber = tags.get("addr:housenumber", "")
        city = tags.get("addr:city", "Vancouver")
        address = f"{housenumber} {street}, {city}".strip(", ")

        # Website may or may not be present in OSM data
        website = tags.get("website") or tags.get("contact:website") or None

        # Get the OSM element ID (works for both nodes and ways)
        osm_id = element.get("id")

        restaurants.append({
            "name": name,
            "address": address,
            "website": website,
            "osm_id": osm_id,
        })

    return restaurants


# ---------------------------------------------------------------------------
# Robots.txt Checker — Ethical Scraping
# ---------------------------------------------------------------------------

def is_scraping_allowed(url: str, user_agent: str = "*") -> bool:
    """
    Check whether scraping is permitted by the site's robots.txt.

    Args:
        url: The full URL we intend to scrape.
        user_agent: The user-agent string to check against (default: "*").

    Returns:
        True if scraping is allowed (or robots.txt cannot be fetched),
        False if the robots.txt explicitly disallows the path.
    """
    try:
        # Parse the base URL to construct the robots.txt location
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        # Use Python's built-in RobotFileParser to read and interpret robots.txt
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()

        # Check if our user-agent is allowed to fetch the target URL
        return rp.can_fetch(user_agent, url)

    except Exception:
        # If robots.txt can't be fetched (404, timeout, etc.),
        # we assume scraping is allowed (standard convention).
        return True


# ---------------------------------------------------------------------------
# Website Scraper — Menu Text Extraction
# ---------------------------------------------------------------------------

# Tags that contain non-visible or non-content elements to remove
NON_CONTENT_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "iframe", "svg"]

# Minimum character threshold — pages returning less text than this are likely
# JavaScript-rendered and need a headless browser to get real content.
JS_RENDER_THRESHOLD = 200


def is_js_rendered(text: str) -> bool:
    """
    Heuristic check: if the scraped text is under 200 characters, the page
    is likely JavaScript-rendered and returned mostly empty HTML to a plain
    requests call.

    Args:
        text: The cleaned text extracted by the initial BeautifulSoup scrape.

    Returns:
        True if the text looks too short (JS-rendered page), False otherwise.
    """
    return len(text.strip()) < JS_RENDER_THRESHOLD


def _clean_html(html: str) -> str:
    """
    Shared helper: parse raw HTML with BeautifulSoup, strip non-content tags,
    and return cleaned plain text.

    Args:
        html: Raw HTML string.

    Returns:
        Cleaned plain-text string.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove all non-content tags (scripts, styles, nav, footer, etc.)
    for tag in soup.find_all(NON_CONTENT_TAGS):
        tag.decompose()

    # Extract the visible text, using newlines as separator
    raw_text = soup.get_text(separator="\n")

    # Clean up: collapse multiple blank lines and strip whitespace
    lines = [line.strip() for line in raw_text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)  # remove empty lines

    # Cap the text length to avoid sending huge payloads to Gemini
    max_chars = 15000
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "\n... [truncated]"

    return cleaned


async def _scrape_with_playwright(url: str) -> str:
    """
    Fallback scraper using Playwright (headless Chromium) for JavaScript-
    heavy websites that don't return meaningful HTML to a plain GET request.

    Requires first-time setup:  playwright install chromium

    Args:
        url: The full URL of the restaurant website.

    Returns:
        Cleaned plain-text string from the fully rendered page,
        or an empty string if Playwright also fails.
    """
    # Import Playwright only when needed (it's a heavy dependency)
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as p:
            # Launch headless Chromium browser
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Navigate to the URL and wait until network activity settles,
            # giving JS frameworks time to render the page content
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle")

            # Get the fully rendered HTML from the DOM
            rendered_html = await page.content()

            # Close browser to free resources
            await browser.close()

        # Clean the rendered HTML using the same shared helper
        return _clean_html(rendered_html)

    except Exception as e:
        print(f"[Playwright Fallback Error] Could not render {url}: {e}")
        return ""


def scrape_menu_text(url: str) -> str:
    """
    Scrape all visible text content from a restaurant website.

    Strategy:
        1. First attempt with requests + BeautifulSoup (fast, lightweight).
        2. If the result is under 200 characters (likely a JS-rendered page),
          automatically fall back to Playwright headless Chromium.
        3. If Playwright also fails, return whatever partial text exists.

    Args:
        url: The full URL of the restaurant website.

    Returns:
        A cleaned plain-text string of the page's visible content,
        or an empty string if both methods fail.
    """

    # ------------------------------------------------------------------
    # Step 1: Fast path — requests + BeautifulSoup
    # ------------------------------------------------------------------
    bs_text = ""  # will hold the initial scrape result
    try:
        # Set a realistic User-Agent header to avoid being blocked
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        # Fetch the page HTML with a 15-second timeout
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        # Parse and clean the HTML
        bs_text = _clean_html(response.text)

    except requests.RequestException as e:
        print(f"[Scraper Error] Could not fetch {url}: {e}")
        # bs_text stays empty — we'll still try Playwright below

    # ------------------------------------------------------------------
    # Step 2: Check if the page looks JS-rendered (too little text)
    # ------------------------------------------------------------------
    if not is_js_rendered(bs_text):
        # Got enough text from the static scrape — return it directly
        return bs_text

    # ------------------------------------------------------------------
    # Step 3: Fallback — Playwright headless Chromium for JS-heavy sites
    # ------------------------------------------------------------------
    print(f"[Scraper] Text too short ({len(bs_text.strip())} chars), "
          f"falling back to Playwright for {url}")

    try:
        # Run the async Playwright scraper in a synchronous context
        pw_text = asyncio.run(_scrape_with_playwright(url))
    except Exception as e:
        # If Playwright completely fails, return whatever we got from BS
        print(f"[Playwright Error] {e} — returning partial text")
        pw_text = ""

    # Return whichever result has more content
    return pw_text if len(pw_text) > len(bs_text) else bs_text
