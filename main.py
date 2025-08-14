from fastapi import FastAPI, Request
import os, requests, re
from typing import Dict, Any

app = FastAPI()

# =============================
# ENVIRONMENT VARIABLES
# =============================
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "verify_me")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

WA_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

# =============================
# COMPANY KNOWLEDGE BASE (KB)
# =============================
# Updated KB to support new interactive message types.
KB: Dict[str, Any] = {
    "menu_list": {
        "text": "👋 Welcome to Dream Webies! Please choose an option below:",
        "button": "View Menu",
        "sections": [
            {
                "title": "Main Menu",
                "rows": [
                    {"id": "menu_about", "title": "1️⃣ About Dream Webies", "description": "Learn about our company"},
                    {"id": "menu_services", "title": "2️⃣ IT Services", "description": "See our project offerings"},
                    {"id": "menu_dwani", "title": "3️⃣ DWANI (Internships & Training)", "description": "Explore our student programs"},
                    {"id": "menu_certifications", "title": "4️⃣ Certifications", "description": "Details on our certificates"},
                    {"id": "menu_contact", "title": "5️⃣ Contact Us", "description": "Get in touch with our team"}
                ]
            }
        ]
    },
    "about": (
        "🏢 *About Dream Webies*\n"
        "Dream Webies is an IT company delivering end-to-end solutions in Web & Mobile, AI/Data, and Cloud/DevOps.\n"
        "We focus on quality delivery, transparent timelines, and scalable architecture.\n"
        "Clients choose us for product thinking, fast execution, and long-term support.\n"
        "Type *services* to see what we build."
    ),
    "services": (
        "💼 *IT Services (Projects & Clients)*\n"
        "• Web Development (frontend, backend, APIs)\n"
        "• Mobile Apps (Flutter/React Native)\n"
        "• AI & Data (ML models, analytics, RAG)\n"
        "• Cloud & DevOps (CI/CD, Docker, Kubernetes)\n"
        "• Custom Software (B2B tools, dashboards)\n\n"
        "Reply with your idea, timeline, and budget to start, or type *contact*."
    ),
    "dwani_intro": (
        "🎓 *DWANI — Student Growth Program*\n"
        "Internships, training, and certifications designed for practical skills and job-readiness.\n"
        "Tracks: Python/AI-ML, Flutter (Mobile), Web Full-Stack.\n"
        "Includes mentorship, project work, and certificate on completion.\n"
        "Type *internships* to see tracks, or *apply* to get the form."
    ),
    "internships": (
        "📝 *DWANI Internships (Choose a track)*\n"
        "1) Python / AI-ML — Python basics, NumPy/Pandas, ML intro, mini-projects\n"
        "2) Flutter (Mobile) — Dart, widgets, REST APIs, app deployment\n"
        "3) Web Full-Stack — HTML/CSS/JS + backend (Python/Node) + DB basics\n"
        "Duration: 8–12 weeks | Mentored projects | Certificate provided\n"
        "Type *apply* to get the application form."
    ),
    # Interactive message with URL button
    "apply": {
        "text": "🔗 *Apply to DWANI*\nReady to apply? Click the button below to fill out your details, choose a track, and our team will contact you.",
        "button_text": "Apply Now",
        "url": "https://example.com/apply" # Replace with your real link
    },
    "certifications": (
        "📜 *Certifications*\n"
        "• Certificate of Completion for each DWANI track\n"
        "• Project Report/Letter (on request)\n"
        "• Performance feedback from mentor\n"
        "Type *dwani* or *internships* for program details."
    ),
    # Interactive message with URL and phone/email buttons
    "contact": {
        "text": "📞 *Contact Dream Webies*\nHave questions? You can reach us directly via the options below.",
        "buttons": [
            {"type": "url", "title": "Visit Website", "url": "https://dreamwebies.com"},
            {"type": "url", "title": "Email Us", "url": "mailto:info@dreamwebies.com"},
            {"type": "url", "title": "Call Us", "url": "tel:+91-98765-43210"}
        ]
    },
    "oos": (  # out-of-scope message
        "🙏 I can only help with Dream Webies company info, IT services, and the DWANI program.\n"
        "Tap the menu button to see options."
    ),
}

# Allowed intents/aliases mapping
ALIASES = {
    "menu": {"hi", "hello", "start", "menu"},
    "about": {"about", "company", "dream webies", "1"},
    "services": {"services", "it services", "projects", "2"},
    "dwani": {"dwani", "program", "student", "training", "3"},
    "internships": {"internship", "internships", "tracks"},
    "certifications": {"certificate", "certificates", "certifications", "4"},
    "contact": {"contact", "phone", "email", "5"},
    "apply": {"apply", "application", "form", "register"},
}

# Hard guardrail keywords – if detected with no company intent, we refuse
OUT_OF_SCOPE_HINTS = {
    "math", "solve", "translate", "news", "weather", "movie", "code", "program",
    "python error", "history", "politics", "celebrity", "recipe", "lyrics", "stock",
    "sports", "medical", "legal", "tax", "gaming", "travel", "horoscope"
}

# =============================
# UTIL: Send WhatsApp text
# =============================
def send_text(to: str, text: str) -> None:
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("Missing WHATSAPP_TOKEN or PHONE_NUMBER_ID")
        return
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "text": {"body": text}}
    try:
        requests.post(WA_URL, headers=headers, json=payload, timeout=20)
    except requests.exceptions.RequestException as e:
        print("WhatsApp send error:", e)

# =============================
# UTIL: Send WhatsApp interactive message (list/button)
# =============================
def send_interactive_message(to: str, message_data: Dict[str, Any]) -> None:
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("Missing WHATSAPP_TOKEN or PHONE_NUMBER_ID")
        return
    
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    
    message_type = "interactive"
    
    if "sections" in message_data:
        # This is a list message
        interactive_payload = {
            "type": "list",
            "body": {"text": message_data["text"]},
            "action": {
                "button": message_data["button"],
                "sections": message_data["sections"]
            }
        }
    elif "buttons" in message_data:
        # This is a button message (with multiple URL buttons)
        interactive_payload = {
            "type": "button",
            "body": {"text": message_data["text"]},
            "action": {
                "buttons": message_data["buttons"]
            }
        }
    elif "url" in message_data:
        # This is a reply button message with a single URL
        interactive_payload = {
            "type": "button",
            "body": {"text": message_data["text"]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "button_id_1", "title": message_data["button_text"]}},
                    {"type": "url", "title": "Visit Link", "url": message_data["url"]}
                ]
            }
        }
    else:
        print("Invalid interactive message type.")
        return
        
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": message_type,
        message_type: interactive_payload
    }
    
    try:
        requests.post(WA_URL, headers=headers, json=payload, timeout=20)
    except requests.exceptions.RequestException as e:
        print("WhatsApp interactive message send error:", e)

# =============================
# OPTIONAL: Groq rephrasing (KB-only)
# =============================
def rephrase_with_groq(original: str) -> str:
    """
    Rephrase the already-approved KB answer for tone/fluency only.
    NEVER answer open-ended questions. If GROQ_API_KEY is missing, return original.
    """
    if not GROQ_API_KEY:
        return original
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        system = (
            "You are a company chatbot for Dream Webies. "
            "Only rewrite the provided ANSWER for clarity and friendliness. "
            "Do NOT add new facts. Do NOT answer questions outside company scope."
        )
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": f"ANSWER:\n{original}\n\nRewrite it politely for WhatsApp (keep emojis)."}
            ],
            "max_tokens": 220,
            "temperature": 0.2
        }
        r = requests.post(url, headers=headers, json=payload, timeout=35)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("Groq rephrase failed:", e)
        return original

# =============================
# INTENT ROUTER (Strict)
# =============================
def route_intent(user_text: str) -> tuple:
    """Return a KB answer and its type (text or interactive)."""
    t = (user_text or "").strip().lower()

    # Normalizations
    t_clean = re.sub(r"\s+", " ", t)

    # Handle interactive list message replies (button clicks)
    if t_clean.startswith("menu_"):
        map_id_to_key = {
            "menu_about": "about",
            "menu_services": "services",
            "menu_dwani": "dwani_intro",
            "menu_certifications": "certifications",
            "menu_contact": "contact"
        }
        key = map_id_to_key.get(t_clean)
        if key and key in KB:
            return KB[key], "text" if isinstance(KB[key], str) else "interactive"

    # Direct aliases
    for key, words in ALIASES.items():
        if any(t_clean == w or w in t_clean for w in words):
            kb_key = key
            if key == "dwani":
                kb_key = "dwani_intro"
            elif key == "menu":
                return KB["menu_list"], "interactive"

            if kb_key in KB:
                return KB[kb_key], "text" if isinstance(KB[kb_key], str) else "interactive"

    # If user's text mentions obvious out-of-scope topics → block
    if any(hint in t_clean for hint in OUT_OF_SCOPE_HINTS):
        return KB["oos"], "text"

    # Otherwise try soft matching to company topics
    soft_map = [
        (("about", "who are you", "company info", "dream webies"), "about"),
        (("service", "build app", "project", "website", "mobile", "ai", "cloud"), "services"),
        (("dwani", "student", "training", "internship", "internships", "apply"), "dwani_intro"),
        (("certificate", "certification"), "certifications"),
        (("contact", "email", "phone"), "contact"),
    ]
    for keys, answer_key in soft_map:
        if any(k in t_clean for k in keys):
            return KB[answer_key], "text" if isinstance(KB[answer_key], str) else "interactive"

    # Default: refuse and show menu
    return KB["menu_list"], "interactive"

# =============================
# WEBHOOK VERIFY (GET)
# =============================
@app.get("/webhook")
async def verify_webhook(request: Request):
    p = dict(request.query_params)
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == VERIFY_TOKEN:
        return int(p.get("hub.challenge", 0))
    return "Verification failed"

# =============================
# WEBHOOK RECEIVE (POST)
# =============================
@app.post("/webhook")
async def receive_webhook(request: Request):
    data: Dict[str, Any] = await request.json()
    try:
        messages = data["entry"][0]["changes"][0]["value"].get("messages", [])
        if not messages:
            return {"status": "no_message"}

        msg = messages[0]
        from_number = msg.get("from")
        
        # Check for both text messages and interactive replies
        if "text" in msg:
            user_text = msg["text"]["body"]
        elif "interactive" in msg:
            # Handle list and button replies
            if "list_reply" in msg["interactive"]:
                user_text = msg["interactive"]["list_reply"]["id"]
            elif "button_reply" in msg["interactive"]:
                user_text = msg["interactive"]["button_reply"]["id"]
            else:
                user_text = ""
        else:
            user_text = ""
            
        # Route strictly to KB
        raw_answer, answer_type = route_intent(user_text)
        
        # If it's a text response, optionally polish with Groq
        if answer_type == "text":
            final_answer = rephrase_with_groq(raw_answer)
            send_text(from_number, final_answer)
        elif answer_type == "interactive":
            send_interactive_message(from_number, raw_answer)
        
    except Exception as e:
        print("Webhook error:", e)

    return {"status": "ok"}
