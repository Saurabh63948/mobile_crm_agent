from typing import Dict, Any

sessions: Dict[str, Dict[str, Any]] = {}

def get_session(user_id: str) -> dict:
    if user_id not in sessions:
        sessions[user_id] = {
            "flow": None,
            "step": None,
            "data": {},
            "temp": {},
            "search_results": {}  
        }
    return sessions[user_id]    

def reset_session(user_id: str):
    sessions[user_id] = {
        "flow": None,
        "step": None,
        "data": {},
        "temp": {}
    }

