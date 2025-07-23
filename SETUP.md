# Real Estate Voice Assistant Setup Instructions

## Purpose
This voice assistant helps with selling a home to Basant, supporting both English and Hindi communication.

## Prerequisites
- Python 3.7 or higher
- Microphone access
- Internet connection
- ElevenLabs API account
- Google Gemini API account

## Installation Steps

1. **Install Python Dependencies**
   ```bash
   pip install -r requirement.txt
   ```

2. **Set up Environment Variables**
   - Copy `.env.example` to `.env`
   - Get your ElevenLabs API key from: https://elevenlabs.io/
   - Get your Gemini API key from: https://makersuite.google.com/app/apikey
   - Fill in your API keys in the `.env` file

3. **Customize Property Information**
   - Edit the `PROPERTY_INFO` section in `main.py` with your actual property details
   - Add specific information about location, price, and features

4. **Test Microphone Access**
   - Ensure your microphone is working and accessible to Python
   - On Windows, you may need to allow microphone permissions

## Running the Voice Assistant

```bash
python main.py
```

## Features

### Bilingual Communication
- **English Support**: Full conversation in English
- **Hindi Support**: Native Hindi responses using Devanagari script
- **Mixed Language**: Can handle code-switching between English and Hindi

### Voice Technology
- **Speech Recognition**: Uses Google Speech Recognition for both languages
- **Text-to-Speech**: Uses ElevenLabs for natural voice synthesis
- **AI-Powered Responses**: Uses Google Gemini for intelligent conversation

### Real Estate Focus
- **Property Information**: Answers questions about the home being sold
- **Buyer Connection**: Enthusiastic responses about Basant as the buyer
- **Sales Process**: Guidance on selling procedures and next steps
- **Pricing Discussions**: Flexible conversations about property value

### Voice Commands
Ask questions like:
- "Tell me about the property" / "संपत्ति के बारे में बताएं"
- "What's the price?" / "कीमत क्या है?"
- "When can Basant see the house?" / "बसंत कब घर देख सकते हैं?"
- "What are the property features?" / "घर की विशेषताएं क्या हैं?"

Exit commands:
- "goodbye", "bye", "धन्यवाद", "अलविदा"

## Customization

### Voice Options
Change the voice in the `speak()` function:
- "Bella" (default) - good for English
- "Adam" - male voice option
- Other ElevenLabs voices available

### Property Information
Update the `PROPERTY_INFO` dictionary with:
- Actual property location
- Real asking price
- Key selling features
- Any special notes about Basant

### Language Preferences
The assistant automatically detects language preference and responds accordingly.

## Troubleshooting

### Common Issues
1. **Import Errors**: Run `pip install -r requirement.txt`
2. **Microphone Issues**: Check system permissions
3. **API Errors**: Verify your Gemini and ElevenLabs API keys
4. **Hindi Display**: Ensure your terminal supports Unicode/Devanagari

### Language Support
- The assistant can understand both English and Hindi input
- Responses adapt to the user's language preference
- Mixed language conversations are supported

## API Usage Notes
- ElevenLabs: Usage depends on your subscription plan
- Google Gemini: Has rate limits and quotas
- Google Speech Recognition: Free with usage limits
