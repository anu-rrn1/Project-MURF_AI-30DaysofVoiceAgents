**🎙️ Voice Conversational Bot with Chat History:**
1. This project is a real-time AI voice assistant that:
2. Listens to your voice 🎤
3. Converts it to text using AssemblyAI Speech-to-Text
4. Sends the text + chat history to Google Gemini API for contextual conversation 🤖
5. Converts the LLM’s reply to speech using Murf API 🔊
6. Plays the AI's voice reply in the browser
7. Automatically starts recording again after the AI finishes speaking, enabling a hands-free, continuous conversation.

**🛠 Technologies Used:**
**Frontend:**
- HTML, CSS, JavaScript (Vanilla)
- Web Audio API (MediaRecorder)
- Fetch API for server communication
**Backend:**
- Python FastAPI (REST API server)
- Requests (for calling AssemblyAI, Gemini, Murf APIs)
- CORS Middleware for frontend-backend communication
**APIs & AI Models:**
- AssemblyAI → Speech-to-Text (STT)
- Google Gemini → Large Language Model
- Murf AI → Text-to-Speech (TTS)
**Datastore:**
- In-memory Python dictionary (prototype-friendly) for session-based chat history

**🏗 Architecture:**
[User Voice] 
     ↓
Browser (MediaRecorder) 
     ↓
POST /agent/chat/{session_id}  
     ↓
[Backend: FastAPI]
  1️⃣ AssemblyAI API → Transcribe
  2️⃣ Fetch chat history for session_id
  3️⃣ Append user message to history
  4️⃣ Gemini API → Get LLM response
  5️⃣ Append AI response to history
  6️⃣ Murf API → Convert to Speech
     ↓
Send {gemini_text, audio_url} back
     ↓
Browser plays audio → Restarts recording

**✨ Features:**
- 🎤 Voice Input: Record audio directly in browser
- 🗣 Speech-to-Text via AssemblyAI
- 🧠 Context-Aware Conversations using Gemini API with chat history
- 🔊 Text-to-Speech using Murf API
- ♻ Continuous Hands-Free Chat — auto-restarts recording after AI speaks
- 💬 Session-based Chat History using session ID in URL
- 🌐 Fully web-based — no app installation required

**How to run this on your laptop:**
- ⚙️ Environment Variables
Create a .env file in the backend folder:
=>
ASSEMBLYAI_API_KEY=your_assemblyai_key
GEMINI_API_KEY=your_gemini_api_key
MURF_API_KEY=your_murf_api_key

**🚀 Setup & Run Instructions**
- 1️⃣ Clone Repository
=>
- git clone https://github.com/yourusername/voice-gemini-murf-chat.git
- cd voice-gemini-murf-chat
- 2️⃣ Backend Setup
- cd backend
- pip install fastapi uvicorn python-dotenv requests
- Create .env with your API keys.
- Run the backend:
- uvicorn main:app --reload
- By default, it runs at:
http://127.0.0.1:8000
- 3️⃣ Frontend Setup
Just open index.html in your browser, or serve it via a simple HTTP server:
cd frontend
python -m http.server 5500
Then visit:
http://localhost:5500/index.html?session_id=123
(session_id can be any unique string to start a new conversation session)

**📡 API Endpoints:**
POST /agent/chat/{session_id}
Description: Handles the full flow (Audio → STT → LLM → TTS → Audio Output) while keeping track of chat history.
Request:
Path Parameter: session_id (string)
Body: file (audio/webm)
Response:
{
  "gemini_text": "Hello! How can I help you?",
  "audio_url": "https://murf.ai/generated_audio.mp3"
}

**🔮 Future Improvements:**
- Replace in-memory chat history with Redis or MongoDB for persistence
- Add speaker diarization for multi-user conversations
- Support multiple languages
- Deploy on cloud (Render, Vercel, Railway, etc.)
