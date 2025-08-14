from fastapi import FastAPI, Request
import os, requests, re
from typing import Dict, Any

app = FastAPI()

# =============================
# ENVIRONMENT VARIABLES
# =============================
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")      # Meta access token (test or permanent)
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")      # From Meta "Getting Started"
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "verify_me")
# Optional: Groq only to rephrase approved replies from our KB (never open-ended)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

WA_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

# =============================
# COMPANY KNOWLEDGE BASE (KB)
# =============================
KB: dict[str, str] = {
    "menu": (
        "👋 *Welcome to Dream Webies!*\n"
        "Please choose an option:\n"
        "1️⃣ About Dream Webies\n"
        "2️⃣ IT Services\n"
        "3️⃣ DWANI (Internships & Training)\n"
        "4️⃣ Certifications\n"
        "5️⃣ Contact Us\n\n"
        "You can also type: *about*, *services*, *dwani*, *internships*, *certifications*, *contact*.\n"
        "Type *menu* anytime to see options again."
    ),
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
        "Type *internships* to see tracks, or *apply* to get the form.\n\n"
        "More info: https://www.dwani.net/"
    ),
    "internships": (
        "📝 *DWANI Internships (Choose a track)*\n"
        "1) Python / AI-ML — Python basics, NumPy/Pandas, ML intro, mini-projects\n"
        "2) Flutter (Mobile) — Dart, widgets, REST APIs, app deployment\n"
        "3) Web Full-Stack — HTML/CSS/JS + backend (Python/Node) + DB basics\n"
        "Duration: 8–12 weeks | Mentored projects | Certificate provided\n"
        "Type *apply* to get the application form.\n\n"
        "Apply here: https://www.dwani.net/"
    ),
    "apply": (
        "🔗 *Apply to DWANI*\n"
        "Application Form: https://www.dwani.net/\n"
        "Fill your details, choose track, and our team will contact you.\n"
        "For queries, type *contact*."
    ),
    "certifications": (
        "📜 *Certifications*\n"
        "• Certificate of Completion for each DWANI track\n"
        "• Project Report/Letter (on request)\n"
        "• Performance feedback from mentor\n"
        "Type *dwani* or *internships* for program details."
    ),
    "contact": (
        "📞 *Contact Dream Webies*\n"
        "Email: dreamwebies@gmail.com\n"
        "Phone: +91 78756 49426\n"
        "Website: https://dreamwebies.com/portfolio.php\n"
        "Share your requirement to get a quick estimate."
    ),
    "oos": (
        "🙏 I can only help with Dream Webies company info, IT services, and the DWANI program.\n"
        "Type *menu* to see options."
    ),
}


# Allowed intents/aliases mapping
ALIASES = {
    "about": {"about", "company", "dream webies", "1"},
    "services": {"services", "it services", "projects", "2"},
    "dwani": {"dwani", "program", "student", "training"},
    "internships": {"internship", "internships", "tracks", "3"},
    "certifications": {"certificate", "certificates", "certifications", "4"},
    "contact": {"contact", "phone", "email", "5"},
    "apply": {"apply", "application", "form", "register"},
    "menu": {"hi", "hello", "start", "menu"},
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
    """Sends a standard text message to a WhatsApp user."""
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
# UTIL: Send WhatsApp Interactive List Message
# =============================
def send_interactive_list_message(to: str, interactive_payload: dict):
    """
    Sends an interactive list message to a WhatsApp user.
    The interactive_payload should be a dictionary formatted
    for a list message, with header, body, action, and sections.
    """
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("Missing WHATSAPP_TOKEN or PHONE_NUMBER_ID")
        return
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": interactive_payload
    }
    try:
        requests.post(WA_URL, headers=headers, json=payload, timeout=20)
    except requests.exceptions.RequestException as e:
        print(f"Error sending interactive message: {e}")

# =============================
# MENU PAYLOAD
# =============================
def get_main_menu_payload():
    """Generates the JSON payload for the main interactive menu."""
    return {
        "type": "list",
        "header": {
            "type": "text",
            "text": "Dream Webies Menu"
        },
        "body": {
            "text": "👋 Welcome to Dream Webies! Please select an option from the menu below."
        },
        "action": {
            "button": "View Options",
            "sections": [
                {
                    "title": "About Us & Services",
                    "rows": [
                        { "id": "about_us", "title": "1️⃣ About Dream Webies", "description": "Our mission and values." },
                        { "id": "it_services", "title": "2️⃣ IT Services", "description": "Web, mobile, and AI solutions." },
                    ]
                },
                {
                    "title": "DWANI Program",
                    "rows": [
                        { "id": "dwani_program", "title": "3️⃣ DWANI (Internships)", "description": "Student growth and training program." },
                        { "id": "certifications", "title": "4️⃣ Certifications", "description": "Certificates for program completion." },
                    ]
                },
                {
                    "title": "Connect",
                    "rows": [
                        { "id": "contact_us", "title": "5️⃣ Contact Us", "description": "Get in touch with our team." },
                    ]
                }
            ]
        },
        "footer": {
            "text": "Type 'menu' anytime to see these options again."
        }
    }


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
        # We pass ONLY the approved KB text. The model must not add external info.
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
def route_intent(user_text: str) -> str:
    """Return a KB answer or out-of-scope message. Groq is never asked open-ended."""
    t = (user_text or "").strip().lower()

    # Normalizations
    t_clean = re.sub(r"\s+", " ", t)

    # Menu words
    if any(t_clean == w for w in ALIASES["menu"]):
        return KB["menu"]

    # Direct aliases
    for key, words in ALIASES.items():
        if key == "menu":
            continue
        if any(t_clean == w or w in t_clean for w in words):
            # map special cases
            if key == "dwani":
                return KB["dwani_intro"]
            if key in KB:
                return KB[key]

    # Numeric shortcuts for menu
    if t_clean in {"1", "2", "3", "4", "5"}:
        mapping = {"1": "about", "2": "services", "3": "dwani_intro", "4": "certifications", "5": "contact"}
        return KB[mapping[t_clean]]

    # If user's text mentions obvious out-of-scope topics → block
    if any(hint in t_clean for hint in OUT_OF_SCOPE_HINTS):
        return KB["oos"]

    # Otherwise try soft matching to company topics
    soft_map = [
        (("about", "who are you", "company info", "dream webies"), KB["about"]),
        (("service", "build app", "project", "website", "mobile", "ai", "cloud"), KB["services"]),
        (("dwani", "student", "training", "internship", "internships", "apply"), KB["dwani_intro"]),
        (("certificate", "certification"), KB["certifications"]),
        (("contact", "email", "phone"), KB["contact"]),
    ]
    for keys, answer in soft_map:
        if any(k in t_clean for k in keys):
            return answer

    # Default: refuse
    return KB["oos"]

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

        # Handle interactive messages (list replies) first
        if msg.get("interactive"):
            interactive_type = msg["interactive"].get("type")
            if interactive_type == "list_reply":
                list_reply_id = msg["interactive"]["list_reply"]["id"]
                # Map the list reply ID to a KB response
                mapping = {
                    "about_us": "about",
                    "it_services": "services",
                    "dwani_program": "dwani_intro",
                    "certifications": "certifications",
                    "contact_us": "contact"
                }
                raw_answer = KB.get(mapping.get(list_reply_id), KB["oos"])
                final_answer = rephrase_with_groq(raw_answer)
                send_text(from_number, final_answer)
                return {"status": "ok"}
            # Future-proof: add logic for other interactive types here if needed

        # Handle standard text messages
        user_text = msg.get("text", {}).get("body", "")
        lc = user_text.strip().lower()

        # If a user types a menu keyword, send the interactive menu
        if any(lc == w for w in ALIASES["menu"]):
            menu_payload = get_main_menu_payload()
            send_interactive_list_message(from_number, menu_payload)
            return {"status": "ok"}

        # Otherwise, route to the KB as a fallback
        raw_answer = route_intent(user_text)
        final_answer = rephrase_with_groq(raw_answer)
        send_text(from_number, final_answer)

    except Exception as e:
        print("Webhook error:", e)

    return {"status": "ok"}
