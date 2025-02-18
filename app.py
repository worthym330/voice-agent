from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import openai
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# Set up OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")
account_sid = os.getenv("account_sid")
auth_token = os.getenv("auth_token")

client = Client(account_sid, auth_token)

def get_openai_response(query):
    """Get response from OpenAI based on the user's query."""
    try:
        response = openai.Completion.create(
            engine="gpt-4",  # You can choose a different model if needed
            prompt=query,
            max_tokens=150
        )
        return response.choices[0].text.strip()
    except Exception as e:
        print(f"Error with OpenAI API: {e}")
        return "Sorry, I couldn't get an answer from the service."

@app.route('/voice', methods=['GET', 'POST'])
def voice_response():
    """Handle incoming calls."""
    response = VoiceResponse()

    # Get the speech input from the user
    response.say("Hello! I am your customer support assistant. How can I help you today? Please ask your question.")
    
    # Record the user's speech and send it to the 'process_query' endpoint
    response.record(maxLength=10, action="/process_query", method="POST", transcribe=True)
    
    return str(response)

@app.route('/process_query', methods=['POST'])
def process_query():
    """Process the recorded query and provide the response."""
    recording_url = request.form.get('RecordingUrl')
    transcribed_text = request.form.get('TranscriptionText')
    
    print(f"User said: {transcribed_text}")
    
    # Check if the query is related to the FAQ section (Where is my money)
    faq_keywords = ["where is my money", "tracking my money", "money transfer status", "delayed transfer", "money not received"]
    if any(keyword in transcribed_text.lower() for keyword in faq_keywords):
        # Get response from OpenAI for the recognized query
        response_text = get_openai_response(f"Answer this FAQ about 'Where is my money': {transcribed_text}")
        response = VoiceResponse()
        response.say(response_text)
        return str(response)
    else:
        # If the question is not recognized, redirect to a human or end the call
        response = VoiceResponse()
        response.say("I'm sorry, I cannot assist with that. I am now ending the call.")
        response.hangup()
        return str(response)

if __name__ == "__main__":
    app.run(debug=True)
