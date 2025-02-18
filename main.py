import openai
import speech_recognition as sr
import pyttsx3
import os
from fuzzywuzzy import process
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

# Load API Key from Environment Variable
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize Text-to-Speech
engine = pyttsx3.init()
engine.setProperty("rate", 150)


# Wise FAQ Responses (Only "Where is my money?" Section)
# FAQ_RESPONSES = {
#     "where is my money": "Transfers usually take a few minutes, but depending on your bank, it can take 1-2 days.",
#     "why is my transfer delayed": "Delays can happen due to bank processing times, verification, or public holidays.",
#     "can i track my transfer": "Yes, you can check your transfer status in the Wise app or website.",
#     "what happens if my money doesn't arrive": "Check your transfer status in the Wise app. If there's an issue, contact Wise support."
# }

WISE_FAQ_URL = "https://wise.com/help/topics/5bVKT0uQdBrDp6T62keyfz/sending-money"


def scrape_wise_faq():
    """Scrape Wise FAQs dynamically."""
    response = requests.get(WISE_FAQ_URL)
    if response.status_code != 200:
        print("Failed to fetch FAQ page.")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")

    faqs = {}
    for section in soup.find_all("div", class_="sc-1y1nc0z-1 jYkeKm"):  # Adjust if needed
        question = section.find("h2") or section.find("h3")
        answer = section.find("p")

        if question and answer:
            faqs[question.text.strip().lower()] = answer.text.strip()

    return faqs

# Load FAQs dynamically
FAQ_RESPONSES = scrape_wise_faq()

# Function to Speak Response
def speak(text):
    """Convert text to speech."""
    engine.say(text)
    engine.runAndWait()

# Function to Recognize Speech
def recognize_speech():
    """Capture and convert speech to text."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening... Speak now!")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    
    try:
        text = recognizer.recognize_google(audio).lower()
        print(f"You said: {text}")
        return text
    except sr.UnknownValueError:
        print("Sorry, I didn't catch that.")
        return None
    except sr.RequestError:
        print("Speech Recognition service is unavailable.")
        return None

# Function to Handle Query
def process_query():
    """Process the user's query and respond."""
    question = recognize_speech()
    if not question:
        speak("I didn't hear you. Please try again.")
        return
    
    # Check FAQ Responses
    for q, answer in FAQ_RESPONSES.items():
        if q in question:
            speak(answer)
            return
    
    # Deflect to a Human Agent
    speak("I’m transferring you to a human agent now. Goodbye!")
    print("Call ended.")  # Simulating call transfer
# Main Loop to Keep Bot Running
# def run_bot():
#     """Keep the bot running continuously."""
#     speak("Hello! I am your Wise support assistant. Please ask your question.")
    
#     while True:
#         process_query()
        
#         # Add exit condition (e.g., if the user says "exit" or a specific keyword)
#         question = recognize_speech()
#         if question and "exit" in question:
#             speak("Goodbye! Ending the session.")
#             break
# # Run the Voice Agent
if __name__ == "__main__":
    speak("Hello! I am your Wise support assistant. Please ask your question.")
    process_query()
