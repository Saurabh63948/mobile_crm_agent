import os
import re
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []
    customer: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    reply: str
    action: str = "TALK"
    choices: Optional[List[str]] = None
    data: Optional[Dict] = None
    items: Optional[List[Dict]] = None
    item_type: Optional[str] = None


# ─── Parse search results from hidden history messages ────────────────────────
def update_search_results_from_history(user_id: str, history: List[Dict], sessions: dict):
    """
    Walk history in order. Each time we see a new [SEARCH_RESULTS] block we
    REPLACE the stored results for that type (not append) — this ensures that
    if the user searched contacts, then searched deals, the old contact data
    is still available but a fresh deal search always overwrites old deal data.
    Additionally, if the LAST search type is different from whatever was stored
    before (i.e. user switched modules), we clear ALL other types so the agent
    only reasons over the current module's data.
    """
    last_type_seen = None
    for msg in history:
        if msg.get("role") == "assistant" and msg.get("isHidden"):
            content = msg.get("content", "")
            if content.startswith("[SEARCH_RESULTS]"):
                try:
                    type_match = re.search(r"type=(\w+)", content)
                    data_match = re.search(r"data=(\[.*\])$", content, re.DOTALL)
                    if type_match and data_match:
                        result_type = type_match.group(1)
                        data = json.loads(data_match.group(1))
                        sessions.setdefault(user_id, {}).setdefault("search_results", {})[result_type] = data
                        last_type_seen = result_type
                        print(f"[DEBUG] Stored {len(data)} {result_type} results for user {user_id}")
                except Exception as e:
                    print(f"Error parsing search results: {e}")

    # ── KEY FIX: If the most recent search was a specific type, clear all OTHER
    # types so the agent doesn't mix results from previous module sessions.
    if last_type_seen and user_id in sessions:
        sr = sessions[user_id].get("search_results", {})
        keys_to_delete = [k for k in sr if k != last_type_seen]
        for k in keys_to_delete:
            del sr[k]
        print(f"[DEBUG] Cleared old types {keys_to_delete}, keeping '{last_type_seen}'")


# ─── Field extractors ─────────────────────────────────────────────────────────
def get_name(item):
    return (item.get("contact_full_name") or item.get("full_name") or item.get("name") or
            item.get("deal_name") or item.get("company_name") or
            f"{item.get('first_name', '')} {item.get('last_name', '')}".strip() or "")

def get_email(item):
    return item.get("email") or item.get("contact_email") or ""

def get_phone(item):
    phone = item.get("phone") or item.get("phone_number") or ""
    if not phone and item.get("contact_phone"):
        try:
            parsed = json.loads(item["contact_phone"])
            if isinstance(parsed, list) and parsed:
                phone = parsed[0].get("phone", "")
        except:
            pass
    return phone or ""

def get_company(item):
    return item.get("company_name") or item.get("company") or ""

def get_stage(item):
    return item.get("stage_name") or item.get("pipeline_stage") or ""

def get_id(item):
    return str(item.get("lead_id") or item.get("deal_id") or item.get("company_id") or item.get("id") or "—")

def get_budget(item):
    direct = item.get("budget") or item.get("expected_revenue") or item.get("amount")
    if direct:
        try:
            return float(direct)
        except:
            pass
    ps = item.get("product_services")
    if ps:
        try:
            if isinstance(ps, str):
                ps = json.loads(ps)
            if isinstance(ps, list) and ps:
                total = 0
                for p in ps:
                    budget = float(p.get("budget", 0) or 0)
                    quantity = float(p.get("quantity", 1) or 1)
                    total += budget * quantity
                return total if total > 0 else None
        except:
            pass
    return None

def get_budget_display(item):
    b = get_budget(item)
    if b is not None:
        return f"₹{b:,.0f}"
    return "Not available"

def get_full_details_text(item, typ="lead"):
    lines = []
    name = get_name(item)
    if name: lines.append(f"**Name:** {name}")
    email = get_email(item)
    if email: lines.append(f"**Email:** {email}")
    phone = get_phone(item)
    if phone: lines.append(f"**Phone:** {phone}")
    company = get_company(item)
    if company: lines.append(f"**Company:** {company}")
    stage = get_stage(item)
    if stage: lines.append(f"**Stage:** {stage}")
    status = item.get("lead_status") or item.get("status")
    if status: lines.append(f"**Status:** {status}")
    requirement = item.get("requirement")
    if requirement: lines.append(f"**Requirement:** {requirement}")
    industry = item.get("industry")
    if industry: lines.append(f"**Industry:** {industry}")
    source = item.get("source_title") or item.get("lead_source_name")
    if source: lines.append(f"**Source:** {source}")
    owner = item.get("lead_owner_name") or item.get("contact_owner_name") or item.get("deal_owner_name")
    if owner: lines.append(f"**Owner:** {owner}")
    closure = item.get("expected_closure_date")
    if closure: lines.append(f"**Expected Closure:** {closure}")
    followup = item.get("followup_date")
    if followup: lines.append(f"**Follow-up Date:** {followup}")
    city = item.get("city_name") or item.get("nicename")
    if city: lines.append(f"**Location:** {city}")
    website = item.get("website")
    if website: lines.append(f"**Website:** {website}")
    budget_val = get_budget(item)
    if budget_val is not None:
        lines.append(f"**Total Budget:** ₹{budget_val:,.0f}")
    ps = item.get("product_services")
    if ps:
        try:
            if isinstance(ps, str): ps = json.loads(ps)
            if isinstance(ps, list) and ps:
                prod_lines = []
                for p in ps:
                    pid = p.get("product_id", "")
                    qty = p.get("quantity", "")
                    bud = p.get("budget", "")
                    prod_lines.append(f"Product ID {pid} × Qty {qty} @ ₹{bud} each")
                lines.append(f"**Products:** {' | '.join(prod_lines)}")
        except:
            pass
    return "\n".join(lines) if lines else "No details available."


def all_items_from_session(user_id, sessions):
    search_results = sessions.get(user_id, {}).get("search_results", {})
    items = []
    for typ, lst in search_results.items():
        for item in lst:
            items.append((typ, item))
    return items, search_results


# ─── Fuzzy name matching ──────────────────────────────────────────────────────
def fuzzy_match(query: str, target: str) -> bool:
    q = query.lower().strip()
    t = target.lower().strip()
    if not q or not t: return False
    if q == t: return True
    q_words = [w for w in q.split() if len(w) >= 3]
    t_words = t.split()
    if len(q_words) >= 2:
        return all(any(qw == tw or tw.startswith(qw) for tw in t_words) for qw in q_words)
    if q in t or t in q: return True
    if len(q) >= 4 and (q[:-1] == t or q == t[:-1]): return True
    return False

def find_by_name(query: str, all_items):
    matches = []
    for typ, item in all_items:
        name = get_name(item)
        if fuzzy_match(query, name):
            matches.append((typ, item))
    return matches

def find_by_phone(phone_query: str, all_items):
    """Find items whose phone number contains the given digits."""
    clean = re.sub(r'\D', '', phone_query)
    if len(clean) < 7:
        return []
    matches = []
    for typ, item in all_items:
        p = re.sub(r'\D', '', get_phone(item))
        if clean in p or p in clean:
            matches.append((typ, item))
    return matches

def find_by_email(email_query: str, all_items):
    """Find items whose email matches (case-insensitive)."""
    eq = email_query.lower().strip()
    matches = []
    for typ, item in all_items:
        e = get_email(item).lower()
        if eq and (eq in e or e in eq):
            matches.append((typ, item))
    return matches

# ─── Action mapper ────────────────────────────────────────────────────────────
def action_for_type(typ: str) -> str:
    return {"contact": "SEARCH_CONTACT", "lead": "SEARCH_LEAD",
            "deal": "SEARCH_DEAL", "company": "SEARCH_COMPANY"}.get(typ, "SEARCH_CONTACT")

def items_key_for_type(typ: str) -> str:
    return {"contact": "contacts", "lead": "leads",
            "deal": "deals", "company": "companies"}.get(typ, "contacts")


# ─── Ordinal helpers ──────────────────────────────────────────────────────────
ORDINAL_MAP = {
    "first": 0, "1st": 0, "pehla": 0, "pehle": 0, "pehli": 0, "ek": 0, "1": 0,
    "second": 1, "2nd": 1, "dusra": 1, "dusre": 1, "dusri": 1, "do": 1, "2": 1,
    "third": 2, "3rd": 2, "teesra": 2, "teesre": 2, "teesri": 2, "teen": 2, "3": 2,
    "fourth": 3, "4th": 3, "chautha": 3, "4": 3,
    "fifth": 4, "5th": 4, "paanchwa": 4, "5": 4,
}


# ─── Main Q&A over stored results ─────────────────────────────────────────────
def answer_from_search_results(user_msg: str, user_id: str, sessions: dict) -> Optional[ChatResponse]:
    lower = user_msg.lower().strip()
    all_items, search_results = all_items_from_session(user_id, sessions)

    if not all_items:
        return None

    # ── 0. "show all" / "list all" ────────────────────────────────────────────
    if re.search(r"\b(show all|list all|sab dikhao|all results|sabhi)\b", lower):
        for typ, lst in search_results.items():
            if lst:
                return ChatResponse(
                    reply=f"Showing all {len(lst)} {typ}(s):",
                    action=action_for_type(typ),
                    items=lst,
                    item_type=typ,
                )

    # ── 1. Find by phone number ───────────────────────────────────────────────
    # e.g. "give the contact where phone is 6394855865"
    phone_filter_match = re.search(r'(?:phone|mobile|number)\s+(?:is|=|:)?\s*([\d\s\-\+]{7,})', lower)
    if phone_filter_match:
        phone_q = re.sub(r'\D', '', phone_filter_match.group(1))
        matches = find_by_phone(phone_q, all_items)
        if matches:
            typ, item = matches[0]
            details = get_full_details_text(item, typ)
            return ChatResponse(
                reply=f"Found {get_name(item)} with phone **{get_phone(item)}**:\n{details}",
                action=action_for_type(typ),
                items=[item],
                item_type=typ,
            )
        return ChatResponse(reply=f"No record found with phone number containing **{phone_q}**.", action="TALK")

    # ── 2. Find by email ──────────────────────────────────────────────────────
    # e.g. "give the deal where email is abc@gmail.com"
    email_filter_match = re.search(r'(?:email|mail)\s+(?:is|=|:)?\s*([\w\.\-]+@[\w\.\-]+)', lower)
    if email_filter_match:
        email_q = email_filter_match.group(1).strip()
        matches = find_by_email(email_q, all_items)
        if matches:
            typ, item = matches[0]
            details = get_full_details_text(item, typ)
            return ChatResponse(
                reply=f"Found {get_name(item)} with email **{get_email(item)}**:\n{details}",
                action=action_for_type(typ),
                items=[item],
                item_type=typ,
            )
        return ChatResponse(reply=f"No record found with email **{email_q}**.", action="TALK")

    # ── 3. Detail by ID ───────────────────────────────────────────────────────
    id_match = re.search(r'\b(?:id\s*[:#]?\s*|lead\s+id\s*|deal\s+id\s*|company\s+id\s*)(\d+)\b', lower)
    if id_match:
        rid = id_match.group(1)
        for typ, item in all_items:
            if str(item.get("lead_id")) == rid or str(item.get("deal_id")) == rid or \
               str(item.get("company_id")) == rid or str(item.get("id")) == rid:
                details = get_full_details_text(item, typ)
                return ChatResponse(
                    reply=f"Here are details for ID {rid}:\n{details}",
                    action=action_for_type(typ),
                    items=[item],
                    item_type=typ,
                )
        return ChatResponse(reply=f"No record found with ID {rid}.", action="TALK")

    # ── 4. Ordinal: first/second/third ────────────────────────────────────────
    ord_match = re.search(r'\b(' + '|'.join(ORDINAL_MAP.keys()) + r')\b', lower)
    type_hint = None
    for t in ("lead", "contact", "deal", "company"):
        if t in lower:
            type_hint = t
            break

    if ord_match:
        idx = ORDINAL_MAP[ord_match.group(1)]
        pool = search_results.get(type_hint, []) if type_hint else [i for _, i in all_items]
        typ_for_format = type_hint or (all_items[idx][0] if idx < len(all_items) else "contact")

        if idx < len(pool):
            item = pool[idx]
            if re.search(r"\b(email|mail)\b", lower):
                e = get_email(item)
                return ChatResponse(reply=f"{get_name(item)}'s email is **{e or 'not available'}**.", action="TALK")
            if re.search(r"\b(phone|number|mobile|call)\b", lower):
                p = get_phone(item)
                return ChatResponse(reply=f"{get_name(item)}'s phone is **{p or 'not available'}**.", action="TALK")
            if re.search(r"\b(company|firm)\b", lower):
                c = get_company(item)
                return ChatResponse(reply=f"{get_name(item)} works at **{c or 'unknown'}**.", action="TALK")
            if re.search(r"\b(budget|revenue|amount|kitna|price)\b", lower):
                b = get_budget_display(item)
                return ChatResponse(reply=f"{get_name(item)}'s total budget is **{b}**.", action="TALK")
            details = get_full_details_text(item, typ_for_format)
            return ChatResponse(
                reply=f"Here's the {ord_match.group(1)} result:\n{details}",
                action=action_for_type(typ_for_format),
                items=[item],
                item_type=typ_for_format,
            )
        return ChatResponse(reply="There aren't that many results.", action="TALK")

    # ── 5. "details" / "detail of <name>" ─────────────────────────────────────
    if re.match(r'^details?$', lower.strip()):
        for typ, lst in search_results.items():
            if lst:
                return ChatResponse(
                    reply=f"Here are all {len(lst)} {typ}(s):",
                    action=action_for_type(typ),
                    items=lst[:10],
                    item_type=typ,
                )

    if re.search(r'\b(detail|details|jankari|info|puri info|poori jankari)\b', lower):
        detail_q = re.search(r'(?:details?|info|about|tell me about|batao|jankari)\s+(?:of\s+|about\s+)?(.+?)(?:\?|$)', lower)
        if detail_q:
            name_q = detail_q.group(1).strip()
            name_q = re.sub(r'\b(of|the|this|lead|contact|deal|is|ki|ka|ke|wala|wali)\b', '', name_q).strip()
            if name_q and name_q not in ORDINAL_MAP and len(name_q) > 1:
                matches = find_by_name(name_q, all_items)
                if len(matches) == 1:
                    typ, item = matches[0]
                    details = get_full_details_text(item, typ)
                    return ChatResponse(
                        reply=f"Here are full details for {get_name(item)}:\n{details}",
                        action=action_for_type(typ),
                        items=[item],
                        item_type=typ,
                    )
                elif len(matches) > 1:
                    choices = [f"{get_name(i)} ({t})" for t, i in matches[:5]]
                    return ChatResponse(reply=f"Found {len(matches)} records. Which one?",
                                        action="TALK", choices=choices)
        for typ, lst in search_results.items():
            if lst:
                details_lines = []
                for item in lst[:5]:
                    details_lines.append(get_full_details_text(item, typ))
                return ChatResponse(
                    reply=f"Here are full details for {len(lst)} {typ}(s):\n\n" + "\n\n---\n\n".join(details_lines),
                    action=action_for_type(typ),
                    items=lst[:10],
                    item_type=typ,
                )

    # ── 6. Email of <name> ────────────────────────────────────────────────────
    email_q = re.search(r'(?:email|mail|e-mail)\s+(?:of\s+)?(.+?)(?:\?|$)', lower) or \
              re.search(r'(.+?)\s*(?:ka\s+)?(?:email|mail|e-mail)(?:\s+kya|batao|\?|$)', lower)
    if email_q:
        name_q = email_q.group(1).strip()
        name_q = re.sub(r'\b(of|the|is|ki|ka|ke|kya|batao)\b', '', name_q).strip()
        if name_q and len(name_q) > 1:
            matches = find_by_name(name_q, all_items)
            if matches:
                typ, item = matches[0]
                e = get_email(item)
                return ChatResponse(reply=f"{get_name(item)}'s email is **{e or 'not available'}**.", action="TALK")
            # No name match — show all emails
            emails_list = [f"**{get_name(i)}**: {get_email(i) or 'not available'}" for _, i in all_items[:10]]
            return ChatResponse(reply="Here are all emails:\n" + "\n".join(emails_list), action="TALK")

    # ── 7. Phone of <name> ────────────────────────────────────────────────────
    phone_q = re.search(r'(?:phone|number|mobile|contact)\s+(?:no\.?\s+)?(?:of\s+)?(.+?)(?:\?|$)', lower) or \
              re.search(r'(.+?)\s*(?:ka\s+)?(?:phone|number|mobile)(?:\s+kya|batao|\?|$)', lower)
    if phone_q:
        name_q = phone_q.group(1).strip()
        name_q = re.sub(r'\b(of|the|is|ki|ka|ke|kya|batao|no)\b', '', name_q).strip()
        if name_q and name_q not in ORDINAL_MAP and len(name_q) > 1:
            matches = find_by_name(name_q, all_items)
            if matches:
                typ, item = matches[0]
                p = get_phone(item)
                return ChatResponse(reply=f"{get_name(item)}'s phone is **{p or 'not available'}**.", action="TALK")
            # No name match — show all phones
            phone_list = [f"**{get_name(i)}**: {get_phone(i) or 'not available'}" for _, i in all_items[:10]]
            return ChatResponse(reply="Here are all phone numbers:\n" + "\n".join(phone_list), action="TALK")

    # ── 8. Company of <name> ──────────────────────────────────────────────────
    company_q = re.search(r'(?:company|firm)\s+(?:of\s+)?(.+?)(?:\?|$)', lower) or \
                re.search(r'(.+?)\s*(?:ki?\s+)?(?:company|firm)(?:\s+kya|batao|\?|$)', lower)
    if company_q:
        name_q = company_q.group(1).strip()
        name_q = re.sub(r'\b(of|the|is|ki|ka|ke)\b', '', name_q).strip()
        if name_q and len(name_q) > 1:
            matches = find_by_name(name_q, all_items)
            if matches:
                typ, item = matches[0]
                c = get_company(item)
                return ChatResponse(reply=f"{get_name(item)} works at **{c or 'not available'}**.", action="TALK")

    # ── 9. Budget / revenue queries ───────────────────────────────────────────
    if re.search(r'\b(budget|revenue|amount|value|kitna|price|total budget|kitna budget)\b', lower):
        budget_name_q = re.search(r'(?:budget|revenue|amount)\s+(?:of\s+)?(.+?)(?:\?|$)', lower) or \
                        re.search(r'(.+?)\s*(?:ka\s+)?(?:budget|revenue|amount)(?:\s+kya|batao|\?|$)', lower)
        if budget_name_q:
            name_q = budget_name_q.group(1).strip()
            name_q = re.sub(r'\b(of|the|is|ki|ka|ke)\b', '', name_q).strip()
            if name_q and name_q not in ORDINAL_MAP and len(name_q) > 1:
                matches = find_by_name(name_q, all_items)
                if matches:
                    typ, item = matches[0]
                    b = get_budget_display(item)
                    return ChatResponse(reply=f"{get_name(item)}'s total budget is **{b}**.", action="TALK")
        results = []
        for typ, item in all_items:
            name = get_name(item)
            b = get_budget_display(item)
            results.append(f"**{name}**: {b}")
        if results:
            return ChatResponse(reply="Budget summary:\n" + "\n".join(results), action="TALK")

    # ── 10. Specific field queries ─────────────────────────────────────────────
    if re.search(r'\b(status|stage|owner|requirement|industry|source|closure|followup|location|city|website)\b', lower):
        # Check if a name is mentioned to narrow down
        field_name_match = re.search(r'(?:of\s+|about\s+)?([A-Za-z]{3,}(?:\s+[A-Za-z]{3,})?)\s+(?:ka\s+)?(?:status|stage|owner|requirement|industry|source|closure|followup|location|city|website)', lower) or \
                           re.search(r'(?:status|stage|owner|requirement|industry|source|closure|followup|location|city|website)\s+(?:of\s+)?([A-Za-z]{3,}(?:\s+[A-Za-z]{3,})?)', lower)
        target_item = None
        if field_name_match:
            name_q = field_name_match.group(1).strip()
            matches = find_by_name(name_q, all_items)
            if matches:
                _, target_item = matches[0]
        if not target_item and all_items:
            _, target_item = all_items[0]

        if target_item:
            name = get_name(target_item)
            if re.search(r'\b(status)\b', lower):
                val = target_item.get("lead_status") or target_item.get("status") or "Not available"
                return ChatResponse(reply=f"{name}'s status is **{val}**.", action="TALK")
            if re.search(r'\b(stage)\b', lower):
                val = get_stage(target_item) or "Not available"
                return ChatResponse(reply=f"{name}'s stage is **{val}**.", action="TALK")
            if re.search(r'\b(owner)\b', lower):
                val = target_item.get("lead_owner_name") or target_item.get("contact_owner_name") or target_item.get("deal_owner_name") or "Not available"
                return ChatResponse(reply=f"{name}'s owner is **{val}**.", action="TALK")
            if re.search(r'\b(requirement)\b', lower):
                val = target_item.get("requirement") or "Not available"
                return ChatResponse(reply=f"{name}'s requirement is **{val}**.", action="TALK")
            if re.search(r'\b(industry)\b', lower):
                val = target_item.get("industry") or "Not available"
                return ChatResponse(reply=f"{name}'s industry is **{val}**.", action="TALK")
            if re.search(r'\b(source)\b', lower):
                val = target_item.get("source_title") or "Not available"
                return ChatResponse(reply=f"{name}'s lead source is **{val}**.", action="TALK")
            if re.search(r'\b(closure|expected closure)\b', lower):
                val = target_item.get("expected_closure_date") or "Not available"
                return ChatResponse(reply=f"{name}'s expected closure date is **{val}**.", action="TALK")
            if re.search(r'\b(followup|follow.?up)\b', lower):
                val = target_item.get("followup_date") or "Not available"
                return ChatResponse(reply=f"{name}'s follow-up date is **{val}**.", action="TALK")
            if re.search(r'\b(location|city)\b', lower):
                val = target_item.get("city_name") or target_item.get("nicename") or "Not available"
                return ChatResponse(reply=f"{name}'s location is **{val}**.", action="TALK")
            if re.search(r'\b(website)\b', lower):
                val = target_item.get("website") or "Not available"
                return ChatResponse(reply=f"{name}'s website is **{val}**.", action="TALK")

    # ── 11. Count query ────────────────────────────────────────────────────────
    if re.search(r'\b(kitne|how many|count|total)\b', lower):
        parts = [f"{len(lst)} {typ}(s)" for typ, lst in search_results.items()]
        return ChatResponse(reply="I have: " + ", ".join(parts) + " in memory.", action="TALK")

    # ── 12. Generic name typed → show full detail card ─────────────────────────
    if len(lower.split()) <= 4 and not re.search(r'\b(search|find|call|dial|hey|hi|hello|stop|quit|cancel)\b', lower):
        matches = find_by_name(lower, all_items)
        if len(matches) == 1:
            typ, item = matches[0]
            details = get_full_details_text(item, typ)
            return ChatResponse(
                reply=f"Here are details for {get_name(item)}:\n{details}",
                action=action_for_type(typ),
                items=[item],
                item_type=typ,
            )
        elif len(matches) > 1:
            choices = [f"{get_name(i)} ({t})" for t, i in matches[:5]]
            return ChatResponse(reply=f"Found {len(matches)} people matching. Which one?",
                                action="TALK", choices=choices)

    return None


# ─── Call handling ────────────────────────────────────────────────────────────
def handle_call_from_stored_results(user_msg: str, user_id: str, sessions: dict) -> Optional[ChatResponse]:
    lower = user_msg.lower().strip()
    if not re.search(r"\b(call|dial|phone|ring)\b", lower):
        return None

    all_items, _ = all_items_from_session(user_id, sessions)

    name_match = re.search(r'(?:call|dial|phone|ring)\s+(?:on\s+)?(?:this\s+)?(.+?)(?:\?|$)', lower)

    if name_match:
        name_q = name_match.group(1).strip()
        name_q = re.sub(r'\b(on|this|the|number|please|ko|use|wala)\b', '', name_q).strip()

        ord_check = re.search(r'\b(' + '|'.join(ORDINAL_MAP.keys()) + r')\b', name_q)
        if ord_check or name_q in ORDINAL_MAP:
            key = ord_check.group(1) if ord_check else name_q
            idx = ORDINAL_MAP.get(key, 0)
            pool = [i for _, i in all_items]
            if idx < len(pool):
                item = pool[idx]
                phone = get_phone(item)
                name = get_name(item)
                if phone:
                    sessions.setdefault(user_id, {})["last_call_made"] = {"name": name, "phone": phone}
                    return ChatResponse(reply=f"📞 Calling {name} at {phone}...",
                                        action="MAKE_CALL", data={"phone": phone, "name": name})
                return ChatResponse(reply=f"No phone number for {name}.", action="TALK")

        if name_q:
            matches = find_by_name(name_q, all_items)
            if len(matches) == 1:
                typ, item = matches[0]
                phone = get_phone(item)
                name = get_name(item)
                if phone:
                    sessions.setdefault(user_id, {})["last_call_made"] = {"name": name, "phone": phone}
                    return ChatResponse(reply=f"📞 Calling {name} at {phone}...",
                                        action="MAKE_CALL", data={"phone": phone, "name": name})
                return ChatResponse(reply=f"No phone number for {name}.", action="TALK")
            elif len(matches) > 1:
                choices = [f"{get_name(i)} — {get_phone(i) or 'no phone'}" for _, i in matches[:5]]
                return ChatResponse(reply=f"Multiple matches for '{name_q}'. Which one to call?",
                                    action="TALK", choices=choices)

    if all_items:
        typ, item = all_items[0]
        phone = get_phone(item)
        name = get_name(item)
        if phone:
            sessions.setdefault(user_id, {})["last_call_made"] = {"name": name, "phone": phone}
            return ChatResponse(reply=f"📞 Calling {name} at {phone}...",
                                action="MAKE_CALL", data={"phone": phone, "name": name})
        return ChatResponse(reply=f"No phone number for {name}.", action="TALK")

    return None


def handle_call_status(user_msg: str, user_id: str, sessions: dict) -> Optional[ChatResponse]:
    lower = user_msg.lower().strip()
    if re.search(r"\b(call done|call finish|call complete|call khatam|haan done)\b", lower):
        last_call = sessions.get(user_id, {}).get("last_call_made")
        if last_call:
            sessions[user_id].pop("last_call_made", None)
            return ChatResponse(reply=f"✅ Call with {last_call['name']} completed. What next?",
                                action="TALK",
                                choices=["Search Lead", "Search Contact", "Search Deal", "Search Company"])
        return ChatResponse(reply="No ongoing call found. Want to call someone?", action="TALK")
    return None


# ─── General Q&A ─────────────────────────────────────────────────────────────
def answer_general_query(user_msg: str) -> Optional[str]:
    lower = user_msg.lower().strip()
    if re.search(r"\b(what is crm|crm kya)\b", lower):
        return "CRM = Customer Relationship Management. I help you search leads, contacts, deals, and companies."
    if re.search(r"\b(who are you|tum kaun|aap kaun|your name|qubie)\b", lower):
        return "I'm qubie 👋 your CRM search assistant!"
    if re.search(r"\b(what can you do|kya kar sakte|capabilities|features)\b", lower):
        return ("I can search contacts, leads, deals, companies. After searching, you can ask:\n"
                "• Email of <name> • Phone of <name> • Budget of <name>\n"
                "• Where phone is <number> • Where email is <address>\n"
                "• Details of <name> • Call <name>")
    if re.search(r"\b(help|kaise|how to use)\b", lower):
        return ("Say 'search contact', 'search lead', 'search deal', or 'search company'.\n"
                "Then ask things like:\n"
                "• 'email of Rahul' • 'phone of Sara'\n"
                "• 'give the lead where phone is 9876543210'\n"
                "• 'give the contact where email is abc@gmail.com'\n"
                "• 'details of Priya' • 'call Vikram'")
    if re.search(r"\b(hi|hello|hey|namaste|hlo|hii)\b", lower):
        return "Hello! 👋 I'm qubie. What would you like to search today?"
    return None


# ─── Main endpoint ────────────────────────────────────────────────────────────
@app.post("/agent/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    user_msg = req.message.strip()
    user_id = "anonymous"
    if req.customer and isinstance(req.customer, dict):
        data_list = req.customer.get("data")
        if isinstance(data_list, list) and data_list:
            cust = data_list[0]
        else:
            cust = req.customer.get("customer_details") or req.customer
        user_id = str(cust.get("id", "anonymous"))

    print(f"[DEBUG] user={user_id} msg='{user_msg}'")
    update_search_results_from_history(user_id, req.history, sessions)

    _, search_results = all_items_from_session(user_id, sessions)
    print(f"[DEBUG] stored: { {k: len(v) for k, v in search_results.items()} }")

    call_status = handle_call_status(user_msg, user_id, sessions)
    if call_status:
        return call_status

    search_answer = answer_from_search_results(user_msg, user_id, sessions)
    if search_answer:
        return search_answer

    call_response = handle_call_from_stored_results(user_msg, user_id, sessions)
    if call_response:
        return call_response

    general = answer_general_query(user_msg)
    if general:
        return ChatResponse(reply=general, action="TALK",
                            choices=["Search Lead", "Search Contact", "Search Deal", "Search Company"])

    if sessions.get(user_id, {}).get("search_results"):
        all_items, _ = all_items_from_session(user_id, sessions)
        names = [get_name(i) for _, i in all_items[:3]]
        return ChatResponse(
            reply=f"I have {len(all_items)} result(s) in memory ({', '.join(names)}). "
                  f"Ask for email, phone, budget, details — or say 'call <name>' or 'where phone is <number>'.",
            action="TALK"
        )

    return ChatResponse(
        reply="I'm qubie 🤖 Say 'search lead', 'search contact', 'search deal', or 'search company' to begin.",
        action="TALK",
        choices=["Search Lead", "Search Contact", "Search Deal", "Search Company"]
    )