"""
Munchr — Gemini AI Cooking Assistant Module

This module handles all AI-powered functionality in the Munchr app.
Its main job is to take a recipe's ingredient list and a user's question
(e.g. "I don't have heavy cream") and return structured substitution
suggestions using Google's Gemini AI model.

Key design decisions:
  - Uses the google-genai SDK (not the deprecated google-generativeai)
  - Forces JSON output via response_mime_type="application/json" so we
    don't have to parse free-text responses
  - Supports multiple missing ingredients in a single query by returning
    a JSON array of substitution objects
  - Includes automatic retry logic (up to 2 attempts) for robustness

Libraries used:
  - google-genai     → Google's official Gemini AI SDK
  - python-dotenv    → Loads the API key from a .env file securely
  - json             → Parses the structured JSON response from Gemini
"""

import os    # For reading environment variables
import json  # For parsing Gemini's JSON response
from google import genai            # Google Gemini AI SDK client
from google.genai import types      # Configuration types for the API call
from dotenv import load_dotenv      # Loads .env file into os.environ

# Load environment variables from the .env file at project root.
# This is where GEMINI_API_KEY is stored (never hardcoded or committed to Git).
load_dotenv()


def suggest_substitutes(recipe_title: str, ingredients: list[str], user_query: str) -> list[dict] | dict:
    """
    Ask Gemini for ingredient substitutions tailored to a specific recipe.

    This is the main AI function of the app. It takes the context of what
    the user is cooking (recipe title + full ingredient list) and their
    question about missing ingredients, then asks Gemini to suggest the
    best substitutes with practical cooking advice.

    Supports single or multiple missing ingredients in one query.
    For example: "I don't have olive oil and pepper" will return two
    separate substitution suggestions.

    Args:
        recipe_title: The name of the recipe (e.g. "Gigi Hadid Pasta").
        ingredients:  The full list of ingredients for the recipe.
        user_query:   The user's natural language question about what
                      they're missing (e.g. "I don't have olive oil and pepper").

    Returns:
        On success: A list of dicts, each containing:
            - ingredient:   The original ingredient being replaced
            - substitute:   The recommended substitute
            - ratio:        How much to use (e.g. "use the same amount")
            - flavour_note: How the substitution may change taste/texture
            - tip:          A practical cooking tip for this substitution
        On failure: A single dict with an "error" key describing the issue.
    """

    # ------------------------------------------------------------------
    # Step 1: Load the Gemini API key from environment variables
    #
    # The API key is stored in a .env file (not committed to Git).
    # If it's missing, we return a helpful error message instead of crashing.
    # ------------------------------------------------------------------
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY not found in environment variables. "
                        "Create a .env file from .env.example and add your key."}

    # Create a Gemini client instance. This is the main entry point for
    # all Gemini API calls using the google-genai SDK.
    client = genai.Client(api_key=api_key)

    # ------------------------------------------------------------------
    # Step 2: Build the structured prompt for Gemini
    #
    # The prompt includes:
    #   - The AI's persona (friendly cooking assistant)
    #   - Full context (recipe name + complete ingredient list)
    #   - The user's specific question
    #   - Exact JSON schema we expect back
    #
    # We ask for a JSON array so the model can return multiple
    # substitutions if the user mentions multiple missing ingredients.
    # ------------------------------------------------------------------
    ingredients_text = "\n".join(f"- {ing}" for ing in ingredients)

    prompt = f"""You are a friendly, knowledgeable cooking assistant called Munchr AI.

A user is cooking the following recipe and needs help with ingredient substitutions.

**Recipe:** {recipe_title}

**Full ingredients list:**
{ingredients_text}

**User's question:** {user_query}

Based on the specific recipe and its ingredients, suggest the best substitution for EACH missing ingredient the user mentions.

Return a JSON **array** of objects (and ONLY a JSON array, no markdown fences).
Each object must have these exact keys:

{{
  "ingredient": "The original ingredient being replaced",
  "substitute": "The recommended substitute",
  "ratio": "How much to use (e.g. 'use the same amount')",
  "flavour_note": "One sentence on how the substitution may change the taste or texture.",
  "tip": "One practical cooking tip for this substitution in this recipe."
}}

If the user only asks about one ingredient, return an array with one object.
Return ONLY the JSON array. No extra text, no markdown code fences."""

    # ------------------------------------------------------------------
    # Step 3: Send the prompt to Gemini (with retry on bad JSON)
    #
    # We use response_mime_type="application/json" to force Gemini to
    # return valid JSON natively. However, even with this setting,
    # responses can occasionally be malformed. So we retry once with
    # a lower temperature (more deterministic) if the first attempt
    # fails to parse.
    # ------------------------------------------------------------------
    max_attempts = 2   # Try up to 2 times before giving up
    raw_response = ""  # Store raw text for debugging if parsing fails

    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    # Lower temperature on retry = more deterministic output
                    temperature=0.4 if attempt > 0 else 0.7,
                    # 2048 tokens is generous enough for multi-ingredient responses
                    max_output_tokens=2048,
                    # This forces Gemini to return valid JSON (not free text)
                    response_mime_type="application/json",
                ),
            )

            raw_response = response.text.strip()

            # Safety: strip markdown code fences if they somehow appear
            # (shouldn't happen with response_mime_type, but just in case)
            if raw_response.startswith("```"):
                raw_response = raw_response.split("\n", 1)[1] if "\n" in raw_response else raw_response[3:]
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3].strip()

            # Parse the JSON string into a Python object
            result = json.loads(raw_response)

            # If Gemini returned a single object instead of an array, wrap it.
            # This can happen when the user asks about only one ingredient.
            if isinstance(result, dict):
                result = [result]

            # ----------------------------------------------------------
            # Step 4: Validate each item in the response
            #
            # Gemini sometimes returns unexpected structures (strings
            # instead of dicts, missing keys, etc.). We validate each
            # item and only keep properly-formed substitution objects.
            # .get() with defaults ensures we never crash on missing keys.
            # ----------------------------------------------------------
            validated = []
            for item in result:
                # Skip any items that aren't dicts (e.g. if Gemini
                # returned a string or number in the array)
                if not isinstance(item, dict):
                    continue
                validated.append({
                    "ingredient": item.get("ingredient", ""),
                    "substitute": item.get("substitute", "N/A"),
                    "ratio": item.get("ratio", "N/A"),
                    "flavour_note": item.get("flavour_note", "N/A"),
                    "tip": item.get("tip", "N/A"),
                })

            # If we got at least one valid substitution, return it
            if validated:
                return validated

            # No valid items — retry
            continue

        except json.JSONDecodeError:
            # JSON parsing failed — retry with lower temperature
            if attempt < max_attempts - 1:
                continue
            return {"error": "Gemini returned an invalid response. Please try again."}

        except Exception as e:
            # Catch-all for API errors, network issues, rate limits, etc.
            return {"error": f"Gemini API call failed: {e}"}

    # If we exhausted all retries without a valid response
    return {"error": "Gemini returned an invalid response after retrying. Please try again."}
