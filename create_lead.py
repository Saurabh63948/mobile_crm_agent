# create_lead.py
from typing import List, Dict, Any, Optional

# Field order and metadata
LEAD_FIELDS = [
    {"field": "contact", "prompt": "Please tell me the contact name.", "type": "dropdown", "options_key": "contacts", "label": "Contact Name"},
    {"field": "pipeline", "prompt": "Which pipeline should this lead go to?", "type": "dropdown", "options_key": "pipelines", "label": "Pipeline"},
    {"field": "pipeline_stage", "prompt": "Select the pipeline stage.", "type": "dropdown", "options_key": "stages", "label": "Pipeline Stage", "depends_on": "pipeline"},
    {"field": "requirement", "prompt": "What is the requirement?", "type": "text", "label": "Requirement"},
    {"field": "product", "prompt": "Select the product or service.", "type": "dropdown", "options_key": "products", "label": "Product"},
    {"field": "quantity", "prompt": "What is the quantity?", "type": "number", "label": "Quantity"},
    {"field": "budget", "prompt": "What is the estimated budget (₹)?", "type": "number", "label": "Budget"},
    {"field": "lead_source", "prompt": "Where did this lead come from?", "type": "dropdown", "options_key": "lead_sources", "label": "Lead Source"},
    {"field": "feedback", "prompt": "Any additional feedback or comments?", "type": "text", "label": "Feedback", "optional": True}
]

# Dummy data (used when frontend doesn't provide real lists)
DUMMY_CONTACTS = [
    {"id": 1, "contact_full_name": "Rahul Sharma", "phone": "9876543210", "email": "rahul@example.com"},
    {"id": 2, "contact_full_name": "Priya Mehta", "phone": "9876501234", "email": "priya@example.com"},
    {"id": 3, "contact_full_name": "Amit Kumar", "phone": "9812345678", "email": "amit@example.com"},
    {"id": 4, "contact_full_name": "Neha Gupta", "phone": "9876512345", "email": "neha@example.com"},
    {"id": 5, "contact_full_name": "Suresh Reddy", "phone": "9988776655", "email": "suresh@example.com"},
    {"id": 6, "contact_full_name": "Anjali Nair", "phone": "9876543211", "email": "anjali@example.com"},
]

DUMMY_PIPELINES = [
    {"id": 1, "pipeline_name": "Sales Funnel", "stages": ["New", "Contacted", "Qualified", "Proposal", "Closed Won"]},
    {"id": 102, "pipeline_name": "Partner Leads", "stages": ["Inquiry", "Meeting Scheduled", "Negotiation", "Closed"]},
    {"id": 103, "pipeline_name": "Enterprise", "stages": ["Initial Contact", "Demo", "Proposal", "Contract"]},
]

DUMMY_PRODUCTS = [
    {"id": 1, "label": "CRM Software - Basic"},
    {"id": 202, "label": "CRM Software - Pro"},
    {"id": 203, "label": "Custom Development"},
    {"id": 204, "label": "Implementation Service"},
]

DUMMY_LEAD_SOURCES = [
    {"id": 1, "label": "Website"},
    {"id": 302, "label": "Referral"},
    {"id": 303, "label": "LinkedIn"},
    {"id": 304, "label": "Google Ads"},
]

# Cancellation keywords
CANCEL_KEYWORDS = ["exit", "quit", "cancel", "stop", "nevermind", "never mind", "forget it", "abort", "back", "go back", "start over"]

def is_cancellation(text: str) -> bool:
    lower = text.lower().strip()
    return any(kw in lower for kw in CANCEL_KEYWORDS)

def get_available_contacts(req_contacts):
    return req_contacts if req_contacts else DUMMY_CONTACTS

def get_available_pipelines(req_pipelines):
    return req_pipelines if req_pipelines else DUMMY_PIPELINES

def get_stages_for_pipeline(pipeline_id, req_stages_map, req_pipelines):
    if req_stages_map and pipeline_id in req_stages_map:
        return req_stages_map[pipeline_id]
    for p in (req_pipelines if req_pipelines else DUMMY_PIPELINES):
        if p.get("id") == pipeline_id:
            return p.get("stages", [])
    return ["New", "Contacted", "Qualified", "Proposal"]

def get_available_products():
    return DUMMY_PRODUCTS

def get_available_lead_sources():
    return DUMMY_LEAD_SOURCES

def handle_create_lead(user_id: str, user_message: str, sessions: dict, req_contacts, req_pipelines, req_stages_map):
    session = sessions.get(user_id)
    lower_msg = user_message.strip().lower()

    # --- Check for cancellation at any point ---
    if session and session.get("flow") == "create_lead" and is_cancellation(user_message):
        del sessions[user_id]
        return {
            "reply": "Sure, no problem! I've cancelled the lead creation. What would you like to do next? 😊",
            "action": "TALK",
            "choices": ["Create Lead", "Create Contact", "Create Deal", "Search Contact", "Search Lead"]
        }

    # Start new lead creation
    if not session or session.get("flow") != "create_lead":
        sessions[user_id] = {
            "flow": "create_lead",
            "step": 0,
            "data": {},
            "temp": {
                "contacts": get_available_contacts(req_contacts),
                "pipelines": get_available_pipelines(req_pipelines),
                "stages_map": req_stages_map or {},
                "products": get_available_products(),
                "lead_sources": get_available_lead_sources(),
            }
        }
        session = sessions[user_id]
        field_info = LEAD_FIELDS[0]
        choices = [c["contact_full_name"] for c in session["temp"]["contacts"][:5]]
        return {
            "reply": "Alright, let's create a new lead! " + field_info["prompt"],
            "action": "TALK",
            "choices": choices,
            "field": field_info["field"]
        }

    # Continue existing flow
    step = session["step"]
    if step >= len(LEAD_FIELDS):
        if "confirm" not in session:
            session["confirm"] = True
            return {
                "reply": "Perfect! I've got all the details. Shall I go ahead and create this lead? (Yes/No)",
                "action": "TALK",
                "choices": ["Yes", "No"]
            }
        else:
            if "yes" in lower_msg:
                lead_data = session["data"]
                del sessions[user_id]
                return {
                    "reply": "✅ Lead created successfully! Great job! What would you like to do next?",
                    "action": "SUBMIT_CREATE_LEAD",
                    "data": lead_data
                }
            else:
                del sessions[user_id]
                return {
                    "reply": "Okay, no worries. I've cancelled the lead creation. How can I assist you now?",
                    "action": "TALK",
                    "choices": ["Create Lead", "Create Contact", "Create Deal", "Search Contact", "Search Lead"]
                }

    field_info = LEAD_FIELDS[step]
    field = field_info["field"]
    field_type = field_info["type"]
    optional = field_info.get("optional", False)

    # Handle "skip" for optional fields
    if optional and lower_msg in ["skip", "koi nahi", "no", "not now"]:
        session["data"][field] = None
        session["step"] += 1
        return ask_next_field(session, step+1)

    # Validate and store answer
    if field_type == "dropdown":
        if field == "contact":
            options = session["temp"]["contacts"]
            matched = None
            for opt in options:
                if opt["contact_full_name"].lower() == lower_msg:
                    matched = opt
                    break
            if not matched:
                for opt in options:
                    if lower_msg in opt["contact_full_name"].lower():
                        matched = opt
                        break
            if not matched:
                choices = [c["contact_full_name"] for c in options[:5]]
                return {
                    "reply": f"Hmm, I couldn't find '{user_message}' in my contacts. Could you please pick one from these?",
                    "action": "TALK",
                    "choices": choices,
                    "field": field
                }
            session["data"][field] = {"id": matched["id"], "name": matched["contact_full_name"]}
        elif field == "pipeline":
            options = session["temp"]["pipelines"]
            matched = None
            for opt in options:
                if opt["pipeline_name"].lower() == lower_msg:
                    matched = opt
                    break
            if not matched:
                choices = [p["pipeline_name"] for p in options[:5]]
                return {
                    "reply": f"Sorry, '{user_message}' is not a valid pipeline. Here are the options:",
                    "action": "TALK",
                    "choices": choices,
                    "field": field
                }
            session["data"][field] = {"id": matched["id"], "name": matched["pipeline_name"]}
            session["temp"]["selected_pipeline_id"] = matched["id"]
        elif field == "pipeline_stage":
            pipeline_id = session["temp"].get("selected_pipeline_id")
            stages = get_stages_for_pipeline(pipeline_id, session["temp"]["stages_map"], session["temp"]["pipelines"])
            if lower_msg not in [s.lower() for s in stages]:
                return {
                    "reply": f"That stage isn't available. Please choose from: {', '.join(stages[:5])}",
                    "action": "TALK",
                    "choices": stages[:5],
                    "field": field
                }
            session["data"][field] = user_message.strip()
        elif field == "product":
            options = session["temp"]["products"]
            matched = None
            for opt in options:
                if opt["label"].lower() == lower_msg:
                    matched = opt
                    break
            if not matched:
                choices = [p["label"] for p in options[:5]]
                return {
                    "reply": f"Product '{user_message}' not found. Please select from these:",
                    "action": "TALK",
                    "choices": choices,
                    "field": field
                }
            session["data"][field] = {"id": matched["id"], "name": matched["label"]}
        elif field == "lead_source":
            options = session["temp"]["lead_sources"]
            matched = None
            for opt in options:
                if opt["label"].lower() == lower_msg:
                    matched = opt
                    break
            if not matched:
                choices = [s["label"] for s in options[:5]]
                return {
                    "reply": f"Lead source '{user_message}' not found. Choose from:",
                    "action": "TALK",
                    "choices": choices,
                    "field": field
                }
            session["data"][field] = {"id": matched["id"], "name": matched["label"]}
    else:
        if field_type == "number":
            try:
                val = float(user_message)
                session["data"][field] = val
            except:
                return {
                    "reply": f"Please enter a valid number for {field_info['label']}.",
                    "action": "TALK",
                    "field": field
                }
        else:
            session["data"][field] = user_message.strip()

    session["step"] += 1
    return ask_next_field(session, session["step"])

def ask_next_field(session, next_step):
    if next_step >= len(LEAD_FIELDS):
        return {
            "reply": "Wonderful! All details collected. Ready to submit? (Yes/No)",
            "action": "TALK",
            "choices": ["Yes", "No"]
        }
    field_info = LEAD_FIELDS[next_step]
    field = field_info["field"]
    field_type = field_info["type"]

    # Warm, natural prompts
    warm_prompts = {
        "contact": "Great, thanks! Now, please tell me the contact name.",
        "pipeline": "Awesome! Which pipeline should this lead go to?",
        "pipeline_stage": "Got it. Now select the pipeline stage.",
        "requirement": "What's the requirement?",
        "product": "Which product or service are they interested in?",
        "quantity": "What quantity are we talking about?",
        "budget": "What's the estimated budget in rupees?",
        "lead_source": "Where did this lead come from?",
        "feedback": "Any additional feedback or comments? (You can say 'skip' if none)"
    }
    actual_prompt = warm_prompts.get(field, field_info["prompt"])

    if field_type == "dropdown":
        if field == "contact":
            choices = [c["contact_full_name"] for c in session["temp"]["contacts"][:5]]
        elif field == "pipeline":
            choices = [p["pipeline_name"] for p in session["temp"]["pipelines"][:5]]
        elif field == "pipeline_stage":
            pipeline_id = session["temp"].get("selected_pipeline_id")
            stages = get_stages_for_pipeline(pipeline_id, session["temp"]["stages_map"], session["temp"]["pipelines"])
            choices = stages[:5]
        elif field == "product":
            choices = [p["label"] for p in session["temp"]["products"][:5]]
        elif field == "lead_source":
            choices = [s["label"] for s in session["temp"]["lead_sources"][:5]]
        else:
            choices = []
        return {
            "reply": actual_prompt,
            "action": "TALK",
            "choices": choices,
            "field": field
        }
    else:
        return {
            "reply": actual_prompt,
            "action": "TALK",
            "field": field
        }