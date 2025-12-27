📌 **Please refer the drive link here for project demo**  
https://drive.google.com/file/d/1n05drrGfnjZDWhRidq2_erRqIixkiJLu/view?usp=drivesdk

📌 **WorkFlow**  
The frontend captures microphone audio and streams it to the backend through a secure WebSocket. The FastAPI backend sends each audio chunk in real time to AssemblyAI for transcription. When AssemblyAI detects the end of speech, it sends a final transcript back to us. The backend forwards that transcript to a Gemini LLM for response. If the query needs a web search, the backend first calls SerpAPI to gather context and then sends that to Gemini. The LLM response is then split into small sentences and each sentence is converted to speech using Murf TTS. These audio chunks are streamed back to the frontend over WebSocket, base64-decoded and played sequentially. The user sees the conversation text in the UI and hears the voice response with very low latency.
