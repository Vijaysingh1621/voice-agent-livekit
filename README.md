# Truliv Voice Agent – Twilio + LiveKit SIP

This repo runs a LiveKit Voice AI agent and provides a small FastAPI service to trigger outbound Twilio calls that connect callers to your LiveKit SIP ingress, so the agent can talk to them.

## What this does
- Starts your LiveKit Agent (see `agent.py`).
- Exposes a minimal API to:
  - `POST /call` – initiate an outbound phone call via Twilio
  - `/twiml` – serve TwiML that connects the call to your LiveKit SIP URI

## Prerequisites
- Python 3.10+
- Twilio account with a verified caller ID or purchased number
- LiveKit project with SIP enabled and a SIP URI you can dial to reach your room/agent
- A public URL (ngrok or a domain) for Twilio to reach your `/twiml`

## Install
```bash
python -m venv venv
venv\\Scripts\\activate  # Windows PowerShell
pip install -r requirements.txt
```

## Configure
Create or update `.env` with:

```
# Twilio
TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+15551234567

# Public URL for the TwiML webhook (use ngrok or your domain)
PUBLIC_BASE_URL=https://<your-ngrok-subdomain>.ngrok.io

# LiveKit SIP target (consult LiveKit SIP docs)
# Examples:
# LIVEKIT_SIP_URI=sip:agent@your-domain.sip.livekit.cloud
# LIVEKIT_SIP_URI=sip:entry@your-domain.sip.livekit.cloud?lk_r=my-room&lk_t=token
LIVEKIT_SIP_URI=sip:agent@your-domain.sip.livekit.cloud

# (Agent credentials/configuration for LiveKit should already be handled by agent.py)
```

## Run
Open two terminals.

Terminal 1 – start the LiveKit Agent:
```bash
venv\\Scripts\\activate
python agent.py
```

Terminal 2 – start the Twilio API server:
```bash
venv\\Scripts\\activate
uvicorn twilio_app:app --host 0.0.0.0 --port 8001
```

Expose the API publicly for Twilio (example using ngrok):
```bash
ngrok http 8001
```
Update `PUBLIC_BASE_URL` in `.env` with the https URL printed by ngrok.

## Trigger a call
With the server running and `PUBLIC_BASE_URL` set, initiate a call:
```bash
curl -X POST "http://localhost:8001/call" \
  -H "Content-Type: application/json" \
  -d '{"to":"+15557654321", "room":"demo-room"}'
```
- Twilio calls `to` from `TWILIO_FROM_NUMBER`.
- Twilio fetches `/twiml` from your public URL.
- TwiML tells Twilio to dial `LIVEKIT_SIP_URI` (with optional `lk_r` query param for room), bridging the caller into LiveKit where your agent is active.

## Notes
- The exact `LIVEKIT_SIP_URI` format depends on your LiveKit SIP configuration (domain, user, optional query tokens/room). Check LiveKit SIP docs and adjust.
- If you prefer Twilio Media Streams instead of SIP, you would need a WebSocket bridge that forwards audio to your agent — this demo uses SIP because it’s simpler to wire up.
- Use `/health` to verify configuration quickly.

## Troubleshooting
- 500 on `/call`: check `/health` for missing env vars.
- Twilio error on call: verify `TWILIO_FROM_NUMBER` is capable of outbound calls and the `to` number is verified (on trial accounts), and that `PUBLIC_BASE_URL` is reachable over HTTPS.
- No audio / agent not responding: ensure your LiveKit SIP setup routes the SIP participant into the same room where your agent joins or auto-spawns, and your `agent.py` process is running.
