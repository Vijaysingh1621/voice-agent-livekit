import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv(".env")

# Required env vars
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")  # E.164 format, e.g. +15551234567
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")  # e.g. https://<your-ngrok-subdomain>.ngrok.io or your domain

# LiveKit SIP URI (configure this in your LiveKit SIP settings)
# Example formats (consult LiveKit SIP docs to pick the right one for your setup):
#   sip:agent@your-domain.sip.livekit.cloud
#   sip:agent@your-domain.sip.livekit.cloud;transport=tls
#   sip:entry@your-domain.sip.livekit.cloud?lk_r=room-name&lk_t=token
LIVEKIT_SIP_URI = os.getenv("LIVEKIT_SIP_URI")

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, PUBLIC_BASE_URL, LIVEKIT_SIP_URI]):
    missing = [
        name for name, val in [
            ("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT_SID),
            ("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN),
            ("TWILIO_FROM_NUMBER", TWILIO_FROM_NUMBER),
            ("PUBLIC_BASE_URL", PUBLIC_BASE_URL),
            ("LIVEKIT_SIP_URI", LIVEKIT_SIP_URI),
        ] if not val
    ]
    # We don't raise here to allow /health to work, but /call will fail with clear error.

app = FastAPI(title="Twilio Caller for LiveKit SIP Agent")

twilio_client: Optional[Client] = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


class CallRequest(BaseModel):
    to: str  # E.164 destination number, e.g. +15557654321
    room: Optional[str] = None  # Optional LiveKit room, appended to TwiML as query if desired


@app.get("/")
@app.post("/")
async def root_webhook(request: Request):
    """
    Root webhook handler - forwards to /twiml for Twilio compatibility.
    This allows you to use just the base URL in Twilio webhook config.
    """
    return await serve_twiml(request)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "twilio_ready": bool(twilio_client),
        "from_number": TWILIO_FROM_NUMBER,
        "public_base_url": bool(PUBLIC_BASE_URL),
        "sip_uri_configured": bool(LIVEKIT_SIP_URI),
    }


@app.post("/call")
async def start_call(payload: CallRequest):
    if not twilio_client or not all([TWILIO_FROM_NUMBER, PUBLIC_BASE_URL, LIVEKIT_SIP_URI]):
        raise HTTPException(status_code=500, detail="Server not fully configured. Check env vars and /health.")

    # TwiML endpoint that instructs Twilio to dial the SIP to LiveKit
    twiml_url = f"{PUBLIC_BASE_URL.rstrip('/')}/twiml"
    # Use demo-room as default if no room specified
    room = payload.room or "demo-room"
    twiml_url = f"{twiml_url}?room={room}"

    try:
        call = twilio_client.calls.create(
            to=payload.to,
            from_=TWILIO_FROM_NUMBER,
            url=twiml_url,
            machine_detection="Enable",  # optional: detect voicemail
        )
        return {"status": "initiated", "call_sid": call.sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Twilio call initiation failed: {e}")


@app.api_route("/twiml", methods=["GET", "POST"], response_class=PlainTextResponse)
async def serve_twiml(request: Request):
    """
    TwiML endpoint for both INBOUND and OUTBOUND calls.
    - Inbound: When someone calls your Twilio number, Twilio hits this webhook
    - Outbound: When you trigger /call API, Twilio fetches this for instructions
    
    Both scenarios connect the caller to your LiveKit voice agent via SIP.
    """
    params = dict(request.query_params)
    
    # Get room name from query param (outbound) or generate unique room (inbound)
    room = params.get("room")
    
    # For inbound calls, try to parse form data to get caller number
    if not room and request.method == "POST":
        try:
            form_data = await request.form()
            caller = form_data.get("From", "").replace("+", "").replace(" ", "")  # Remove + and spaces
            if caller:
                room = f"inbound-{caller}"
        except Exception:
            # If form parsing fails, just use default room
            pass
    
    # Default fallback room
    if not room:
        room = "agent-room"

    if not LIVEKIT_SIP_URI:
        raise HTTPException(status_code=500, detail="LIVEKIT_SIP_URI not configured.")

    # Use base SIP URI without room encoding - let LiveKit dispatch rule handle routing
    # For "Individual" dispatch: LiveKit creates unique rooms automatically
    # For "Direct" dispatch: Configure roomName in LiveKit dispatch rule
    sip_uri = LIVEKIT_SIP_URI

    # Return TwiML that connects the call to your LiveKit SIP ingress
    twiml = f"""
<Response>
  <Dial>
    <Sip>{sip_uri}</Sip>
  </Dial>
</Response>
""".strip()

    return PlainTextResponse(content=twiml, media_type="application/xml")


# Run with: uvicorn twilio_app:app --host 0.0.0.0 --port 8001
