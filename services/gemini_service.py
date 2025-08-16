import logging
import os
import time

import requests
from fastapi import HTTPException

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def generate_gemini_response(chat_history: list[dict]) -> str:
    """
    Generates a text response using the Google Gemini API based on the chat history.
    Includes retry mechanism for API calls.

    Args:
        chat_history: A list of dictionaries representing the conversation history,
                      e.g., [{"role": "user", "content": "hello"}, {"role": "model", "content": "hi"}]

    Returns:
        The generated text response from Gemini.

    Raises:
        HTTPException: If Gemini API key is missing, or if the API call fails or
                       returns an unexpected response.
    """
    if not GEMINI_API_KEY:
        logger.error("Gemini API key is not configured.")
        raise HTTPException(status_code=500, detail="Gemini API key is not configured.")

    # Format history for the Gemini API
    gemini_messages = []
    for turn in chat_history:
        # Gemini expects 'user' and 'model' roles.
        role = "user" if turn["role"] == "user" else "model"
        gemini_messages.append({
            "role": role,
            "parts": [{"text": turn["content"]}]
        })
    
    gemini_payload = {"contents": gemini_messages}
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}"
    
    gemini_text = ""
    max_gemini_retries = 3
    gemini_retry_delay = 1 # seconds

    for i in range(max_gemini_retries):
        try:
            logger.info(f"Calling Gemini API (attempt {i+1}/{max_gemini_retries})...")
            gemini_res = requests.post(gemini_url, json=gemini_payload, timeout=60)
            gemini_res.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            gemini_json = gemini_res.json()
            
            # Safely extract the text response
            gemini_text = gemini_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
            
            if not gemini_text:
                logger.warning(f"Gemini returned empty text (attempt {i+1}/{max_gemini_retries}).")
                # If Gemini returns no text, consider it a soft error and retry
                if i < max_gemini_retries - 1:
                    time.sleep(gemini_retry_delay)
                    gemini_retry_delay *= 2
                    continue # Retry immediately
                else:
                    logger.error("Gemini API did not return text content after multiple retries.")
                    raise HTTPException(status_code=502, detail="Gemini API did not return text content after retries.")
            
            logger.info(f"Successfully received response from Gemini API.")
            break # Break out of loop if successful
        except requests.exceptions.Timeout:
            logger.warning(f"Gemini API request timed out (attempt {i+1}/{max_gemini_retries}).")
            if i == max_gemini_retries - 1:
                raise HTTPException(status_code=504, detail="Gemini API request timed out after multiple retries.")
            time.sleep(gemini_retry_delay)
            gemini_retry_delay *= 2
        except requests.exceptions.RequestException as e:
            error_detail = f"Gemini API error: {e}"
            if e.response is not None:
                error_detail += f" - Response: {e.response.text}"
            logger.error(f"Error calling Gemini API (attempt {i+1}/{max_gemini_retries}): {error_detail}", exc_info=True)
            if i == max_gemini_retries - 1:
                raise HTTPException(status_code=502, detail=f"Failed to get response from Gemini API: {error_detail}")
            time.sleep(gemini_retry_delay)
            gemini_retry_delay *= 2
        except KeyError as e:
            logger.error(f"Key error in Gemini response: {e}. Response: {gemini_json}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Unexpected Gemini response structure: {e}")
    
    return gemini_text

