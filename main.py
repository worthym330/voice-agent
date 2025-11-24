import google.generativeai as genai
import os
from dotenv import load_dotenv
import requests
import io
from datetime import datetime
import json
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from fastapi import FastAPI, Request, Form, Header, HTTPException, Depends
from fastapi.responses import Response, JSONResponse
from typing import Optional, List
from pydantic import BaseModel, Field
import uvicorn
import logging
import sys

# Ensure stdout/stderr use UTF-8 on Windows to avoid UnicodeEncodeError for Devanagari/emojis
try:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")  # type: ignore
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")  # type: ignore
except Exception:
    pass
import traceback

# Load environment variables
load_dotenv()

# Configure logging (UTF-8 safe)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('voice_agent.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

logger.info("="*60)
logger.info("Voice Agent Application Starting")
logger.info("="*60)


def safe_log_twiml(twiml: str):
    """Safely log TwiML content without causing UnicodeEncodeError; truncates long output."""
    try:
        truncated = twiml if len(twiml) <= 2000 else twiml[:2000] + "... [truncated]"
        logger.info("Returning TwiML (len=%d): %s", len(twiml), truncated)
    except Exception as e:
        logger.warning(f"Failed to log TwiML safely: {e}")

# Load API Keys from Environment Variables
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))  # type: ignore[attr-defined]
except Exception:
    logger.warning("Failed to configure Gemini API key; proceeding without explicit configuration.")

# Initialize Gemini model
model = genai.GenerativeModel('gemini-2.0-flash')  # type: ignore

# Initialize Twilio client
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

# Global variables for recording and conversation logging
conversation_log = []
API_KEY = os.getenv("API_KEY")  # Optional API key for securing endpoints
CALL_LOG_FILES: dict[str, str] = {}
RECORDING_DOWNLOADS: dict[str, str] = {}
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TARGET_PHONE_NUMBER = os.getenv("TARGET_PHONE_NUMBER")
PUBLIC_URL = os.getenv("PUBLIC_URL", os.getenv("CALLBACK_URL", "http://localhost:8000"))
CALLBACK_URL = f"{PUBLIC_URL}/api/callback/twilio/voice"
COMPANY_NAME = os.getenv("COMPANY_NAME", "XYZ")
PROJECT_NAME = os.getenv("PROJECT_NAME", "XYZ Apartments")
PROJECT_LOCATION = os.getenv("PROJECT_LOCATION", "")
STARTING_PRICE = os.getenv("STARTING_PRICE", "₹55 lakhs")
UNIT_TYPES = os.getenv("UNIT_TYPES", "1BHK–3BHK")

# Track per-call state like captured name, stage
CALL_STATE: dict[str, dict] = {}

def create_call_log(call_sid: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    os.makedirs("call_logs", exist_ok=True)
    path = os.path.join("call_logs", f"call_{ts}_{call_sid}.log")
    CALL_LOG_FILES[call_sid] = path
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"CALL START {ts} SID={call_sid}\n")
    return path

def append_call_log(call_sid: str | None, message: str):
    if not call_sid:
        return
    path = CALL_LOG_FILES.get(call_sid) or create_call_log(call_sid)
    ts = datetime.utcnow().isoformat()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception as e:
        logger.warning(f"Failed to write call log for {call_sid}: {e}")

def finalize_call(call_sid: str):
    append_call_log(call_sid, "CALL END")
tags_metadata = [
    {
        "name": "twilio",
        "description": "Inbound voice, status and recording webhooks from Twilio. These are called by Twilio servers (not user initiated)."
    },
    {
        "name": "calls",
        "description": "Programmatic outbound call initiation endpoints secured by API key."
    },
    {
        "name": "conversation",
        "description": "Access logs generated during assistant interactions (local or phone)."
    },
    {
        "name": "system",
        "description": "Health and configuration introspection endpoints."
    }
]

app = FastAPI(
    title="Real Estate Voice Agent API",
    description="AI powered bilingual (English/Hindi) real estate voice assistant integrating Twilio + Gemini.",
    version="1.0.0",
    contact={
        "name": "Voice Agent Support",
        "email": "support@example.com"
    },
    license_info={
        "name": "Proprietary",
        "url": "https://example.com/license"
    },
)

# ============================
# Pydantic Schemas (restored)
# ============================
class OutboundCallRequest(BaseModel):
    to_number: Optional[str] = Field(None, description="Destination E.164 number; falls back to TARGET_PHONE_NUMBER.")
    language_pref: str = Field("both", description="Greeting language: english | hindi | both")

class OutboundCallResponse(BaseModel):
    call_sid: str
    status: str
    to: str

class ConversationEntry(BaseModel):
    timestamp: str
    speaker: str
    text: str

class ConversationLogResponse(BaseModel):
    count: int
    log: List[ConversationEntry]

class ConfigResponse(BaseModel):
    twilio_number: Optional[str]
    target_number: Optional[str]
    has_api_key: bool

class HealthResponse(BaseModel):
    status: str
    timestamp: str

def get_gemini_response(question: str, _language_pref: str = "both") -> Optional[str]:
    """AI response generator with detailed real estate agent persona."""
    logger.info(f"Gemini generating for: {question}")
    try:
        system_prompt = f"""You are a friendly, trustworthy real-estate sales agent for {COMPANY_NAME} selling apartments at {PROJECT_NAME}{(' in ' + PROJECT_LOCATION) if PROJECT_LOCATION else ''}.
            Inventory: {UNIT_TYPES}. Pricing starts from {STARTING_PRICE} (all-inclusive ranges only if asked).

            Primary goals:
            1) On the first turn: politely ASK the caller's name before sharing project details.
            2) After the name, personalize responses and QUALIFY the lead (unit type, budget, location/commute, timeline/possession, financing/loan, contact details).
            3) Progress toward scheduling a SITE VISIT or VIRTUAL TOUR.

            Behavior and style:
            - Mirror the caller's language (English/Hindi). If mixed, you may mix politely. Use simple, clear sentences.
            - Keep answers concise: max 2–3 short sentences, then end with ONE relevant question.
            - Be warm, professional, and consultative. Never pressure or make guarantees.
            - If asked out-of-scope, briefly answer if possible then steer back to the property.
            - Be transparent: if you don't know exact figures, give best range + offer brochure/price sheet.
            - Don't invent facts. Mention typical USPs only if true (quality construction, strong connectivity, amenities, RERA status, loan assistance).

            Project talking points (adapt/limit to truth):
            - Starting price: {STARTING_PRICE}; configurations: {UNIT_TYPES}.
            - Highlights: good connectivity, essential amenities, quality construction, loan assistance (if applicable).
            - Next steps: share brochure/price sheet, answer queries, propose site visit slots.

            Lead-qualification focus (ask ONE at a time, based on context):
            - Unit preference (1/2/3BHK) and usable budget.
            - Preferred location/commute needs.
            - Move-in timeline/possession expectations.
            - Financing/loan support needed.
            - Best contact and site-visit availability.

            Edge cases:
            - If user is busy: offer to send brochure (WhatsApp/email) and propose a callback time.
            - If user wants to end: thank them and close politely.

            User said: {question}

            Respond naturally following the guidelines above."""
        
        resp = model.generate_content(system_prompt)  # type: ignore
        return resp.text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return None

def log_conversation(speaker: str, text: str):
    conversation_log.append({"timestamp": datetime.utcnow().isoformat(), "speaker": speaker, "text": text})


def initiate_twilio_call(to_number=None, language_pref="both"):
    """Initiate a phone call using Twilio."""
    logger.info(f"Initiating Twilio call to {to_number} with language pref: {language_pref}")
    try:
        phone_number = to_number or TARGET_PHONE_NUMBER
        logger.debug(f"Resolved phone number: {phone_number}")
        
        if not phone_number:
            logger.error("No target phone number configured")
            print("❌ Error: No target phone number configured.")
            print("Please set TARGET_PHONE_NUMBER in your .env file")
            return None
        
        if not TWILIO_PHONE_NUMBER:
            logger.error("No Twilio phone number configured")
            print("❌ Error: No Twilio phone number configured.")
            print("Please set TWILIO_PHONE_NUMBER in your .env file")
            return None
        
        logger.info(f"📞 Initiating call to {phone_number}...")
        logger.info(f"🌐 Using callback URL: {CALLBACK_URL}")
        
        # Create TwiML for the call
        twiml = VoiceResponse()
        logger.debug("Created initial TwiML response object.")
        
        # Initial greeting: ask for name first (no project details yet)
        if language_pref == "english":
            greeting = f"Hello! This is your real estate advisor from {COMPANY_NAME}. Before we begin, may I know your name?"
            voice = 'Polly.Joanna'; lang = 'en-US'
        elif language_pref == "hindi":
            greeting = f"नमस्ते! मैं {COMPANY_NAME} से आपका रियल एस्टेट सलाहकार हूँ। शुरू करने से पहले, आपका नाम जान सकता/सकती हूँ?"
            voice = 'Polly.Aditi'; lang = 'hi-IN'
        else:
            greeting = f"Hello! नमस्ते! I’m your real‑estate advisor from {COMPANY_NAME}. Before we begin, may I know your name?"
            voice = 'Polly.Aditi'; lang = 'hi-IN'
        
        twiml.say(greeting, voice=voice, language=lang)
        logger.debug(f"Added greeting to TwiML: {greeting}")
        
        # Gather input from the user with enhanced settings
        gather = Gather(
            input='speech',
            action=CALLBACK_URL,
            method='POST',
            language='en-US hi-IN',  # Support both English and Hindi
            speechTimeout='auto',
            timeout=5,
            profanityFilter=False,
            hints='my name is, I am, this is, नाम, मेरा नाम'
        )
        # After the greeting above, Gather will capture the name
        twiml.append(gather)
        logger.debug("Added Gather block to TwiML for user input.")
        
        # If no input, redirect
        twiml.say("I didn't hear you. Please tell me your name. मैंने नहीं सुना—कृपया अपना नाम बताइए।", voice='Polly.Aditi', language='hi-IN')
        twiml.redirect(CALLBACK_URL)
        
        # Make the call
        status_callback_url = f"{PUBLIC_URL}/api/callback/twilio/status"
        recording_callback_url = f"{PUBLIC_URL}/api/callback/twilio/recording"
        
        logger.info(f"Creating Twilio call: to={phone_number}, from={TWILIO_PHONE_NUMBER}")
        logger.info(f"Voice callback: {CALLBACK_URL}")
        logger.info(f"Status callback: {status_callback_url}")
        logger.info(f"Recording callback: {recording_callback_url}")
        
        call = twilio_client.calls.create(
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,
            twiml=str(twiml),
            record=True,  # Record the call
            recording_status_callback=recording_callback_url,
            status_callback=status_callback_url,
            status_callback_event=['initiated', 'ringing', 'answered', 'completed']
        )
        
        logger.info(f"Call initiated successfully! SID: {call.sid}, Status: {call.status}")
        print(f"✅ Call initiated successfully!")
        print(f"📞 Call SID: {call.sid}")
        print(f"📱 Calling: {phone_number}")
        print(f"📞 From: {TWILIO_PHONE_NUMBER}")
        print(f"⏳ Status: {call.status}")
        
        # Log the call initiation
        log_conversation("SYSTEM", f"Twilio call initiated to {phone_number}. Call SID: {call.sid}")
        # Per-call log file
        create_call_log(str(call.sid))
        append_call_log(str(call.sid), f"OUTBOUND to={phone_number} from={TWILIO_PHONE_NUMBER} status={call.status}")
        logger.debug("Call initiation logged in conversation log.")
        
        return call
        
    except Exception as e:
        logger.error(f"Error initiating Twilio call: {e}")
        logger.error(traceback.format_exc())
        print(f"❌ Error initiating Twilio call: {e}")
        log_conversation("SYSTEM", f"Error initiating Twilio call: {e}")
        logger.debug("Error logged in conversation log.")
        return None

# ============================
# FastAPI Helper & Middleware
# ============================
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    return True

# ============================
# FastAPI Endpoints
# ============================
@app.post("/api/callback/twilio/voice", summary="Primary Twilio Voice Webhook", tags=["twilio"])
async def twilio_voice_webhook(
    request: Request,
    SpeechResult: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    CallSid: Optional[str] = Form(None),
    Confidence: Optional[str] = Form(None)
):
    """Handle initial Twilio voice interaction or subsequent Gather speech results."""
    # Log all form data for debugging
    form_data = await request.form()
    logger.info(f"=" * 80)
    logger.info(f"WEBHOOK RECEIVED - CallSid: {CallSid}")
    logger.info(f"From: {From}, To: {To}")
    logger.info(f"SpeechResult: {SpeechResult}")
    logger.info(f"Confidence: {Confidence}")
    logger.info(f"All form data: {dict(form_data)}")
    logger.info(f"=" * 80)
    
    try:
        vr = VoiceResponse()

        # Ensure call state exists
        if CallSid and CallSid not in CALL_STATE:
            CALL_STATE[CallSid] = {"name": None, "stage": "intro"}

        if SpeechResult:
            # Log user speech
            logger.info(f"Processing speech result: {SpeechResult}")
            log_conversation("USER", SpeechResult)
            append_call_log(CallSid, f"USER {SpeechResult}")
            # Try to capture name if not set yet
            if CallSid and CALL_STATE.get(CallSid, {}).get("name") in (None, ""):
                name_text = SpeechResult.strip()
                # Heuristic: take first 2 words max as name
                parts = name_text.split()
                caller_name = " ".join(parts[:2]) if parts else ""
                CALL_STATE[CallSid]["name"] = caller_name or name_text
                CALL_STATE[CallSid]["stage"] = "qualified_intro"
                append_call_log(CallSid, f"NAME_CAPTURED {CALL_STATE[CallSid]['name']}")

                # Personalized intro and next qualifying question
                intro = (
                    f"Nice to meet you, {CALL_STATE[CallSid]['name']}. "
                    f"We have {UNIT_TYPES} homes with prices starting around {STARTING_PRICE}. "
                    f"Do you prefer 1BHK, 2BHK or 3BHK—or a budget range?"
                )
                gather = Gather(
                    input='speech',
                    speechTimeout='auto',
                    action=CALLBACK_URL,
                    method='POST',
                    language='en-US hi-IN',
                    timeout=5,
                    profanityFilter=False,
                    hints='1BHK,2BHK,3BHK,budget,price,कीमत,बजट'
                )
                gather.say(intro, voice='Polly.Aditi', language='hi-IN')
                vr.append(gather)
                vr.say("If I didn’t hear you, please share your preferred configuration or budget.", voice='Polly.Joanna', language='en-US')
                vr.redirect(CALLBACK_URL)
                twiml_response = str(vr)
                safe_log_twiml(twiml_response)
                return Response(content=twiml_response, media_type="application/xml")
            
            # Check for end conversation keywords
            end_keywords = ["goodbye", "bye", "end call", "hang up", "thank you bye", "that's all", "stop"]
            if any(keyword in SpeechResult.lower() for keyword in end_keywords):
                logger.info("User requested to end call")
                farewell = "Thank you for calling! Have a great day! धन्यवाद और शुभ दिन!"
                log_conversation("ASSISTANT", farewell)
                append_call_log(CallSid, f"ASSISTANT {farewell}")
                vr.say(farewell, voice='Polly.Aditi', language='hi-IN')
                vr.hangup()
            else:
                # Generate AI response with project framing
                ai_resp = get_gemini_response(
                    f"Project: {PROJECT_NAME} by {COMPANY_NAME} {('in ' + PROJECT_LOCATION) if PROJECT_LOCATION else ''}. "
                    f"Inventory: {UNIT_TYPES}. Starting price: {STARTING_PRICE}.\n"
                    f"User said: {SpeechResult}\n"
                    f"Respond briefly (2-3 short sentences) and end with one relevant question."
                ) or "I'm having trouble. Please ask again."
                log_conversation("ASSISTANT", ai_resp)
                append_call_log(CallSid, f"ASSISTANT {ai_resp}")
                logger.info(f"Sending AI response: {ai_resp[:100]}...")
                
                # Continue conversation with another gather
                gather = Gather(
                    input='speech', 
                    speechTimeout='auto', 
                    action=CALLBACK_URL, 
                    method='POST',
                    language='en-US hi-IN',  # Support both languages
                    timeout=5,
                    profanityFilter=False,
                    hints='sell, property, home, Basant, price, location, घर, संपत्ति, बेचना, बसंत, कीमत'
                )
                gather.say(ai_resp, voice='Polly.Aditi', language='hi-IN')
                vr.append(gather)
                
                # If user doesn't respond, prompt them
                vr.say("Are you still there? क्या आप अभी भी हैं?", voice='Polly.Aditi', language='hi-IN')
                vr.redirect(CALLBACK_URL)
        else:
            # First-time or no speech: ask for name (keep consistent with initiation)
            logger.info("No speech yet – asking for caller name")
            greet = (
                f"Hello! नमस्ते! I’m your real‑estate advisor from {COMPANY_NAME}. "
                f"Before we begin, may I know your name?"
            )
            log_conversation("ASSISTANT", greet)
            append_call_log(CallSid, f"ASSISTANT {greet}")

            gather = Gather(
                input='speech',
                speechTimeout='auto',
                action=CALLBACK_URL,
                method='POST',
                language='en-US hi-IN',
                timeout=5,
                profanityFilter=False,
                hints='my name is, I am, this is, नाम, मेरा नाम'
            )
            gather.say(greet, voice='Polly.Aditi', language='hi-IN')
            vr.append(gather)

            vr.say("If I didn’t hear you, please tell me your name.", voice='Polly.Joanna', language='en-US')
            vr.redirect(CALLBACK_URL)

        twiml_response = str(vr)
        safe_log_twiml(twiml_response)
        return Response(content=twiml_response, media_type="application/xml")
    except Exception as e:
        logger.error(f"Error in voice webhook: {e}")
        logger.error(traceback.format_exc())
        # Return error TwiML
        error_vr = VoiceResponse()
        error_vr.say("I'm sorry, an error occurred. Please try again later.", voice='Polly.Aditi', language='hi-IN')
        return Response(content=str(error_vr), media_type="application/xml")

@app.post("/api/callback/twilio/status", summary="Twilio Call Status Callback", tags=["twilio"])
async def twilio_status_callback(
    CallSid: Optional[str] = Form(None),
    CallStatus: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None)
):
    logger.info(f"Status callback: SID={CallSid} Status={CallStatus} From={From} To={To}")
    log_conversation("SYSTEM", f"Status update: SID={CallSid} Status={CallStatus} From={From} To={To}")
    append_call_log(CallSid, f"STATUS {CallStatus}")
    if CallStatus == "completed" and CallSid:
        finalize_call(CallSid)
    return JSONResponse({"ok": True})

@app.post(
    "/api/call/outbound",
    summary="Initiate outbound Twilio call",
    tags=["calls"],
    response_model=OutboundCallResponse,
    dependencies=[Depends(verify_api_key)],
    responses={
        200: {"description": "Call initiated successfully"},
        400: {"description": "Missing to_number and no default configured"},
        401: {"description": "Unauthorized - invalid API key"},
        500: {"description": "Twilio initiation failed"}
    }
)
async def api_outbound_call(request: OutboundCallRequest):
    """Initiate an outbound phone call using Twilio.

    Provide an optional `to_number` in the request body. If omitted, the number in `TARGET_PHONE_NUMBER` env var is used.
    Language preference affects the initial greeting only.
    """
    to_number = request.to_number or TARGET_PHONE_NUMBER
    if not to_number:
        raise HTTPException(status_code=400, detail="to_number missing and TARGET_PHONE_NUMBER not configured")
    call = initiate_twilio_call(to_number, request.language_pref)
    if not call:
        raise HTTPException(status_code=500, detail="Failed to initiate call")
    return OutboundCallResponse(call_sid=call.sid, status=call.status, to=to_number)

@app.get(
    "/api/conversation/current",
    summary="Get current conversation log",
    tags=["conversation"],
    response_model=ConversationLogResponse,
    dependencies=[Depends(verify_api_key)]
)
async def get_current_conversation():
    """Return the in-memory conversation log captured during current runtime.

    Entries are also written to a timestamped JSON file as they are appended.
    """
    return ConversationLogResponse(count=len(conversation_log), log=conversation_log)  # type: ignore[arg-type]

@app.get(
    "/api/health",
    summary="Health check",
    tags=["system"],
    response_model=HealthResponse
) 
async def health():
    """Basic application liveness probe."""
    return HealthResponse(status="ok", timestamp=datetime.utcnow().isoformat()) 

@app.get(
    "/api/config",
    summary="Basic config info",
    tags=["system"],
    response_model=ConfigResponse,
    dependencies=[Depends(verify_api_key)]
)
async def config():
    """Return limited configuration details (does not expose secrets)."""
    return ConfigResponse(twilio_number=TWILIO_PHONE_NUMBER, target_number=TARGET_PHONE_NUMBER, has_api_key=bool(API_KEY))
@app.get(
    "/api/docs/openapi.json",
    summary="Download OpenAPI specification JSON",
    tags=["system"],
    response_model=dict
)
async def download_openapi():
    """Return the generated OpenAPI schema allowing external tooling (e.g. Swagger UI, Postman import)."""
    return app.openapi()

@app.post("/api/callback/twilio/recording", summary="Recording status callback", tags=["twilio"]) 
async def recording_status_callback(CallSid: Optional[str] = Form(None), RecordingUrl: Optional[str] = Form(None), RecordingStatus: Optional[str] = Form(None)):
    logger.info(f"Recording callback: SID={CallSid} Status={RecordingStatus} Url={RecordingUrl}")
    log_conversation("SYSTEM", f"Recording callback: SID={CallSid} Status={RecordingStatus} Url={RecordingUrl}")
    append_call_log(CallSid, f"RECORDING status={RecordingStatus} url={RecordingUrl}")
    if RecordingStatus == "completed" and RecordingUrl and CallSid:
        try:
            audio_url = RecordingUrl + ".mp3" if not RecordingUrl.endswith(".mp3") else RecordingUrl
            account_sid = os.getenv("TWILIO_ACCOUNT_SID") or ""
            auth_token = os.getenv("TWILIO_AUTH_TOKEN") or ""
            r = requests.get(audio_url, auth=(account_sid, auth_token), timeout=30)
            if r.status_code == 200:
                os.makedirs("recordings", exist_ok=True)
                fname = os.path.join("recordings", f"recording_{CallSid}.mp3")
                with open(fname, "wb") as f:
                    f.write(r.content)
                RECORDING_DOWNLOADS[CallSid] = fname
                append_call_log(CallSid, f"RECORDING_DOWNLOADED {fname}")
                logger.info(f"Recording saved as {fname}")
            else:
                append_call_log(CallSid, f"RECORDING_DOWNLOAD_FAILED status={r.status_code}")
                logger.warning(f"Failed to download recording {RecordingUrl}: {r.status_code}")
        except Exception as e:
            append_call_log(CallSid, f"RECORDING_DOWNLOAD_ERROR {e}")
            logger.warning(f"Recording download error: {e}")
    return {"ok": True}


if __name__ == "__main__":
    print("Starting FastAPI server on port 9004... (docs at /docs)")
    uvicorn.run("main:app", host="0.0.0.0", port=9004, reload=False)