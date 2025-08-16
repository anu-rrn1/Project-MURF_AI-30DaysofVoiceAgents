import logging
import os
import time
from dotenv import load_dotenv
import assemblyai as aai
from fastapi import HTTPException, UploadFile
load_dotenv()
logger = logging.getLogger(__name__)

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

async def transcribe_audio(file: UploadFile) -> str:
    """
    Handles the audio transcription process with AssemblyAI using their official SDK.

    Args:
        file: The audio file uploaded by the user (FastAPI UploadFile).

    Returns:
        The transcribed text from the audio.

    Raises:
        HTTPException: If AssemblyAI API key is missing, or if the transcription fails.
    """
    if not ASSEMBLYAI_API_KEY:
        logger.error("AssemblyAI API key is not configured.")
        raise HTTPException(status_code=500, detail="AssemblyAI API key is not configured.")

    try:
        # Set the API key globally for the AssemblyAI SDK
        aai.settings.api_key = ASSEMBLYAI_API_KEY
        transcriber = aai.Transcriber()

        logger.info(f"Starting transcription for file: {file.filename}...")

        # The SDK can take a file-like object directly.
        # file.file is a SpooledTemporaryFile, which is a file-like object.
        # We need to ensure the file pointer is at the beginning if read previously.
        await file.seek(0) # Ensure the file pointer is at the start

        # Configure transcription settings (e.g., speech model)
        # You can add more configurations here as needed, e.g., language_code
        config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best) # Using 'best' model

        # Perform the transcription. The SDK handles upload, polling, and status checks.
        transcript = transcriber.transcribe(file.file, config)

        if transcript.status == aai.TranscriptStatus.completed:
            transcription_text = transcript.text
            if not transcription_text:
                logger.warning("AssemblyAI returned empty transcription text.")
                raise HTTPException(status_code=500, detail="AssemblyAI returned empty transcription text.")
            logger.info(f"Transcription completed for file {file.filename}.")
            return transcription_text
        elif transcript.status == aai.TranscriptStatus.error:
            error_msg = transcript.error or "Unknown transcription error from AssemblyAI."
            logger.error(f"AssemblyAI transcription failed: {error_msg}")
            raise HTTPException(status_code=500, detail=f"AssemblyAI transcription failed: {error_msg}")
        else:
            # This case should ideally not be reached with typical SDK usage
            # unless an unexpected status occurs without an error
            logger.error(f"AssemblyAI transcription ended with unexpected status: {transcript.status}")
            raise HTTPException(status_code=500, detail=f"AssemblyAI transcription ended with unexpected status: {transcript.status}")

    except aai.APIError as e:
        logger.error(f"AssemblyAI API error: {e}", exc_info=True)
        # Translate common API errors to appropriate HTTP exceptions
        if "rate limit" in str(e).lower():
            raise HTTPException(status_code=429, detail=f"AssemblyAI API rate limit exceeded: {e}")
        elif "authentication" in str(e).lower() or "api key" in str(e).lower():
            raise HTTPException(status_code=401, detail=f"AssemblyAI API authentication error. Check your API key: {e}")
        else:
            raise HTTPException(status_code=502, detail=f"AssemblyAI API general error: {e}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during AssemblyAI transcription: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred during transcription: {e}")

