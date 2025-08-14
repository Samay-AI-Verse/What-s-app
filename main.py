from fastapi import FastAPI, Request
import requests
import os

app = FastAPI()

# =============================
# ENVIRONMENT VARIABLES
# =============================
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")  # Meta test token
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  # Meta phone number ID
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_verify_token")  # Your secret token
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Groq API key
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")  # Groq model

WA_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

# =============================
# SEND WHATSAPP TEXT MESSAGE
# =============================
def send_text(to: str, text: str):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": text}
    }
    requests.post(WA_URL, headers=headers, json=payload, timeout=20)

# =============================
# GROQ AI CHAT
# =============================
def groq_chat(user_text: str) -> str:
    if not GROQ_API_KEY:
        return "AI service is not available right now."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are a friendly and helpful WhatsApp chatbot."},
            {"role": "user", "content": user_text}
        ],
        "max_tokens": 300
    }
    r = requests.post(url, headers=headers, json=payload, timeout=40)
    return r.json()["choices"][0]["message"]["content"].strip()

# =============================
# MENU
# =============================
def menu_root():
    return (
        "👋 Welcome!\n"
        "1️⃣ Our Services\n"
        "2️⃣ Contact Info\n"
        "Type anything else to chat with AI.\n"
        "Type *menu* anytime to see this again."
    )

# =============================
# VERIFY WEBHOOK (GET)
# =============================
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", 0)
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    return "Verification failed"

# =============================
# RECEIVE WHATSAPP MESSAGE (POST)
# =============================
@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    try:
        messages = data["entry"][0]["changes"][0]["value"].get("messages", [])
        if not messages:
            return {"status": "no_message"}

        msg = messages[0]
        from_number = msg["from"]
        user_text = msg.get("text", {}).get("body", "").strip()

        lc = user_text.lower()

        # Show menu
        if lc in ["hi", "hello", "menu", "start"]:
            send_text(from_number, menu_root())
            return {"status": "ok"}

        # Menu options
        if lc == "1":
            send_text(from_number, "💼 We provide AI, Web, and Mobile development services.")
            return {"status": "ok"}
        elif lc == "2":
            send_text(from_number, "📞 Contact us: info@example.com | +91-98765-43210")
            return {"status": "ok"}

        # AI fallback
        ai_reply = groq_chat(user_text)
        send_text(from_number, ai_reply + "\n\nType *menu* to see options.")

    except Exception as e:
        print("Error:", e)

    return {"status": "ok"}
