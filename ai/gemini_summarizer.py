"""
Munchr — Gemini AI Summarizer Module
Sends scraped restaurant menu text to Google Gemini 1.5 Flash (free tier)
and returns structured dish recommendations, vibe, tips, and price range.
"""

import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def summarize_restaurant(restaurant_name: str, menu_text: str) -> dict:
    """
    Use Google Gemini 1.5 Flash to analyse scraped menu text and return
    a structured summary with dish recommendations and practical info.

    Args:
        restaurant_name: The name of the restaurant (used in the prompt).
        menu_text: Plain-text content scraped from the restaurant's website.

    Returns:
        A dict with keys:
            - top_dishes: list of 5 dicts, each with "dish" and "description"
            - vibe: one-sentence atmosphere description
            - practical_tips: list of 2-3 short tips for visitors
            - price_range: one of "$", "$$", "$$$"
        On failure, returns a dict with an "error" key describing the issue.
    """

    # ------------------------------------------------------------------
    # Step 1: Load the Gemini API key from environment variables
    # ------------------------------------------------------------------
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY not found in environment variables. "
                        "Create a .env file from .env.example and add your key."}

    # Configure the Gemini client with the API key
    genai.configure(api_key=api_key)

    # ------------------------------------------------------------------
    # Step 2: Build the structured prompt for Gemini
    # ------------------------------------------------------------------
    prompt = f"""You are a helpful Vancouver food critic and restaurant advisor.

I scraped the following text from the website of a restaurant called "{restaurant_name}".
Analyse the text and return a JSON object (and ONLY a JSON object, no markdown fences) with these exact keys:

{{
  "top_dishes": [
    {{"dish": "Dish Name", "description": "One-line description of why it's great"}},
    ... (exactly 5 dishes)
  ],
  "vibe": "One sentence describing the restaurant's atmosphere and style.",
  "practical_tips": [
    "Tip 1 (e.g. reservations recommended)",
    "Tip 2 (e.g. limited parking nearby)",
    "Tip 3 (optional)"
  ],
  "price_range": "$"  // one of "$", "$$", or "$$$" based on the menu prices
}}

If the text does not contain enough information for a field, make a reasonable
inference based on the restaurant name and whatever context is available.

--- START OF SCRAPED TEXT ---
{menu_text}
--- END OF SCRAPED TEXT ---

Return ONLY the JSON object. No extra text, no markdown code fences."""

    # ------------------------------------------------------------------
    # Step 3: Send the prompt to Gemini 1.5 Flash
    # ------------------------------------------------------------------
    try:
        # Use Gemini 1.5 Flash — free tier model with generous rate limits
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Generate the response with a temperature of 0.7 for balanced creativity
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1024,
            ),
        )

        # Extract the text from the response
        raw_response = response.text.strip()

        # ------------------------------------------------------------------
        # Step 4: Parse the JSON response
        # ------------------------------------------------------------------
        # Sometimes Gemini wraps output in ```json ... ``` fences — strip them
        if raw_response.startswith("```"):
            # Remove opening fence (```json or ```)
            raw_response = raw_response.split("\n", 1)[1] if "\n" in raw_response else raw_response[3:]
        if raw_response.endswith("```"):
            raw_response = raw_response[:-3].strip()

        # Parse the cleaned JSON string into a Python dict
        result = json.loads(raw_response)

        # Validate that expected keys are present
        expected_keys = {"top_dishes", "vibe", "practical_tips", "price_range"}
        if not expected_keys.issubset(result.keys()):
            missing = expected_keys - result.keys()
            return {"error": f"Gemini response missing keys: {missing}",
                    "raw_response": raw_response}

        return result

    except json.JSONDecodeError as e:
        # Gemini returned something that isn't valid JSON
        return {"error": f"Failed to parse Gemini response as JSON: {e}",
                "raw_response": raw_response if 'raw_response' in locals() else "N/A"}

    except Exception as e:
        # Catch-all for API errors, network issues, rate limits, etc.
        return {"error": f"Gemini API call failed: {e}"}
