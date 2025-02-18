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


def scrape_faq_answers(section_name):
    """Scrape FAQ questions & answers using BeautifulSoup."""
    
    # Fetch the main FAQ page
    response = requests.get(WISE_FAQ_URL, headers={"User-Agent": "Mozilla/5.0"})
    
    if response.status_code != 200:
        print("Failed to fetch the FAQ page.")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the section header that contains the given FAQ category
    section = soup.find("h2", string=section_name)
    if not section:
        print(f"Section '{section_name}' not found!")
        return {}

    # Find the parent div that contains the question list
    section_div = soup.find('div', {'data-testid': 'accordion-content-3QX93lakVA1h92VKze5gHp'})


    # Find all links inside the dropdown (FAQ links)
    faq_links = section_div.find_all("a", href=True)

    faq_data = {}

    for link in faq_links:
        # Extract question text and URL
        question_text = link.get_text(strip=True)
        question_url = f"https://wise.com{link['href']}"
        
        # Fetch the question's detailed answer page
        question_response = requests.get(question_url, headers={"User-Agent": "Mozilla/5.0"})
        
        if question_response.status_code != 200:
            faq_data[question_text] = "Error fetching answer."
            continue

        question_soup = BeautifulSoup(question_response.text, "html.parser")
        
        # Extract the answer from the content div with class "rich-article-content"
        answer_div = question_soup.find("div", class_ ="article-content")
        
        if answer_div:
            # Get only the text content, stripping out all HTML
            faq_data[question_text] = answer_div.get_text(separator=" ", strip=True)
        else:
            faq_data[question_text] = "No answer found."

    return faq_data

# Scrape the "Where is my money?" FAQ section
FAQ_RESPONSES = scrape_faq_answers("Where is my money?")


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
    
    # Use fuzzy matching to find the best match
    best_match, score = process.extractOne(question, FAQ_RESPONSES.keys())

    
    # If the score is above a certain threshold (e.g., 60), respond with the answer
    if score >= 90:
        answer = FAQ_RESPONSES[best_match]
        speak(answer)
    else:
        # Deflect to a Human Agent
        speak("I’m transferring you to a human agent now. Goodbye!")
        print("Call ended.")  # Simulating call transfer


if __name__ == "__main__":
    speak("Hello! I am your Wise support assistant. Please ask your question.")
    process_query()
