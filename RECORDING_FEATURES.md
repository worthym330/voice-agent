# Voice Agent - Enhanced with Call Recording & Conversation Logging

## New Features Added ✨

### 1. Call Recording 📹
- **Automatic call recording** starts when the conversation begins
- Records all audio (both user speech and system responses)
- Saves as `.wav` file with timestamp: `call_recording_YYYYMMDD_HHMMSS.wav`
- User is notified that the call is being recorded

### 2. Conversation Logging 💬
- **Real-time conversation logging** to JSON file
- Records every interaction with timestamps
- Saves as: `conversation_YYYYMMDD_HHMMSS.json`
- Includes:
  - User speech (what you said)
  - Assistant responses 
  - System messages (errors, notifications)
  - Precise timestamps

### 3. Single Voice Output 🔊
- **Fixed multiple voice issue** using thread locks
- Only one audio plays at a time
- Prevents overlapping speech
- Cleaner, more professional conversation flow

### 4. Recording Notification 📢
- User is informed at the start: *"This call is being recorded for quality and training purposes"*
- Available in both English and Hindi
- Complies with recording disclosure requirements

## Generated Files 📁

After each conversation, you'll find:

1. **`call_recording_YYYYMMDD_HHMMSS.wav`** - Complete audio recording
2. **`conversation_YYYYMMDD_HHMMSS.json`** - Detailed conversation log

### Sample Conversation Log Format:
```json
[
  {
    "timestamp": "2025-01-23 14:30:15",
    "speaker": "SYSTEM",
    "text": "Call recording started"
  },
  {
    "timestamp": "2025-01-23 14:30:16",
    "speaker": "ASSISTANT", 
    "text": "This call is being recorded for quality and training purposes."
  },
  {
    "timestamp": "2025-01-23 14:30:25",
    "speaker": "USER",
    "text": "tell me about the house"
  },
  {
    "timestamp": "2025-01-23 14:30:26",
    "speaker": "ASSISTANT",
    "text": "I'd be happy to tell you about the property we're selling to Basant..."
  }
]
```

## How to Run 🚀

```bash
python main.py
```

The system will:
1. ✅ Start recording automatically
2. ✅ Notify you about recording
3. ✅ Ask for language preference
4. ✅ Begin the real estate conversation
5. ✅ Log everything in real-time
6. ✅ Save files when conversation ends

## Requirements 📋

All dependencies are in `requirement.txt`:
- google-generativeai
- SpeechRecognition
- elevenlabs
- pygame (for audio playback)
- pyttsx3 (backup TTS)
- And standard Python libraries

## Privacy & Compliance 🔒

- Recording disclosure at conversation start
- Local file storage (not uploaded anywhere)
- User has full control over recorded files
- Compliant with call recording regulations
