"""
Munchr — Gemini AI Cooking Assistant Module
Uses Google Gemini 2.5 Flash to suggest ingredient substitutions
in the context of a specific recipe being viewed.

Uses the google-genai SDK.
"""

import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def suggest_substitutes(recipe_title: str, ingredients: list[str], user_query: str) -> list[dict] | dict:
    """
    Ask Gemini for ingredient substitutions tailored to a specific recipe.
    Supports single or multiple missing ingredients in one query.

    Args:
        recipe_title: The name of the recipe (e.g. "Gigi Hadid Pasta").
        ingredients: The full list of ingredients for the recipe.
        user_query: The user's question (e.g. "I don't have olive oil and pepper").

    Returns:
        A list of dicts, each with keys: substitute, ratio, flavour_note, tip.
        On failure, returns a single dict with an "error" key.
    """

    # ------------------------------------------------------------------
    # Step 1: Load the Gemini API key from environment variables
    # ------------------------------------------------------------------
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY not found in environment variables. "
                        "Create a .env file from .env.example and add your key."}

    # Create a Gemini client with the API key
    client = genai.Client(api_key=api_key)

    # ------------------------------------------------------------------
    # Step 2: Build the structured prompt for Gemini
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
    # ------------------------------------------------------------------
    max_attempts = 2
    raw_response = ""

    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4 if attempt > 0 else 0.7,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                ),
            )

            raw_response = response.text.strip()

            # Strip markdown fences if present
            if raw_response.startswith("```"):
                raw_response = raw_response.split("\n", 1)[1] if "\n" in raw_response else raw_response[3:]
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3].strip()

            result = json.loads(raw_response)

            # If Gemini returned a single object instead of an array, wrap it
            if isinstance(result, dict):
                result = [result]

            # Validate: ensure every item is a dict with the expected keys
            validated = []
            for item in result:
                if not isinstance(item, dict):
                    continue
                validated.append({
                    "ingredient": item.get("ingredient", ""),
                    "substitute": item.get("substitute", "N/A"),
                    "ratio": item.get("ratio", "N/A"),
                    "flavour_note": item.get("flavour_note", "N/A"),
                    "tip": item.get("tip", "N/A"),
                })

            if validated:
                return validated

            # If no valid items, retry
            continue

        except json.JSONDecodeError:
            # Retry on parse failure
            if attempt < max_attempts - 1:
                continue
            return {"error": "Gemini returned an invalid response. Please try again."}

        except Exception as e:
            return {"error": f"Gemini API call failed: {e}"}

    return {"error": "Gemini returned an invalid response after retrying. Please try again."}
