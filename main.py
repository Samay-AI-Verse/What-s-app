from fastapi import FastAPI, Request
import requests
import os
from typing import Dict, Union

app = FastAPI()

# =======================================================
# ==== ENV VARS (set these on your hosting platform) ====
# =======================================================
# WHATSAPP_TOKEN: The permanent or temporary access token for the WhatsApp Business API.
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
# PHONE_NUMBER_ID: The "From" phone number ID from your WhatsApp Business Account.
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
# VERIFY_TOKEN: A custom token used for webhook verification. Must match the one in Meta's dashboard.
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_verify_token")
# GROQ_API_KEY: Your Groq API key for the AI fallback.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# GROQ_MODEL: The specific Groq model to use, e.g., "llama3-8b-8192".
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
# =======================================================

# Dynamically construct the WhatsApp API URL using the environment variable.
# This is a crucial fix to ensure the bot works in different environments.
if PHONE_NUMBER_ID:
    WA_URL = f"https://graph.facebook.com/v19.0/{756179407576683}/messages"
else:
    # If the PHONE_NUMBER_ID is not set, the bot cannot send messages.
    # Raise an error or log a critical message.
    print("CRITICAL: PHONE_NUMBER_ID environment variable is not set!")
    WA_URL = "https://graph.facebook.com/v19.0/invalid_id/messages"


# Simple in-memory session state (per WhatsApp number)
# WARNING: This is NOT suitable for a production environment like Render, which is stateless.
# The `STATE` will be reset on every server restart or scale event.
# For production, consider a persistent store like Redis, a database, or a cloud function's
# built-in state management.
STATE: Dict[str, str] = {}  # "ROOT", "DWANI", "DWANI_INTERNSHIP"

# ---------- Helper Functions for Messaging and AI ----------

def send_text(to: str, text: str):
    """
    Sends a text message to a given WhatsApp number.
    
    Args:
        to (str): The recipient's WhatsApp number.
        text (str): The message content.
    """
    if not WHATSAPP_TOKEN:
        print("CRITICAL: WHATSAPP_TOKEN is not set. Cannot send messages.")
        return

    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": text}
    }
    try:
        requests.post(WA_URL, headers=headers, json=payload, timeout=20)
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message: {e}")

def menu_root() -> str:
    """Returns the main menu text."""
    return (
        "👋 Welcome to *Dream Webies*!\n"
        "Choose an option:\n"
        "1️⃣ IT Services (Projects & Clients)\n"
        "2️⃣ *DWANI* (Students: internships, learning, jobs)\n"
        "3️⃣ Contact Us\n"
        "Type *menu* anytime to see this again."
    )

def menu_dwani() -> str:
    """Returns the DWANI submenu text."""
    return (
        "🎓 *DWANI – Student Growth Platform*\n"
        "1️⃣ Apply for Internship\n"
        "2️⃣ Learning Resources\n"
        "3️⃣ Job Opportunities\n"
        "4️⃣ Go Back"
    )

def menu_dwani_internship() -> str:
    """Returns the DWANI internship submenu text."""
    return (
        "📝 *DWANI Internships – Choose your track:*\n"
        "1️⃣ Python / AI-ML\n"
        "2️⃣ Flutter (Mobile)\n"
        "3️⃣ Web Full-Stack\n"
        "4️⃣ Go Back"
    )

def groq_chat(user_text: str) -> str:
    """
    Sends a message to the Groq API and returns the AI response.
    
    Args:
        user_text (str): The user's message to send to the AI.
        
    Returns:
        str: The AI's response text.
    """
    if not GROQ_API_KEY:
        print("CRITICAL: GROQ_API_KEY is not set. Cannot use AI fallback.")
        return "Sorry, I can't access my AI brain right now. Please try a different option."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are Dream Webies virtual assistant. Be concise, helpful and friendly."},
            {"role": "user", "content": user_text}
        ],
        "max_tokens": 300
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=40)
        r.raise_for_status() # Raises an exception for bad HTTP status codes
        return r.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        print(f"Groq API call failed: {e}")
        return "I'm having trouble with my AI right now. Please try again later."


# ---------- WhatsApp Webhook verification endpoint ----------
@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    Endpoint for Meta's webhook verification process.
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", 0)

    # Check if the mode is 'subscribe' and the tokens match.
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified successfully!")
        return int(challenge)
    
    print("Webhook verification failed.")
    return "Verification failed"

# ---------- WhatsApp Incoming Messages endpoint ----------
@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    Endpoint to receive and process incoming WhatsApp messages.
    """
    data: Dict[str, Union[list, dict]] = await request.json()
    try:
        # Check for the expected structure of a WhatsApp message notification.
        if "entry" not in data or not data["entry"][0].get("changes"):
            print("Received data without 'entry' or 'changes'. Ignoring.")
            return {"status": "ignored"}

        changes = data["entry"][0]["changes"][0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            print("Received changes without messages. Ignoring.")
            return {"status": "no_message"}

        msg = messages[0]
        from_number = msg.get("from")
        # Extract the message text, handling potential missing fields.
        text_body = msg.get("text", {}).get("body", "")
        user_text = (text_body or "").strip()

        # Handle button or list replies here if needed.
        # For this example, we only process text messages.

        # Normalize the user input to lowercase for case-insensitive matching.
        lc = user_text.lower()

        # Get or initialize the user's state.
        state = STATE.get(from_number, "ROOT")

        # --- GLOBAL SHORTCUTS ---
        # These commands work from any state.
        if lc in ["hi", "hello", "hey", "menu", "start"]:
            STATE[from_number] = "ROOT"
            send_text(from_number, menu_root())
            return {"status": "ok"}

        # --- STATE MACHINE LOGIC ---
        if state == "ROOT":
            if lc == "1":
                # IT Services option
                reply = (
                    "💼 *Dream Webies – IT Services*\n"
                    "• Web & Mobile Development\n"
                    "• AI & Data Science Projects\n"
                    "• Cloud & DevOps\n"
                    "• Custom Software Solutions\n\n"
                    "Reply with your project idea, timeline, and budget, and our team will reach out.\n"
                    "Or type *menu* to go back."
                )
                send_text(from_number, reply)
            elif lc == "2":
                # DWANI submenu
                STATE[from_number] = "DWANI"
                send_text(from_number, menu_dwani())
            elif lc == "3":
                # Contact Us option
                reply = (
                    "📞 *Contact Dream Webies*\n"
                    "Email: info@dreamwebies.com\n"
                    "Phone: +91-98765-43210\n"
                    "Website: https://dreamwebies.com\n\n"
                    "Type *menu* to return."
                )
                send_text(from_number, reply)
            else:
                # If the input doesn't match a menu option, use the AI fallback.
                ai = groq_chat(user_text)
                send_text(from_number, ai + "\n\n(Type *menu* to see options.)")

        elif state == "DWANI":
            if lc == "1":
                # DWANI Internship submenu
                STATE[from_number] = "DWANI_INTERNSHIP"
                send_text(from_number, menu_dwani_internship())
            elif lc == "2":
                # Learning Resources option
                reply = (
                    "📚 *DWANI Learning Resources*\n"
                    "• Python & AI/ML roadmap: https://example.com/learn/python-ai-ml\n"
                    "• Flutter crash course: https://example.com/learn/flutter\n"
                    "• Web Full-Stack path: https://example.com/learn/web-fullstack\n\n"
                    "Type *4* to go back or *menu* to main."
                )
                send_text(from_number, reply)
            elif lc == "3":
                # Job Opportunities option
                reply = (
                    "💼 *DWANI Jobs (Current Openings)*\n"
                    "• Python/AI-ML Intern (Remote)\n"
                    "• Flutter Developer Intern (Onsite/Remote)\n"
                    "• Web Full-Stack Intern (Remote)\n\n"
                    "Apply here: https://example.com/dwani/jobs\n"
                    "Type *4* to go back or *menu* to main."
                )
                send_text(from_number, reply)
            elif lc == "4":
                # Go Back to the main menu
                STATE[from_number] = "ROOT"
                send_text(from_number, menu_root())
            else:
                # AI fallback for the DWANI state
                ai = groq_chat(user_text)
                send_text(from_number, ai + "\n\n(You are in *DWANI*. Type *4* to go back or *menu* for main.)")

        elif state == "DWANI_INTERNSHIP":
            if lc == "1":
                # Apply Python / AI-ML Internship
                reply = (
                    "📝 *Apply – Python / AI-ML Internship*\n"
                    "Form: https://example.com/apply/python-aiml\n"
                    "Prereqs: Python basics, NumPy/Pandas, ML intro.\n"
                    "Duration: 8–12 weeks\n"
                    "Type *4* to go back or *menu*."
                )
                send_text(from_number, reply)
            elif lc == "2":
                # Apply Flutter Internship
                reply = (
                    "📝 *Apply – Flutter Internship*\n"
                    "Form: https://example.com/apply/flutter\n"
                    "Prereqs: Dart, basic Flutter widgets, REST APIs.\n"
                    "Duration: 8–12 weeks\n"
                    "Type *4* to go back or *menu*."
                )
                send_text(from_number, reply)
            elif lc == "3":
                # Apply Web Full-Stack Internship
                reply = (
                    "📝 *Apply – Web Full-Stack Internship*\n"
                    "Form: https://example.com/apply/web-fullstack\n"
                    "Prereqs: HTML/CSS/JS, one backend (Node/Python), DB basics.\n"
                    "Duration: 8–12 weeks\n"
                    "Type *4* to go back or *menu*."
                )
                send_text(from_number, reply)
            elif lc == "4":
                # Go Back to the DWANI menu
                STATE[from_number] = "DWANI"
                send_text(from_number, menu_dwani())
            else:
                # AI fallback for the DWANI_INTERNSHIP state
                ai = groq_chat(user_text)
                send_text(from_number, ai + "\n\n(You are in *DWANI → Internships*. Type *4* to go back or *menu*.)")

        else:
            # Unknown state → reset the session
            STATE[from_number] = "ROOT"
            send_text(from_number, menu_root())

    except Exception as e:
        # A broad catch-all is good to prevent webhook failures, but
        # consider more specific logging or error handling in production.
        print(f"Error processing webhook payload: {e}")

    return {"status": "ok"}
