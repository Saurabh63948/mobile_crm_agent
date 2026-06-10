import re

def extract_phone_number(text: str) -> str | None:
    match = re.search(r'[\+]?[0-9\s\-\(\)]{8,20}', text)
    return match.group(0).strip() if match else None

def extract_email(text: str) -> str | None:
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else None