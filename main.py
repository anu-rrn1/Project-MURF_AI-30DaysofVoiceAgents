import logging
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from schemas import ChatResponse
from services.assemblyai_service import transcribe_audio
from services.gemini_service import generate_gemini_response
from services.murf_service import generate_murf_audio

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Voice Chat Agent API",
    description="API for a voice-enabled chat agent using AssemblyAI, Gemini, and Murf.",
    version="1.0.0"
)

# Configure CORS middleware to allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for chat histories. In a production environment, use a proper database.
chat_histories: dict[str, list[dict]] = {}

# Check for API keys at startup
REQUIRED_ENV_VARS = ["ASSEMBLYAI_API_KEY", "GEMINI_API_KEY", "MURF_API_KEY"]
for var in REQUIRED_ENV_VARS:
    if not os.getenv(var):
        logger.warning(f"Warning: Environment variable '{var}' not found. Some functionalities may be limited.")


@app.post("/agent/chat/{session_id}", response_model=ChatResponse)
async def agent_chat(session_id: str, file: UploadFile = File(...)):
    """
    Handles a full conversational turn with chat history.
    1. Transcribes user audio using AssemblyAI.
    2. Generates a text response using Google Gemini, maintaining chat context.
    3. Converts Gemini's text response to audio using Murf.
    """
    if session_id not in chat_histories:
        chat_histories[session_id] = []
        logger.info(f"New session created with ID: {session_id}")

    try:
        # 1. Transcribe user's audio
        logger.info(f"[{session_id}] - Starting audio transcription...")
        user_transcript = await transcribe_audio(file)
        logger.info(f"[{session_id}] - User transcript: '{user_transcript}'")

        # Prepare chat history for Gemini
        # We add a specific instruction to the first message to control length
        # and ensure it's not repeated in subsequent turns.
        if not chat_histories[session_id]:
            # Initial prompt for the first user message to guide Gemini's response length
            instruction = (
                "Please respond concisely, in less than 200 words, focusing on the main point. "
                "Do not mention the word count or character limit in your response."
            )
            chat_histories[session_id].append({"role": "user", "content": f"{instruction} The user said: '{user_transcript}'"})
        else:
            # For subsequent messages, just add the transcription
            chat_histories[session_id].append({"role": "user", "content": user_transcript})
        
        # 2. Generate response using Gemini
        logger.info(f"[{session_id}] - Generating Gemini response...")
        gemini_text = await generate_gemini_response(chat_histories[session_id])
        logger.info(f"[{session_id}] - Gemini response: '{gemini_text}'")

        # Append Gemini's response to the chat history
        chat_histories[session_id].append({"role": "model", "content": gemini_text})

        # 3. Generate audio from Gemini's text response using Murf
        logger.info(f"[{session_id}] - Generating Murf audio...")
        audio_url_murf = await generate_murf_audio(gemini_text)
        logger.info(f"[{session_id}] - Murf audio URL: {audio_url_murf}")

        return ChatResponse(
            gemini_text=gemini_text,
            audio_url=audio_url_murf
        )

    except HTTPException as he:
        # Re-raise HTTPException directly as it's already formatted
        logger.error(f"[{session_id}] - Handled HTTP Exception: {he.detail} (Status: {he.status_code})")
        raise he
    except Exception as e:
        # Catch any other unexpected errors and return a generic 500
        logger.exception(f"[{session_id}] - An unexpected error occurred in agent_chat: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")

