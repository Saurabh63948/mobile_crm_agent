from state_manager import get_session

LEAD_FIELDS = [
    ("contact_name", "Please select the contact name from the list below:", "dropdown_contact"),
    ("pipeline", "Which pipeline does this lead belong to?", "dropdown_pipeline"),
    ("pipeline_stage", "Select the pipeline stage:", "dropdown_stage"),
    ("product_service", "Enter the product or service name:", "text"),
    ("budget", "What is the estimated budget? (numeric)", "number"),
    ("lead_source", "Where did this lead come from? (e.g., website, referral)", "text"),
    ("feedback_requirement", "Any feedback or special requirements?", "text")
]

def handle_create_deal(user_id: str, user_message: str, available_contacts: list, pipelines: list, stages_map: dict):
    session = get_session(user_id)
    if session["flow"] != "create_lead":
        # Start new lead creation
        session["flow"] = "create_lead"
        session["step"] = 0
        session["data"] = {}
        session["temp"]["contacts"] = available_contacts
        session["temp"]["pipelines"] = pipelines
        session["temp"]["stages_map"] = stages_map  # {pipeline_id: [stages]}
        field_name, prompt, field_type = LEAD_FIELDS[0]
        if field_type == "dropdown_contact":
            choices = [c["contact_full_name"] for c in available_contacts[:5]]
            return {"reply": prompt, "action": "TALK", "choices": choices, "field": field_name}
        else:
            return {"reply": prompt, "action": "TALK"}
    
    # Continue existing flow
    step = session["step"]
    field_name, prompt, field_type = LEAD_FIELDS[step]
    
    # Store the answer
    if field_type == "dropdown_contact":
        selected_name = user_message.strip()
        selected_contact = next((c for c in session["temp"]["contacts"] if c["contact_full_name"] == selected_name), None)
        if not selected_contact:
            return {"reply": f"Contact '{selected_name}' not found. Please choose from the list.", "action": "TALK", "choices": [c["contact_full_name"] for c in session["temp"]["contacts"][:5]]}
        session["data"]["contact_id"] = selected_contact["id"]
        session["data"]["contact_name"] = selected_name
    elif field_type == "dropdown_pipeline":
        selected_pipeline = next((p for p in session["temp"]["pipelines"] if p["pipeline_name"] == user_message.strip()), None)
        if not selected_pipeline:
            return {"reply": "Please select a valid pipeline from the list.", "action": "TALK", "choices": [p["pipeline_name"] for p in session["temp"]["pipelines"]]}
        session["data"]["pipeline_id"] = selected_pipeline["id"]
        session["data"]["pipeline_name"] = selected_pipeline["pipeline_name"]
        # Store stages for next step
        session["temp"]["current_stages"] = session["temp"]["stages_map"].get(selected_pipeline["id"], [])
    elif field_type == "dropdown_stage":
        if user_message.strip() not in session["temp"]["current_stages"]:
            return {"reply": f"Stage '{user_message}' invalid. Choose from: {', '.join(session['temp']['current_stages'])}", "action": "TALK", "choices": session["temp"]["current_stages"]}
        session["data"]["stage"] = user_message.strip()
    elif field_type == "number":
        try:
            session["data"][field_name] = float(user_message)
        except ValueError:
            return {"reply": "Please enter a valid number for budget.", "action": "TALK"}
    else:
        session["data"][field_name] = user_message.strip()
    
    # Move to next step
    session["step"] += 1
    if session["step"] >= len(LEAD_FIELDS):
        # All fields collected
        reset_session(user_id)  # clear flow state
        return {
            "reply": "All lead details collected. Do you want to submit?",
            "action": "SUBMIT_CREATE_LEAD",
            "data": session["data"]
        }
    
    # Ask next question
    next_field, next_prompt, next_type = LEAD_FIELDS[session["step"]]
    if next_type == "dropdown_pipeline":
        choices = [p["pipeline_name"] for p in session["temp"]["pipelines"]]
        return {"reply": next_prompt, "action": "TALK", "choices": choices, "field": next_field}
    elif next_type == "dropdown_stage":
        choices = session["temp"]["current_stages"]
        return {"reply": next_prompt, "action": "TALK", "choices": choices, "field": next_field}
    elif next_type == "dropdown_contact":
        choices = [c["contact_full_name"] for c in session["temp"]["contacts"][:5]]
        return {"reply": next_prompt, "action": "TALK", "choices": choices, "field": next_field}
    else:
        return {"reply": next_prompt, "action": "TALK", "field": next_field}