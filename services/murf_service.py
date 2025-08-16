import logging
import os

from fastapi import HTTPException
from murf import Murf

# Attempt to import MurfError. If it's not directly exposed by 'murf',
# we'll fall back to using a generic 'Exception' for broader error catching.
try:
    from murf import MurfError
except ImportError:
    logging.warning("MurfError not directly importable from 'murf'. Falling back to generic Exception handling for Murf API calls.")
    MurfError = Exception # Fallback to a generic exception

logger = logging.getLogger(__name__)

MURF_API_KEY = os.getenv("MURF_API_KEY")

async def generate_murf_audio(text: str) -> str:
    """
    Generates audio from text using the Murf client.
    Includes robust error handling and text truncation to fit Murf's limits.

    Args:
        text: The text string to convert to speech.

    Returns:
        The URL of the generated audio file.

    Raises:
        HTTPException: If Murf API key is missing, or if the audio generation fails.
    """
    if not MURF_API_KEY:
        logger.error("Murf API key is not configured.")
        raise HTTPException(status_code=500, detail="Murf API key is not configured.")

    try:
        murf_client = Murf(api_key=MURF_API_KEY)
        
        # Max length allowed is 3000 characters by Murf.
        # We will truncate as a safety net, although the Gemini prompt aims to keep it short.
        max_murf_text_length = 3000
        if len(text) > max_murf_text_length:
            logger.warning(f"Murf API: Text too long ({len(text)} chars). Truncating to {max_murf_text_length} chars.")
            truncated_text = text[:max_murf_text_length]
            last_space_index = truncated_text.rfind(' ')
            if last_space_index != -1:
                # Ensure truncation doesn't cut a word in half
                truncated_text = truncated_text[:last_space_index]
            text = truncated_text + "..." # Add ellipsis to indicate truncation
            
        logger.info(f"Generating Murf audio for text (length: {len(text)})...")
        tts_response = murf_client.text_to_speech.generate(
            text=text,
            voice_id="en-US-terrell", # Using the suggested voice_id
        )
        audio_url_murf = tts_response.audio_file
        
        if not audio_url_murf:
            logger.error("Murf API did not return an audio URL.")
            raise HTTPException(status_code=502, detail="Murf API did not return an audio URL.")
        
        logger.info(f"Murf audio generated successfully. URL: {audio_url_murf}")
        return audio_url_murf
    except MurfError as e: # Now catches MurfError if successfully imported, or generic Exception
        logger.error(f"Murf client API error: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to generate audio with Murf API: {e}")
    except Exception as e: # Catch any other unexpected errors from the Murf client or system
        logger.exception(f"An unexpected error occurred while generating audio with Murf API: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred during audio generation: {e}")

