from fastapi import FastAPI, UploadFile, File, HTTPException
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import time
from murf import Murf
import uuid

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_histories = {}

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MURF_API_KEY = os.getenv("MURF_API_KEY")

if not ASSEMBLYAI_API_KEY:
    print("Warning: ASSEMBLYAI_API_KEY not found in .env")
if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY not found in .env")
if not MURF_API_KEY:
    print("Warning: MURF_API_KEY not found in .env")

# Helper function to handle the transcription logic
async def transcribe_audio(file: UploadFile):
    """
    Handles the audio upload and transcription process with AssemblyAI.
    Includes robust error handling and exponential backoff.
    """
    upload_url = "https://api.assemblyai.com/v2/upload"
    headers = {"authorization": ASSEMBLYAI_API_KEY}
    audio_data = await file.read()

    if not ASSEMBLYAI_API_KEY:
        raise HTTPException(status_code=500, detail="AssemblyAI API key is not configured.")

    try:
        # 1️⃣ Upload to AssemblyAI for Speech-to-Text
        res = requests.post(upload_url, headers=headers, data=audio_data, timeout=30)
        res.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        audio_url = res.json()["upload_url"]
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="AssemblyAI upload timed out.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to upload audio to AssemblyAI: {e}")
    except KeyError:
        raise HTTPException(status_code=502, detail="AssemblyAI upload response missing 'upload_url'.")

    try:
        # 2️⃣ Request transcription from AssemblyAI
        trans_req = {"audio_url": audio_url, "language_code": "en_us"}
        trans_res = requests.post("https://api.assemblyai.com/v2/transcript", json=trans_req, headers=headers, timeout=30)
        trans_res.raise_for_status()
        trans_id = trans_res.json()["id"]
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="AssemblyAI transcription request timed out.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to request transcription from AssemblyAI: {e}")
    except KeyError:
        raise HTTPException(status_code=502, detail="AssemblyAI transcription request response missing 'id'.")

    # Wait for transcription to complete with exponential backoff
    max_retries = 10
    retry_delay = 1 # seconds
    for i in range(max_retries):
        try:
            check_res = requests.get(f"https://api.assemblyai.com/v2/transcript/{trans_id}", headers=headers, timeout=30)
            check_res.raise_for_status()
            check_data = check_res.json()

            if check_data["status"] == "completed":
                transcription = check_data["text"]
                if not transcription:
                    raise HTTPException(status_code=500, detail="AssemblyAI returned empty transcription text.")
                return transcription
            elif check_data["status"] == "error":
                error_msg = check_data.get("error", "Unknown transcription error.")
                raise HTTPException(status_code=500, detail=f"AssemblyAI transcription failed: {error_msg}")
            else:
                print(f"AssemblyAI status: {check_data['status']}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 16) # Cap retry delay to prevent excessively long waits
        except requests.exceptions.Timeout:
            print(f"AssemblyAI status check timed out (attempt {i+1}/{max_retries}).")
            if i == max_retries - 1:
                raise HTTPException(status_code=504, detail="AssemblyAI transcription status check timed out after multiple retries.")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 16)
        except requests.exceptions.RequestException as e:
            print(f"Error checking AssemblyAI transcription status (attempt {i+1}/{max_retries}): {e}")
            if i == max_retries - 1:
                raise HTTPException(status_code=502, detail=f"Failed to get transcription status from AssemblyAI: {e}")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 16)
        except KeyError:
            raise HTTPException(status_code=502, detail="AssemblyAI status response missing expected keys.")
    
    raise HTTPException(status_code=504, detail="AssemblyAI transcription did not complete within expected time.")

# Helper function for Murf Text-to-Speech
def generate_murf_audio(text: str):
    """
    Generates audio from text using the Murf client.
    Includes robust error handling.
    """
    if not MURF_API_KEY:
        raise HTTPException(status_code=500, detail="Murf API key is not configured.")

    try:
        murf_client = Murf(api_key=MURF_API_KEY)
        
        # Max length allowed is 3000 characters by Murf.
        # We will truncate as a safety net, although the Gemini prompt aims to keep it short.
        max_murf_text_length = 3000
        if len(text) > max_murf_text_length:
            print(f"Murf API: Text too long ({len(text)} chars). Truncating to {max_murf_text_length} chars.")
            truncated_text = text[:max_murf_text_length]
            last_space_index = truncated_text.rfind(' ')
            if last_space_index != -1:
                truncated_text = truncated_text[:last_space_index]
            text = truncated_text + "..."
            
        tts_response = murf_client.text_to_speech.generate(
            text=text,
            voice_id="en-US-terrell", # Using the suggested voice_id
        )
        audio_url_murf = tts_response.audio_file
        
        if not audio_url_murf:
            raise HTTPException(status_code=502, detail="Murf API did not return an audio URL.")
        
        return audio_url_murf
    except Exception as e: # Catch broader exceptions from the Murf client
        print(f"Error generating audio with Murf API: {e}")
        # Murf client might wrap HTTP errors in its own exception type
        raise HTTPException(status_code=502, detail=f"Failed to generate audio with Murf API: {e}")

@app.post("/agent/chat/{session_id}")
async def agent_chat(session_id: str, file: UploadFile = File(...)):
    """
    Handles a full conversational turn with chat history, using a prompt to control length.
    Includes robust error handling for all steps.
    """
    if session_id not in chat_histories:
        chat_histories[session_id] = []
        print(f"New session created with ID: {session_id}")

    try:
        user_transcript = await transcribe_audio(file)
        print(f"User ({session_id}): {user_transcript}")

        # Append the new user message to the history
        # We add a specific instruction to the first message to control length
        # and ensure it's not repeated in subsequent turns.
        if not chat_histories[session_id]:
            # Initial prompt for the first user message
            instruction = (
                "Please respond concisely, in less than 200 words, focusing on the main point. "
                "Do not mention the word count or character limit in your response."
            )
            chat_histories[session_id].append({"role": "user", "content": f"{instruction} The user said: '{user_transcript}'"})
        else:
            # For subsequent messages, just add the transcription
            chat_histories[session_id].append({"role": "user", "content": user_transcript})

        # Format history for the Gemini API
        gemini_messages = []
        for turn in chat_histories[session_id]:
            # Gemini expects 'user' and 'model' roles.
            # Convert 'assistant' if it was used in previous implementations for 'model'
            role = "user" if turn["role"] == "user" else "model"
            gemini_messages.append({
                "role": role,
                "parts": [{"text": turn["content"]}]
            })
        
        gemini_payload = {"contents": gemini_messages}
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}"
        
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API key is not configured.")

        # Send to Gemini API with retry mechanism
        gemini_text = ""
        max_gemini_retries = 3
        gemini_retry_delay = 1
        for i in range(max_gemini_retries):
            try:
                gemini_res = requests.post(gemini_url, json=gemini_payload, timeout=60)
                gemini_res.raise_for_status()
                gemini_json = gemini_res.json()
                gemini_text = gemini_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
                if not gemini_text:
                    # If Gemini returns no text, consider it a soft error and retry
                    if i < max_gemini_retries - 1:
                        print(f"Gemini returned empty text, retrying ({i+1}/{max_gemini_retries})...")
                        time.sleep(gemini_retry_delay)
                        gemini_retry_delay *= 2
                        continue # Retry immediately
                    else:
                        raise HTTPException(status_code=502, detail="Gemini API did not return text content after retries.")
                break # Break out of loop if successful
            except requests.exceptions.Timeout:
                print(f"Gemini API request timed out (attempt {i+1}/{max_gemini_retries}).")
                if i == max_gemini_retries - 1:
                    raise HTTPException(status_code=504, detail="Gemini API request timed out after multiple retries.")
                time.sleep(gemini_retry_delay)
                gemini_retry_delay *= 2
            except requests.exceptions.RequestException as e:
                # Catch specific HTTP errors from Gemini for better debugging
                error_detail = f"Gemini API error: {e}"
                if e.response is not None:
                    error_detail += f" - Response: {e.response.text}"
                print(f"Error calling Gemini API (attempt {i+1}/{max_gemini_retries}): {error_detail}")
                if i == max_gemini_retries - 1:
                    raise HTTPException(status_code=502, detail=f"Failed to get response from Gemini API: {error_detail}")
                time.sleep(gemini_retry_delay)
                gemini_retry_delay *= 2
            except KeyError as e:
                print(f"Key error in Gemini response: {e}, Response: {gemini_json}")
                raise HTTPException(status_code=502, detail=f"Unexpected Gemini response structure: {e}")
        
        print(f"Gemini ({session_id}): {gemini_text}")
        
        chat_histories[session_id].append({"role": "model", "content": gemini_text})

        audio_url_murf = generate_murf_audio(gemini_text)

        return {
            "gemini_text": gemini_text,
            "audio_url": audio_url_murf
        }

    except HTTPException as he:
        # Re-raise HTTPException directly as it's already formatted
        print(f"Handled HTTP Exception: {he.detail}")
        raise he
    except Exception as e:
        # Catch any other unexpected errors and return a generic 500
        print(f"An unexpected error occurred in agent_chat: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")

