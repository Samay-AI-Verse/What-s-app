from fastapi import FastAPI, Request
import os, requests, re
from typing import Dict, Any

app = FastAPI()

# =============================
# ENVIRONMENT VARIABLES
# =============================
# Get Meta access token (test or permanent)
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
# Get Phone number ID from Meta "Getting Started"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "verify_me")

# Optional: Groq only to rephrase approved replies from our KB (never open-ended)
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
    "services": (
        "💼 *IT Services (Projects & Clients)*\n"
        "• Web Development (frontend, backend, APIs)\n"
        "• Mobile Apps (Flutter/React Native)\n"
        "• AI & Data (ML models, analytics, RAG)\n"
        "• Cloud & DevOps (CI/CD, Docker, Kubernetes)\n"
        "• Custom Software (B2B tools, dashboards)"
    ),
    "dwani_intro": (
        "🎓 *DWANI — Student Growth Program*\n"
        "Internships, training, and certifications designed for practical skills and job-readiness.\n"
        "Tracks: Python/AI-ML, Flutter (Mobile), Web Full-Stack.\n"
        "Includes mentorship, project work, and certificate on completion.\n"
        "More info: https://www.dwani.net/"
    ),
    "internships": (
        "📝 *DWANI Internships (Choose a track)*\n"
        "1) Python / AI-ML — Python basics, NumPy/Pandas, ML intro, mini-projects\n"
        "2) Flutter (Mobile) — Dart, widgets, REST APIs, app deployment\n"
        "3) Web Full-Stack — HTML/CSS/JS + backend (Python/Node) + DB basics\n"
        "Duration: 8–12 weeks | Mentored projects | Certificate provided\n"
        "Apply here: https://www.dwani.net/"
    ),
    "apply": (
        "🔗 *Apply to DWANI*\n"
        "Application Form: https://www.dwani.net/\n"
        "Fill your details, choose track, and our team will contact you.\n"
    ),
    "certifications": (
        "📜 *Certifications*\n"
        "• Certificate of Completion for each DWANI track\n"
        "• Project Report/Letter (on request)\n"
        "• Performance feedback from mentor"
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

# Allowed intents/aliases mapping
ALIASES = {
    "about": {"about", "company", "dream webies", "1"},
    "services": {"services", "it services", "projects", "2"},
    "dwani_intro": {"dwani", "program", "student", "training", "dwani_program", "3"},
    "internships": {"internship", "internships", "tracks", "internship_tracks"},
    "certifications": {"certificate", "certificates", "certifications", "4"},
    "contact": {"contact", "phone", "email", "5"},
    "apply": {"apply", "application", "form", "register", "apply_form"},
    "menu": {"hi", "hello", "start", "menu"},
}

# Hard guardrail keywords
OUT_OF_SCOPE_HINTS = {
    "math", "solve", "translate", "news", "weather", "movie", "code", "program",
    "python error", "history", "politics", "celebrity", "recipe", "lyrics", "stock",
    "sports", "medical", "legal", "tax", "gaming", "travel", "horoscope"
}


# =============================
# UTIL: Send WhatsApp Text
# =============================
def send_text(to: str, text: str) -> None:
    """Sends a standard text message."""
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
# UTIL: Send WhatsApp Interactive Message (Button or List)
# =============================
def send_interactive_message(to: str, interactive_payload: dict):
    """
    Sends an interactive message (list or button) to a WhatsApp user.
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
# INTERACTIVE PAYLOADS
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
            "text": "👋 Welcome! How can I help you today?"
        },
        "action": {
            "button": "View Options",
            "sections": [
                {
                    "title": "About Us & Services",
                    "rows": [
                        {"id": "about_us", "title": "1️⃣ About Dream Webies", "description": "Our mission and values."},
                        {"id": "it_services", "title": "2️⃣ IT Services", "description": "Web, mobile, and AI solutions."},
                    ]
                },
                {
                    "title": "DWANI Program",
                    "rows": [
                        {"id": "dwani_program", "title": "3️⃣ DWANI (Internships)", "description": "Student training program."},
                        {"id": "certifications", "title": "4️⃣ Certifications", "description": "Certificates for program completion."},
                    ]
                },
                {
                    "title": "Connect",
                    "rows": [
                        {"id": "contact_us", "title": "5️⃣ Contact Us", "description": "Get in touch with our team."},
                    ]
                }
            ]
        },
        "footer": {
            "text": "Type 'menu' anytime to see these options again."
        }
    }


def get_dwani_buttons_payload():
    """Generates a button message for the DWANI program."""
    return {
        "type": "button",
        "header": {
            "type": "text",
            "text": "DWANI Student Growth Program"
        },
        "body": {
            "text": "Our program offers practical training and mentorship. Which would you like to know more about?"
        },
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "internship_tracks", "title": "Internship Tracks"}},
                {"type": "reply", "reply": {"id": "certifications", "title": "Certifications"}},
                {"type": "reply", "reply": {"id": "apply_form", "title": "Apply Now"}},
            ]
        },
        "footer": {
            "text": "Select an option to proceed."
        }
    }


def get_internship_list_payload():
    """Generates a list message for internship tracks."""
    return {
        "type": "list",
        "header": {
            "type": "text",
            "text": "DWANI Internship Tracks"
        },
        "body": {
            "text": "Choose a track to view details:"
        },
        "action": {
            "button": "View Tracks",
            "sections": [
                {
                    "title": "Available Tracks",
                    "rows": [
                        {"id": "intern_python_ai", "title": "Python / AI-ML", "description": "Python, ML intro, mini-projects."},
                        {"id": "intern_flutter", "title": "Flutter (Mobile)", "description": "Dart, widgets, REST APIs, app deployment."},
                        {"id": "intern_web", "title": "Web Full-Stack", "description": "HTML/CSS/JS + backend."},
                    ]
                }
            ]
        },
        "footer": {
            "text": "Select a track or type 'apply' to get the form."
        }
    }


def get_apply_button_payload():
    """Generates a button message to get the application form."""
    return {
        "type": "button",
        "body": {
            "text": "Ready to apply for the DWANI program?\nClick the button below to fill out the form."
        },
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "apply_form", "title": "Apply Now"}},
                {"type": "reply", "reply": {"id": "main_menu", "title": "Back to Main Menu"}},
            ]
        },
        "footer": {
            "text": "We'll get back to you shortly!"
        }
    }


# =============================
# OPTIONAL: Groq rephrasing (KB-only)
# =============================
def rephrase_with_groq(original: str) -> str:
    """
    Rephrase the already-approved KB answer for tone/fluency only.
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

            # Map interactive replies to a response
            if reply_id == "main_menu":
                send_interactive_message(from_number, get_main_menu_payload())
            elif reply_id == "dwani_program":
                send_interactive_message(from_number, get_dwani_buttons_payload())
            elif reply_id == "it_services":
                # For services, we provide the text info and then a button to contact
                raw_answer = KB.get("services", KB["oos"])
                final_answer = rephrase_with_groq(raw_answer)
                send_text(from_number, final_answer)
                send_interactive_message(from_number, get_contact_button_payload())
            elif reply_id == "internship_tracks":
                send_interactive_message(from_number, get_internship_list_payload())
            elif reply_id == "apply_form":
                send_text(from_number, KB["apply"])
            else:
                # For other menu options, send the KB text and a back-to-menu button
                # This covers `about_us`, `certifications`, `contact_us`, and `internship_tracks`
                # And also new interactive IDs like `intern_python_ai`, `intern_flutter`, `intern_web`
                mapping = {
                    "about_us": "about",
                    "certifications": "certifications",
                    "contact_us": "contact",
                    "intern_python_ai": "internships", # This will be handled as a general internship response
                    "intern_flutter": "internships",
                    "intern_web": "internships",
                }
                key = mapping.get(reply_id, None)
                if key:
                    raw_answer = KB.get(key, KB["oos"])
                    final_answer = rephrase_with_groq(raw_answer)
                    send_text(from_number, final_answer)
                    send_interactive_message(from_number, get_back_to_menu_button_payload())
                else:
                    send_text(from_number, KB["oos"])
            
            return {"status": "ok"}
        
        # --- Handle Standard Text Messages as a fallback ---
        user_text = msg.get("text", {}).get("body", "")
        lc = user_text.strip().lower()

        # Check for main menu keywords first
        if any(lc == w for w in ALIASES["menu"]):
            send_interactive_message(from_number, get_main_menu_payload())
            return {"status": "ok"}

        # If a user types a command, try to match it to a response
        # We'll use the interactive payloads for these responses too
        if lc in ALIASES["dwani_intro"] or lc in {"3"}:
            send_interactive_message(from_number, get_dwani_buttons_payload())
            return {"status": "ok"}
        
        if lc in ALIASES["services"] or lc in {"2"}:
            raw_answer = KB.get("services", KB["oos"])
            final_answer = rephrase_with_groq(raw_answer)
            send_text(from_number, final_answer)
            send_interactive_message(from_number, get_contact_button_payload())
            return {"status": "ok"}
        
        if lc in ALIASES["apply"]:
            send_text(from_number, KB["apply"])
            return {"status": "ok"}
        
        # Use a general fallback for text input
        # Note: We're not using route_intent anymore, as we want to push users to buttons.
        # This simplifies the logic to just handle the core commands and then send a default response.
        raw_answer = KB["oos"]
        final_answer = rephrase_with_groq(raw_answer)
        send_text(from_number, final_answer)
        send_interactive_message(from_number, get_main_menu_payload())

    except Exception as e:
        print("Webhook error:", e)

    return {"status": "ok"}


def get_back_to_menu_button_payload():
    """Generates a simple button to go back to the main menu."""
    return {
        "type": "button",
        "body": {
            "text": "Would you like to explore other options?"
        },
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "main_menu", "title": "Main Menu"}},
            ]
        },
        "footer": {
            "text": "Tap the button above."
        }
    }


def get_contact_button_payload():
    """Generates a button to contact the company."""
    return {
        "type": "button",
        "body": {
            "text": "Got a project idea? Let's talk!"
        },
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "contact_us", "title": "Contact Us"}},
                {"type": "reply", "reply": {"id": "main_menu", "title": "Back to Main Menu"}},
            ]
        },
        "footer": {
            "text": "Tap the button to get our contact details."
        }
    }
