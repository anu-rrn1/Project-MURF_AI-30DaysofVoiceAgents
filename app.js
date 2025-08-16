// app.js
let mediaRecorder;
let audioChunks = [];
let session_id;

const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const statusText = document.getElementById("status");
const spinner = document.getElementById("spinner");
const audioPlayer = document.getElementById("audioPlayer");
const geminiText = document.getElementById("geminiText");

// --- Session ID Management ---
/**
 * Retrieves a session ID from the URL parameters or generates a new one.
 * If a new ID is generated, it updates the URL to reflect it.
 * @returns {string} The current session ID.
 */
function getOrCreateSessionId() {
    const urlParams = new URLSearchParams(window.location.search);
    let id = urlParams.get('session_id');
    if (!id) {
        // Generate a new UUID if no session ID exists
        id = self.crypto.randomUUID(); 
        // Update the browser's URL without reloading the page
        window.history.pushState(null, '', `?session_id=${id}`);
    }
    return id;
}

// Initialize session ID when the script loads
session_id = getOrCreateSessionId();
console.log(`Current Session ID: ${session_id}`);

// --- Core Recording and Processing Logic ---
/**
 * Starts the audio recording process.
 * Requests microphone access, initializes MediaRecorder, and sets up event listeners.
 */
async function startRecording() {
    try {
        // Request access to the user's microphone
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // Create a MediaRecorder instance to record audio
        mediaRecorder = new MediaRecorder(stream);
        // Clear previous audio chunks
        audioChunks = [];

        // Event handler for when audio data is available
        mediaRecorder.ondataavailable = e => {
            if (e.data.size > 0) {
                audioChunks.push(e.data);
            }
        };

        // Event handler for when recording stops
        mediaRecorder.onstop = async () => {
            // Combine recorded audio chunks into a single Blob
            const blob = new Blob(audioChunks, { type: 'audio/webm' });
            // Create FormData to send the audio file to the server
            const formData = new FormData();
            formData.append('file', blob, 'recording.webm');
            
            // Update UI to show processing status
            statusText.textContent = "Processing your request...";
            spinner.style.display = "block"; // Show loading spinner

            try {
                // Send the audio file to the FastAPI backend with the session ID
                const res = await fetch(`http://127.0.0.1:8000/agent/chat/${session_id}`, {
                    method: "POST",
                    body: formData
                });
                
                // Parse the JSON response from the server
                const data = await res.json();
                spinner.style.display = "none"; // Hide loading spinner
                
                // Check if the response contains both text and audio URL
                if (data.gemini_text && data.audio_url) {
                    geminiText.textContent = data.gemini_text; // Display Gemini's text response
                    audioPlayer.src = data.audio_url;       // Set audio player source
                    audioPlayer.style.display = "block";     // Show audio player
                    audioPlayer.play();                      // Play the audio response
                    statusText.textContent = "✅ Response ready! I am listening again...";
                } else {
                    // Handle incomplete or invalid server response
                    throw new Error(data.detail || "Incomplete response from server. Missing text or audio URL.");
                }
            } catch (err) {
                // Handle errors during the fetch operation (e.g., network issues, server errors)
                spinner.style.display = "none"; // Hide spinner on error
                statusText.textContent = "❌ Error processing: " + err.message;
                console.error("Error during fetch:", err);
            }
        };

        // Start the recording
        mediaRecorder.start();
        // Update button states and status text
        recordBtn.disabled = true;
        stopBtn.disabled = false;
        statusText.textContent = "🎤 Recording...";
        // Clear previous content
        geminiText.textContent = "No response yet.";
        audioPlayer.style.display = "none";
        audioPlayer.src = ""; // Clear previous audio source
    } catch (err) {
        // Handle errors if microphone access is denied or other media device issues
        statusText.textContent = "❌ Mic access denied. Please allow microphone access.";
        console.error("Error accessing microphone:", err);
    }
}

// --- Event Listeners ---
// Assign click event to the "Start Recording" button
recordBtn.onclick = startRecording;

// Assign click event to the "Stop Recording" button
stopBtn.onclick = () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop(); // Stop the recording
    }
    // Update button states
    recordBtn.disabled = false;
    stopBtn.disabled = true;
};

// --- Auto-record after audio playback finishes ---
// Listen for the 'ended' event on the audio player
audioPlayer.addEventListener('ended', () => {
    // Wait a moment before restarting to avoid capturing the end of the audio or immediate re-triggering
    setTimeout(() => {
        // Only auto-start if the record button is not already disabled (i.e., not already recording)
        if (!recordBtn.disabled) { 
            startRecording();
        }
    }, 500); // 500ms delay
});
