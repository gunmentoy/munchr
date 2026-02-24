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


def suggest_substitutes(recipe_title: str, ingredients: list[str], user_query: str) -> dict:
    """
    Ask Gemini for an ingredient substitution tailored to a specific recipe.

    Args:
        recipe_title: The name of the recipe (e.g. "Gigi Hadid Pasta").
        ingredients: The full list of ingredients for the recipe.
        user_query: The user's question (e.g. "I don't have heavy cream, what can I use?").

    Returns:
        A dict with keys:
            - substitute: the recommended substitute ingredient
            - ratio: how much to use (e.g. "use the same amount")
            - flavour_note: one sentence on how it may change the taste
            - tip: one practical cooking tip related to the substitution
        On failure, returns a dict with an "error" key describing the issue.
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

A user is cooking the following recipe and needs help with an ingredient substitution.

**Recipe:** {recipe_title}

**Full ingredients list:**
{ingredients_text}

**User's question:** {user_query}

Based on the specific recipe and its ingredients, suggest the best substitution.
Return a JSON object (and ONLY a JSON object, no markdown fences) with these exact keys:

{{
  "substitute": "The recommended substitute ingredient",
  "ratio": "How much to use (e.g. 'use the same amount', '1/2 cup instead of 1 cup')",
  "flavour_note": "One sentence on how the substitution may change the taste or texture.",
  "tip": "One practical cooking tip related to this substitution in this specific recipe."
}}

Return ONLY the JSON object. No extra text, no markdown code fences."""

    # ------------------------------------------------------------------
    # Step 3: Send the prompt to Gemini 2.5 Flash
    # ------------------------------------------------------------------
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=1024,
                response_mime_type="application/json",
            ),
        )

        # Extract the text from the response
        raw_response = response.text.strip()

        # ------------------------------------------------------------------
        # Step 4: Parse the JSON response
        # ------------------------------------------------------------------
        # Safety: strip markdown fences if they somehow still appear
        if raw_response.startswith("```"):
            raw_response = raw_response.split("\n", 1)[1] if "\n" in raw_response else raw_response[3:]
        if raw_response.endswith("```"):
            raw_response = raw_response[:-3].strip()

        # Parse the cleaned JSON string into a Python dict
        result = json.loads(raw_response)

        # Validate that expected keys are present
        expected_keys = {"substitute", "ratio", "flavour_note", "tip"}
        if not expected_keys.issubset(result.keys()):
            missing = expected_keys - result.keys()
            return {"error": f"Gemini response missing keys: {missing}",
                    "raw_response": raw_response}

        return result

    except json.JSONDecodeError as e:
        # Gemini returned something that isn't valid JSON
        return {"error": f"Failed to parse Gemini response as JSON: {e}",
                "raw_response": raw_response if "raw_response" in locals() else "N/A"}

    except Exception as e:
        # Catch-all for API errors, network issues, rate limits, etc.
        return {"error": f"Gemini API call failed: {e}"}
