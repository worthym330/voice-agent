import google.generativeai as genai
import speech_recognition as sr
import os
from fuzzywuzzy import process
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from elevenlabs import ElevenLabs
import time
import pygame
import io
import tempfile
import wave
import threading
from datetime import datetime
import json

# Load environment variables
load_dotenv()

# Load API Keys from Environment Variables
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize ElevenLabs client
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Initialize Gemini model
model = genai.GenerativeModel('gemini-2.0-flash')

# Global variables for recording and conversation logging
is_recording = False
recording_frames = []
conversation_log = []
conversation_start_time = None
current_audio_lock = threading.Lock()  # Prevent multiple audio playback


# Real Estate Assistant Configuration
# This assistant helps with selling home to Basant and supports Hindi/English communication

# Sample property information (you can customize this for your specific property)
PROPERTY_INFO = {
    "location": "Your property location here",
    "price": "Your asking price here", 
    "features": "Key features of your property",
    "buyer_name": "Basant"
}


# Function to detect and set language preference
def get_language_preference():
    """Ask user for their preferred language and return the choice."""
    speak("Hello! नमस्ते! I can speak in English, Hindi, or both. Which language would you prefer? आप कौन सी भाषा पसंद करेंगे - English, Hindi, या दोनों?")
    
    max_attempts = 3
    for attempt in range(max_attempts):
        response = recognize_speech()
        if not response:
            if attempt < max_attempts - 1:
                speak("I didn't catch that. Please say English, Hindi, or both. मैंने नहीं सुना, कृपया English, Hindi या both कहें।")
                continue
            else:
                speak("I'll use both languages to help you. मैं दोनों भाषाओं का उपयोग करूंगा।")
                return "both"
        
        response = response.lower()
        
        # Check for language preferences
        if any(word in response for word in ["english", "इंग्लिश", "अंग्रेजी"]):
            speak("Great! I'll communicate in English.")
            return "english"
        elif any(word in response for word in ["hindi", "हिंदी", "हिन्दी"]):
            speak("बहुत अच्छा! मैं हिंदी में बात करूंगा।")
            return "hindi"
        elif any(word in response for word in ["both", "दोनों", "mix", "mixed"]):
            speak("Perfect! I'll use both languages as needed. बहुत बढ़िया!")
            return "both"
        else:
            if attempt < max_attempts - 1:
                speak("Please choose English, Hindi, or both. कृपया English, Hindi या both में से चुनें।")
            else:
                speak("I'll use both languages to help you. मैं दोनों भाषाओं का उपयोग करूंगा।")
                return "both"
    
    return "both"  # Default fallback
# Function to get intelligent response from Gemini
def get_gemini_response(question, language_pref="both"):
    """Use Gemini AI to generate intelligent responses for home selling queries."""
    try:
        # Create language-specific instructions
        language_instruction = ""
        if language_pref == "english":
            language_instruction = "Respond only in English."
        elif language_pref == "hindi":
            language_instruction = "Respond only in Hindi using proper Devanagari script."
        else:  # both or mixed
            language_instruction = "Respond in the same language the user used, or mix Hindi and English naturally if appropriate."
        
        # Create a prompt for selling home to Basant
        prompt = f"""
        You are a helpful real estate assistant helping to sell a home to Basant. 
        
        Language preference: {language_instruction}
        
        A customer has asked: "{question}"
        
        Please provide a helpful, concise response (2-3 sentences max) that:
        1. If the question is about selling a home, property details, pricing, or real estate - provide helpful information
        2. If they mention Basant or ask about the buyer, be enthusiastic about connecting them
        3. If they ask about property features, location benefits, or selling process - provide relevant details
        4. Keep the tone friendly, professional, and encouraging about the sale
        5. If the question is completely unrelated to real estate, politely redirect to the main topic
        
        Important: Follow the language preference strictly. If Hindi is requested or preferred, use proper Devanagari script and natural Hindi phrases.
        
        Response:
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        print(f"Error with Gemini API: {e}")
        return None

# Function to log conversation
def log_conversation(speaker, text, timestamp=None):
    """Log conversation to both memory and file."""
    global conversation_log
    
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_entry = {
        "timestamp": timestamp,
        "speaker": speaker,
        "text": text
    }
    
    conversation_log.append(log_entry)
    
    # Also write to file immediately
    log_filename = f"conversation_{conversation_start_time.strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(log_filename, 'w', encoding='utf-8') as f:
            json.dump(conversation_log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error writing conversation log: {e}")

# Function to start call recording
def start_recording():
    """Start recording the call."""
    global is_recording, recording_frames, conversation_start_time
    
    conversation_start_time = datetime.now()
    is_recording = True
    recording_frames = []
    
    # Log recording start
    log_conversation("SYSTEM", "Call recording started")
    print("📹 Call recording started...")

# Function to stop call recording and save
def stop_recording():
    """Stop recording and save the audio file."""
    global is_recording, recording_frames
    
    if not is_recording:
        return
    
    is_recording = False
    
    if recording_frames:
        # Save recorded audio
        recording_filename = f"call_recording_{conversation_start_time.strftime('%Y%m%d_%H%M%S')}.wav"
        try:
            with wave.open(recording_filename, 'wb') as wf:
                wf.setnchannels(1)  # Mono
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(44100)  # 44.1kHz
                wf.writeframes(b''.join(recording_frames))
            
            log_conversation("SYSTEM", f"Call recording saved as {recording_filename}")
            print(f"📹 Call recording saved as: {recording_filename}")
        except Exception as e:
            print(f"Error saving recording: {e}")
            log_conversation("SYSTEM", f"Error saving recording: {e}")
    
    # Save final conversation log
    log_filename = f"conversation_{conversation_start_time.strftime('%Y%m%d_%H%M%S')}.json"
    print(f"💬 Conversation log saved as: {log_filename}")

# Function to get the first available voice ID
def get_available_voice_id():
    """Get the first available voice ID from the user's account."""
    try:
        voices = elevenlabs_client.voices.search()
        if voices.voices and len(voices.voices) > 0:
            return voices.voices[0].voice_id
        else:
            # Fallback to common default voice IDs
            return "pNInz6obpgDQGcFmaJgB"  # Adam voice (common default)
    except Exception as e:
        print(f"Error getting voices: {e}")
        return "pNInz6obpgDQGcFmaJgB"  # Fallback to default

# Function to Speak Response using ElevenLabs or fallback to system TTS
def speak(text):
    """Convert text to speech using ElevenLabs or system TTS as fallback."""
    global current_audio_lock
    
    # Prevent multiple audio from playing simultaneously
    with current_audio_lock:
        # Log what the assistant is saying
        log_conversation("ASSISTANT", text)
        
        try:
            # Try ElevenLabs first using the correct API
            voice_id = get_available_voice_id()
            audio = elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2"
            )
            
            # Save audio to temporary file and play with pygame
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                # Write audio bytes to temp file
                for chunk in audio:
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Initialize pygame mixer if not already done
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(temp_file_path)
                pygame.mixer.music.play()
                
                # Wait for playback to complete
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)
                    
            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            
        except Exception as e:
            print(f"ElevenLabs TTS failed: {e}")
            try:
                # Fallback to Windows built-in TTS
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", 150)
                engine.say(text)
                engine.runAndWait()
            except Exception as e2:
                print(f"System TTS also failed: {e2}")
                # Final fallback to just printing
                print(f"Assistant: {text}")

# Function to Recognize Speech
def recognize_speech():
    """Capture and convert speech to text."""
    global is_recording, recording_frames
    
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening... Speak now!")
        recognizer.adjust_for_ambient_noise(source)
        
        # Record audio for both speech recognition and call recording
        audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
        
        # If recording is active, save the audio data
        if is_recording:
            recording_frames.append(audio.get_raw_data())
    
    try:
        text = recognizer.recognize_google(audio).lower()
        print(f"You said: {text}")
        
        # Log what the user said
        log_conversation("USER", text)
        
        return text
    except sr.UnknownValueError:
        print("Sorry, I didn't catch that.")
        log_conversation("SYSTEM", "Speech not recognized")
        return None
    except sr.RequestError:
        print("Speech Recognition service is unavailable.")
        log_conversation("SYSTEM", "Speech recognition service unavailable")
        return None
    except sr.WaitTimeoutError:
        print("Listening timeout - no speech detected.")
        log_conversation("SYSTEM", "Listening timeout")
        return None

# Function to ask for confirmation before ending call
def confirm_end_call(language_pref="both"):
    """Ask user to confirm if they want to end the call."""
    if language_pref == "english":
        speak("It sounds like you might want to end our conversation. Would you like to continue discussing your property sale, or would you prefer to end the call now? Please say 'continue' to keep talking or 'end call' to finish.")
    elif language_pref == "hindi":
        speak("लगता है कि आप बातचीत समाप्त करना चाहते हैं। क्या आप अपनी संपत्ति की बिक्री के बारे में और बात करना चाहते हैं, या कॉल समाप्त करना चाहते हैं? कृपया 'जारी रखें' कहें या 'कॉल समाप्त करें' कहें।")
    else:  # both
        speak("It sounds like you might want to end our conversation. Would you like to continue discussing your property sale, or would you prefer to end the call now? क्या आप बातचीत जारी रखना चाहते हैं या कॉल समाप्त करना चाहते हैं? Please say 'continue' or 'end call'.")
    
    # Get user's confirmation
    max_attempts = 3
    for attempt in range(max_attempts):
        response = recognize_speech()
        if not response:
            if attempt < max_attempts - 1:
                if language_pref == "english":
                    speak("I didn't hear you. Please say 'continue' to keep talking or 'end call' to finish.")
                elif language_pref == "hindi":
                    speak("मैंने नहीं सुना। कृपया 'जारी रखें' या 'कॉल समाप्त करें' कहें।")
                else:
                    speak("I didn't hear you. Please say 'continue' or 'end call'. मैंने नहीं सुना, कृपया बताएं।")
                continue
            else:
                # Default to continuing if no clear response
                if language_pref == "english":
                    speak("I'll assume you want to continue. How else can I help you with your property sale?")
                elif language_pref == "hindi":
                    speak("मैं समझूंगा कि आप जारी रखना चाहते हैं। मैं आपकी संपत्ति की बिक्री में और कैसे मदद कर सकता हूं?")
                else:
                    speak("I'll assume you want to continue. How else can I help you? मैं मान लूंगा कि आप जारी रखना चाहते हैं।")
                return False  # Continue conversation
        
        response = response.lower()
        
        # Check for end call confirmation
        end_confirmations = ["end call", "end", "finish", "stop", "quit", "goodbye", "bye", 
                           "कॉल समाप्त करें", "समाप्त", "खत्म", "बंद करें", "अलविदा", "बाय"]
        
        # Check for continue confirmation
        continue_confirmations = ["continue", "keep going", "go on", "yes", "carry on", "more",
                                "जारी रखें", "जारी", "हां", "और", "आगे", "चालू रखें"]
        
        if any(conf in response for conf in end_confirmations):
            if language_pref == "english":
                speak("Thank you for your time! I hope I could help with your home selling queries. Have a great day!")
            elif language_pref == "hindi":
                speak("आपका समय देने के लिए धन्यवाद! मुझे उम्मीद है कि मैं आपकी घर बेचने में मदद कर सका। शुभ दिन!")
            else:
                speak("Thank you for your time! I hope I could help with your home selling queries. धन्यवाद और शुभकामनाएं!")
            return True  # End conversation
        
        elif any(conf in response for conf in continue_confirmations):
            if language_pref == "english":
                speak("Great! I'm happy to continue helping you. What else would you like to know about selling your property to Basant?")
            elif language_pref == "hindi":
                speak("बहुत बढ़िया! मैं आपकी मदद करना जारी रखूंगा। बसंत को संपत्ति बेचने के बारे में आप और क्या जानना चाहते हैं?")
            else:
                speak("Great! I'm happy to continue helping you. What else would you like to know? बहुत बढ़िया! मैं आपकी मदद करना जारी रखूंगा।")
            return False  # Continue conversation
        
        else:
            if attempt < max_attempts - 1:
                if language_pref == "english":
                    speak("I'm not sure I understood. Please clearly say 'continue' if you want to keep talking, or 'end call' if you want to finish.")
                elif language_pref == "hindi":
                    speak("मुझे समझ नहीं आया। कृपया स्पष्ट रूप से 'जारी रखें' या 'कॉल समाप्त करें' कहें।")
                else:
                    speak("I'm not sure I understood. Please clearly say 'continue' or 'end call'. मुझे समझ नहीं आया।")
            else:
                # Default to continuing if unclear
                if language_pref == "english":
                    speak("I'll assume you want to continue our conversation. How can I help you further?")
                elif language_pref == "hindi":
                    speak("मैं समझूंगा कि आप बातचीत जारी रखना चाहते हैं। मैं आपकी और कैसे मदद कर सकता हूं?")
                else:
                    speak("I'll assume you want to continue. How can I help you further? मैं बातचीत जारी रखूंगा।")
                return False  # Continue conversation
    
    return False  # Default to continue

# Function to Handle Query
def process_query(language_pref="both"):
    """Process the user's query and respond."""
    question = recognize_speech()
    if not question:
        if language_pref == "english":
            speak("I didn't hear you. Please try again.")
        elif language_pref == "hindi":
            speak("मैंने आपकी बात नहीं सुनी, कृपया दोबारा कोशिश करें।")
        else:
            speak("I didn't hear you. Please try again. मैंने आपकी बात नहीं सुनी, कृपया दोबारा कोशिश करें।")
        return False  # Continue conversation
    
    # Check for potential end call keywords (but ask for confirmation)
    potential_end_keywords = ["thank you", "thanks", "धन्यवाद", "शुक्रिया", "good", "okay", "ok", 
                             "that's all", "that's it", "बस", "ठीक है", "अच्छा"]
    
    # Check for definitive end commands (immediate end without confirmation)
    definitive_end_commands = ["goodbye", "bye", "exit", "quit", "end call", "hang up", "stop now", 
                              "अलविदा", "बाय", "समाप्त करो", "रुको", "कॉल समाप्त करो"]
    
    # Immediate end for definitive commands
    if any(cmd in question.lower() for cmd in definitive_end_commands):
        if language_pref == "english":
            speak("Thank you for your time! I hope I could help with your home selling queries.")
        elif language_pref == "hindi":
            speak("आपका समय देने के लिए धन्यवाद! मुझे उम्मीद है कि मैं आपकी घर बेचने में मदद कर सका।")
        else:
            speak("Thank you for your time! I hope I could help with your home selling queries. धन्यवाद और शुभकामनाएं!")
        return True  # End conversation
    
    # Ask for confirmation for potential end keywords
    elif any(keyword in question.lower() for keyword in potential_end_keywords):
        # Check if it's just a thank you or if they want to continue
        return confirm_end_call(language_pref)
    
    # Handle real estate related keywords
    real_estate_keywords = ["home", "house", "property", "sell", "selling", "basant", "buyer", "price", "location",
                           "घर", "मकान", "संपत्ति", "बेचना", "बसंत", "खरीदार", "कीमत", "स्थान"]
    
    # Check if question contains real estate keywords
    if any(keyword in question.lower() for keyword in real_estate_keywords):
        # Use Gemini AI for intelligent responses
        gemini_response = get_gemini_response(question, language_pref)
        if gemini_response:
            speak(gemini_response)
            # Follow-up question based on language preference
            if language_pref == "english":
                speak("Is there anything else about the property or sale process you'd like to know?")
            elif language_pref == "hindi":
                speak("क्या संपत्ति या बिक्री प्रक्रिया के बारे में आपका कोई और सवाल है?")
            else:
                speak("Is there anything else about the property or sale process you'd like to know? क्या आपका कोई और सवाल है?")
            return False
        else:
            if language_pref == "english":
                speak("I'm sorry, I'm having trouble processing your question right now. Please try asking again.")
            elif language_pref == "hindi":
                speak("माफ़ करें, मुझे अभी आपके सवाल को समझने में परेशानी हो रही है। कृपया दोबारा पूछें।")
            else:
                speak("I'm sorry, I'm having trouble processing your question right now. Please try asking again.")
            return False
    else:
        # For non-real estate questions, still try to help but redirect gently
        gemini_response = get_gemini_response(question, language_pref)
        if gemini_response:
            speak(gemini_response)
            # Redirect based on language preference
            if language_pref == "english":
                speak("Is there anything about selling your home to Basant that I can help with?")
            elif language_pref == "hindi":
                speak("क्या बसंत को घर बेचने के बारे में कोई सवाल है जिसमें मैं आपकी मदद कर सकूं?")
            else:
                speak("Is there anything about selling your home to Basant that I can help with? क्या घर बेचने के बारे में कोई सवाल है?")
            return False
        else:
            if language_pref == "english":
                speak("I'm here to help with selling your home. Do you have any questions about the property or the sale to Basant?")
            elif language_pref == "hindi":
                speak("मैं आपकी घर बेचने में मदद के लिए यहाँ हूँ। क्या आपके पास संपत्ति या बसंत को बिक्री के बारे में कोई सवाल है?")
            else:
                speak("I'm here to help with selling your home. Do you have any questions about the property or the sale to Basant?")
            return False


def main_conversation_loop():
    """Main conversation loop for continuous interaction."""
    
    # Start call recording and inform user
    start_recording()
    
    # Inform user about recording
    recording_notice = "This call is being recorded for quality and training purposes. आपकी जानकारी के लिए, यह कॉल रिकॉर्ड हो रही है।"
    speak(recording_notice)
    
    # First, get the user's language preference
    language_pref = get_language_preference()
    
    # Welcome message based on language preference
    if language_pref == "english":
        speak("Excellent! I am your real estate assistant and I can help you with selling your home to Basant. How can I assist you today?")
    elif language_pref == "hindi":
        speak("बहुत बढ़िया! मैं आपका रियल एस्टेट सहायक हूँ और मैं बसंत को आपका घर बेचने में आपकी मदद कर सकता हूँ। आज मैं आपकी कैसे सेवा कर सकता हूँ?")
    else:  # both
        speak("Perfect! I am your real estate assistant. I can help you with selling your home to Basant. मैं आपकी घर बेचने में मदद कर सकता हूँ। How can I assist you today?")
    
    conversation_count = 0
    max_conversations = 10  # Prevent infinite loops
    
    try:
        while conversation_count < max_conversations:
            should_exit = process_query(language_pref)
            conversation_count += 1
            
            if should_exit:
                break
            
            # Brief pause between interactions
            time.sleep(1)
        
        if conversation_count >= max_conversations:
            if language_pref == "english":
                speak("I notice we've been talking for a while. Please feel free to contact me again if you have more questions about selling your home. Thank you!")
            elif language_pref == "hindi":
                speak("मैं देख रहा हूँ कि हम काफी देर से बात कर रहे हैं। यदि आपके पास घर बेचने के बारे में और भी सवाल हैं तो कृपया मुझसे दोबारा संपर्क करें। धन्यवाद!")
            else:
                speak("I notice we've been talking for a while. Please feel free to contact me again if you have more questions about selling your home. धन्यवाद!")
    
    finally:
        # Always stop recording when conversation ends
        stop_recording()


if __name__ == "__main__":
    try:
        main_conversation_loop()
    except KeyboardInterrupt:
        print("\nConversation ended by user.")
        log_conversation("SYSTEM", "Conversation ended by user (Ctrl+C)")
        stop_recording()
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please check your API keys and internet connection.")
        log_conversation("SYSTEM", f"Error occurred: {e}")
        stop_recording()
