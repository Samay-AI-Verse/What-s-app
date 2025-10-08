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
KB: dict[str, str] = {
    "about": (
        "🏢 *About Dream Webies*\n"
        "Dream Webies is an IT company delivering end-to-end solutions in Web & Mobile, AI/Data, and Cloud/DevOps.\n"
        "We focus on quality delivery, transparent timelines, and scalable architecture.\n"
        "Clients choose us for product thinking, fast execution, and long-term support."
    ),
    "services_intro": (
        "💼 *IT Services*\n"
        "We specialize in a variety of IT solutions. Please select the service you are interested in to tell us more about your project."
    ),
    "dwani_intro": (
        "🎓 *DWANI — Student Growth Program*\n"
        "Internships, training, and certifications designed for practical skills and job-readiness.\n"
        "Tracks: Python/AI-ML, Flutter (Mobile), Web Full-Stack.\n"
        "Includes mentorship, project work, and certificate on completion.\n"
        "More info: https://www.dwani.net/"
    ),
    "internships": (
        "📝 *DWANI Internship Tracks*\n"
        "1) Python / AI-ML — Python basics, NumPy/Pandas, ML intro, mini-projects\n"
        "2) Flutter (Mobile) — Dart, widgets, REST APIs, app deployment\n"
        "3) Web Full-Stack — HTML/CSS/JS + backend (Python/Node) + DB basics\n"
        "Duration: 8–12 weeks | Mentored projects | Certificate provided"
    ),
    "apply": (
        "🔗 *Apply to DWANI*\n"
        "Application Form: https://www.dwani.net/\n"
        "Fill your details, choose a track, and our team will contact you."
    ),
    "certifications": (
        "📜 *Certifications*\n"
        "Upon successful completion of the DWANI program, you will receive a Certificate of Completion, a Project Report, and a Letter of Recommendation from your mentor."
    ),
    "contact": (
        "📞 *Contact Dream Webies*\n"
        "Email: dreamwebies@gmail.com\n"
        "Phone: +91 78756 49426\n"
        "Website: https://dreamwebies.com/portfolio.php"
    ),
    "oos": (
        "🙏 I can only help with Dream Webies company info, IT services, and the DWANI program.\n"
        "Please select an option from the menu to continue."
    ),
}

# Aliases for text-based fallback
ALIASES = {
    "about": {"about", "company", "dream webies", "1"},
    "services": {"services", "it services", "projects", "2"},
    "dwani_intro": {"dwani", "program", "student", "training", "dwani_program", "3"},
    "certifications": {"certificate", "certificates", "certifications", "4"},
    "contact": {"contact", "phone", "email", "5"},
    "menu": {"hi", "hello", "start", "menu"},
}

OUT_OF_SCOPE_HINTS = {
    "math", "solve", "translate", "news", "weather", "movie", "code", "program",
    "python error", "history", "politics", "celebrity", "recipe", "lyrics", "stock",
    "sports", "medical", "legal", "tax", "gaming", "travel", "horoscope"
}

# =============================
# UTIL: Send WhatsApp Messages
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

def send_image(to: str, image_url: str, caption: str) -> None:
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("Missing WHATSAPP_TOKEN or PHONE_NUMBER_ID")
        return
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    try:
        requests.post(WA_URL, headers=headers, json=payload, timeout=20)
    except requests.exceptions.RequestException as e:
        print("WhatsApp image send error:", e)

def send_interactive_message(to: str, interactive_payload: dict):
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
# INTERACTIVE PAYLOADS
# =============================
def get_main_menu_payload():
    return {
        "type": "list",
        "header": {"type": "text", "text": "Dream Webies Menu"},
        "body": {"text": "👋 Welcome! How can I help you today?"},
        "action": {
            "button": "View Options",
            "sections": [
                {"title": "Our Company", "rows": [
                    {"id": "about_us", "title": "1️⃣ About Dream Webies", "description": "Our mission and values."},
                    {"id": "it_services_menu", "title": "2️⃣ IT Services", "description": "Web, mobile, and AI solutions."},
                ]},
                {"title": "DWANI Program", "rows": [
                    {"id": "dwani_program", "title": "3️⃣ DWANI (Internships)", "description": "Student growth and training program."},
                    {"id": "certifications", "title": "4️⃣ Certifications", "description": "Certificates for program completion."},
                ]},
                {"title": "Connect", "rows": [
                    {"id": "contact_us", "title": "5️⃣ Contact Us", "description": "Get in touch with our team."},
                ]}
            ]
        },
        "footer": {"text": "Type 'menu' anytime to see these options again."}
    }

def get_it_services_menu_payload():
    return {
        "type": "list",
        "header": {"type": "text", "text": "IT Services"},
        "body": {"text": "What type of project are you looking for?"},
        "action": {
            "button": "Select a Service",
            "sections": [
                {"title": "Our Expertise", "rows": [
                    {"id": "service_web", "title": "Web Development", "description": "Websites, web apps, APIs."},
                    {"id": "service_mobile", "title": "Mobile Apps", "description": "iOS/Android apps with Flutter."},
                    {"id": "service_ai", "title": "AI & Data Solutions", "description": "ML models, data analytics."},
                    {"id": "service_cloud", "title": "Cloud & DevOps", "description": "CI/CD, infrastructure."},
                ]},
                {"title": "Need something else?", "rows": [
                    {"id": "contact_us", "title": "Contact Us Directly", "description": "For custom solutions and quotes."},
                ]},
            ]
        },
        "footer": {"text": "Select a service to get started."}
    }

def get_dwani_buttons_payload():
    return {
        "type": "button",
        "header": {"type": "text", "text": "DWANI Student Growth Program"},
        "body": {"text": "Our program offers practical training and mentorship. Which would you like to know more about?"},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "internship_tracks", "title": "Internship Tracks"}},
                {"type": "reply", "reply": {"id": "certifications", "title": "Certifications"}},
                {"type": "reply", "reply": {"id": "apply_form", "title": "Apply Now"}},
            ]
        },
        "footer": {"text": "Select an option to proceed."}
    }

def get_after_service_prompt_payload(service_name):
    return {
        "type": "button",
        "body": {
            "text": f"Thank you for your interest in {service_name}! To give you an accurate estimate, please share more details about your project, including your timeline and budget."
        },
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "contact_us", "title": "Share Details & Contact"}},
                {"type": "reply", "reply": {"id": "it_services_menu", "title": "Back to Services"}},
            ]
        },
        "footer": {"text": "We look forward to hearing from you!"}
    }

def get_back_to_menu_button_payload():
    return {
        "type": "button",
        "body": {"text": "Would you like to explore other options?"},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "main_menu", "title": "Main Menu"}},
            ]
        },
        "footer": {"text": "Tap the button above."}
    }


# =============================
# OPTIONAL: Groq rephrasing (KB-only)
# =============================
def rephrase_with_groq(original: str) -> str:
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
async def handle_message(request: Request):
    data: Dict[str, Any] = await request.json()
    try:
        messages = data["entry"][0]["changes"][0]["value"].get("messages", [])
        if not messages:
            return {"status": "no_message"}

        msg = messages[0]
        from_number = msg.get("from")

        # --- Handle Interactive Messages (List and Button Replies) ---
        if msg.get("interactive"):
            interactive_type = msg["interactive"].get("type")
            if interactive_type == "list_reply":
                reply_id = msg["interactive"]["list_reply"]["id"]
            elif interactive_type == "button_reply":
                reply_id = msg["interactive"]["button_reply"]["id"]
            else:
                return {"status": "unsupported_interactive_type"}

            if reply_id == "main_menu":
                send_interactive_message(from_number, get_main_menu_payload())
            elif reply_id == "it_services_menu":
                send_interactive_message(from_number, get_it_services_menu_payload())
            elif reply_id.startswith("service_"):
                service_map = {
                    "service_web": "Web Development",
                    "service_mobile": "Mobile Apps",
                    "service_ai": "AI & Data Solutions",
                    "service_cloud": "Cloud & DevOps"
                }
                service_name = service_map.get(reply_id, "an IT service")
                send_interactive_message(from_number, get_after_service_prompt_payload(service_name))
            elif reply_id == "dwani_program":
                send_interactive_message(from_number, get_dwani_buttons_payload())
            elif reply_id == "internship_tracks":
                send_text(from_number, rephrase_with_groq(KB["internships"]))
                send_interactive_message(from_number, get_back_to_menu_button_payload())
            elif reply_id == "certifications":
                send_text(from_number, rephrase_with_groq(KB["certifications"]))
                # A public image of a sample certificate (replace with your own)
                cert_image_url = "https://i.imgur.com/3N4o1fB.png"
                send_image(from_number, cert_image_url, "Here is a sample certificate you can earn.")
                send_interactive_message(from_number, get_back_to_menu_button_payload())
            elif reply_id == "apply_form":
                send_text(from_number, rephrase_with_groq(KB["apply"]))
            elif reply_id == "about_us":
                send_text(from_number, rephrase_with_groq(KB["about"]))
                send_interactive_message(from_number, get_back_to_menu_button_payload())
            elif reply_id == "contact_us":
                send_text(from_number, rephrase_with_groq(KB["contact"]))
                send_interactive_message(from_number, get_back_to_menu_button_payload())
            else:
                send_text(from_number, KB["oos"])
                send_interactive_message(from_number, get_main_menu_payload())
            
            return {"status": "ok"}
        
        # --- Handle Standard Text Messages as a fallback ---
        user_text = msg.get("text", {}).get("body", "")
        lc = user_text.strip().lower()

        if any(lc == w for w in ALIASES["menu"]):
            send_interactive_message(from_number, get_main_menu_payload())
        elif lc in ALIASES["services"]:
            send_interactive_message(from_number, get_it_services_menu_payload())
        elif lc in ALIASES["dwani_intro"]:
            send_interactive_message(from_number, get_dwani_buttons_payload())
        elif lc in ALIASES["certifications"]:
            send_text(from_number, rephrase_with_groq(KB["certifications"]))
            cert_image_url = "https://i.imgur.com/3N4o1fB.png" # Replace with a real image link
            send_image(from_number, cert_image_url, "Here is a sample certificate you can earn.")
            send_interactive_message(from_number, get_back_to_menu_button_payload())
        else:
            send_text(from_number, rephrase_with_groq(KB["oos"]))
            send_interactive_message(from_number, get_main_menu_payload())

    except Exception as e:
        print("Webhook error:", e)

    return {"status": "ok"}

