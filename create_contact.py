from state_manager import get_session, reset_session

CONTACT_FIELDS = [
    ("full_name", "Enter the contact's full name:", "text"),
    ("email", "Enter email address:", "email"),
    ("phone", "Enter phone number:", "phone"),
    ("company_name", "Company name (optional):", "text_optional")
]

def handle_create_contact(user_id: str, user_message: str):
    session = get_session(user_id)
    if session["flow"] != "create_contact":
        session["flow"] = "create_contact"
        session["step"] = 0
        session["data"] = {}
        return {"reply": CONTACT_FIELDS[0][1], "action": "TALK"}
    
    step = session["step"]
    field_name, prompt, field_type = CONTACT_FIELDS[step]
    
    # Store
    if field_type == "email" and "@" not in user_message:
        return {"reply": "Please enter a valid email address.", "action": "TALK"}
    session["data"][field_name] = user_message.strip()
    
    session["step"] += 1
    if session["step"] >= len(CONTACT_FIELDS):
        reset_session(user_id)
        return {
            "reply": "Contact details complete. Submit?",
            "action": "SUBMIT_CREATE_CONTACT",
            "data": session["data"]
        }
    
    next_field, next_prompt, _ = CONTACT_FIELDS[session["step"]]
    return {"reply": next_prompt, "action": "TALK", "field": next_field}