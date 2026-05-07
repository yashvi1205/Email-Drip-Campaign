from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.integrations.google_sheets import (
    get_enhanced_profile_data,
    get_latest_post_for_profile,
    get_profile_urls,
)
from app.repositories.leads_repository import (
    get_latest_interaction_summary_event,
)
from database.db import SessionLocal
from database.models import Lead

logger = logging.getLogger("profiles")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROFILES_FILE = os.path.join(PROJECT_ROOT, "profiles.txt")
LAST_POSTS_FILE = os.path.join(PROJECT_ROOT, "last_posts.json")


def read_profiles() -> List[str]:
    try:
        profiles = get_profile_urls("Profiles")
        if profiles:
            return profiles
    except Exception:
        logger.exception("Error fetching profiles from Google Sheets in API.")

    if not os.path.exists(PROFILES_FILE):
        return []
    with open(PROFILES_FILE, "r") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


def load_last_posts() -> dict:
    if not os.path.exists(LAST_POSTS_FILE):
        return {}
    with open(LAST_POSTS_FILE, "r") as f:
        return json.load(f)


def save_last_posts(data: dict) -> None:
    with open(LAST_POSTS_FILE, "w") as f:
        json.dump(data, f, indent=4)


def list_profiles_clean() -> List[Dict[str, Any]]:
    profiles = read_profiles()
    last_posts = load_last_posts()
    updated = False

    result: List[Dict[str, Any]] = []
    for url in profiles:
        username = (
            url.split("/in/")[1].split("/")[0].replace("-", " ").title()
            if "/in/" in url
            else url
        )
        entry = last_posts.get(url)

        if not entry or (isinstance(entry, str) and entry == "No activity tracked yet"):
            sheet_entry = get_latest_post_for_profile(url)
            if sheet_entry:
                entry = sheet_entry
                last_posts[url] = entry
                updated = True
            else:
                entry = "No activity tracked yet"

        if isinstance(entry, dict):
            post_text = entry.get("text", "No text found")
            photo_url = entry.get("photo_url", "")
            post_time = entry.get("post_time", "")
            is_repost = entry.get("is_repost", False)
            reposter_name = entry.get("reposter_name", "")
            reposter_photo = entry.get("reposter_photo", "")
            original_author_name = entry.get("original_author_name", "")
            stats = {
                "likes": entry.get("likes", 0),
                "comments": entry.get("comments", 0),
                "reposts": entry.get("reposts", 0),
            }
        else:
            post_text = entry
            photo_url = ""
            post_time = ""
            is_repost = False
            reposter_name = ""
            reposter_photo = ""
            original_author_name = ""
            stats = {"likes": 0, "comments": 0, "reposts": 0}

        headline = entry.get("headline", "") if isinstance(entry, dict) else ""
        about = entry.get("about", "") if isinstance(entry, dict) else ""
        work_description = entry.get("work_description", "") if isinstance(entry, dict) else ""
        company = entry.get("company", "") if isinstance(entry, dict) else ""
        role = entry.get("role", "") if isinstance(entry, dict) else ""
        email = entry.get("email", "") if isinstance(entry, dict) else ""

        if not about or not role:
            enhanced = get_enhanced_profile_data(url)
            if enhanced:
                role = role or enhanced.get("role")
                company = company or enhanced.get("company")
                headline = headline or enhanced.get("headline")
                about = about or enhanced.get("about")
                work_description = work_description or enhanced.get("work_description")
                email = email or enhanced.get("email")

        db = SessionLocal()
        lead = db.query(Lead).filter(Lead.linkedin_url == url).first()
        db.close()

        p_data: Dict[str, Any] = {
            "url": url,
            "name": lead.name if lead else username,
            "headline": headline,
            "company": company,
            "role": role,
            "about": about,
            "work_description": work_description,
            "recent_activity": [],
            "is_repost": is_repost,
            "reposter_name": reposter_name,
            "reposter_photo": reposter_photo,
            "original_author_name": original_author_name,
            "photo_url": photo_url,
            "post_time": post_time,
            "stats": stats,
        }

        latest_event = get_latest_interaction_summary_event(lead.id if lead else None)
        if latest_event and "recent_activity" in latest_event.additional_data:
            p_data["recent_activity"] = latest_event.additional_data["recent_activity"]
        elif post_text and post_text != "No activity tracked yet":
            p_data["recent_activity"] = [post_text]

        result.append(p_data)

    def parse_relative_time(rt):
        if not rt or not isinstance(rt, str):
            return 9999999
        rt = rt.lower().split("•")[0].strip()
        num_str = "".join(filter(str.isdigit, rt))
        if not num_str:
            return 9999998
        num = int(num_str)
        if "s" in rt:
            return num
        if "m" in rt:
            return num * 60
        if "h" in rt:
            return num * 3600
        if "d" in rt:
            return num * 86400
        if "w" in rt:
            return num * 604800
        if "mo" in rt:
            return num * 2592000
        if "yr" in rt:
            return num * 31536000
        return 9999997

    def get_estimated_post_date(p):
        ts_str = p.get("timestamp", "")
        rt = p.get("post_time", "")
        if not ts_str:
            return datetime(1970, 1, 1)
        try:
            base_time = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            rel_sec = parse_relative_time(rt)
            return base_time - timedelta(seconds=rel_sec)
        except Exception:
            return datetime(1970, 1, 1)

    for p in result:
        url = p["url"]
        entry = last_posts.get(url)
        if isinstance(entry, dict):
            p["timestamp"] = entry.get("timestamp", "")
        else:
            p["timestamp"] = ""

        p["full_name"] = p["name"]
        db = SessionLocal()
        lead = db.query(Lead).filter(Lead.linkedin_url == p["url"]).first()
        if lead:
            p["name"] = lead.name or p["name"]
            p["email"] = lead.email or p.get("email")
            p["company"] = (
                p.get("company")
                if p.get("company") and p.get("company").lower() not in ["self-employed", ""]
                else lead.company
            )
            p["role"] = (
                p.get("role")
                if p.get("role") and p.get("role").lower() not in ["experience", ""]
                else lead.role
            )
            p["headline"] = lead.headline or p.get("headline")
            p["about"] = lead.about or p.get("about")
            p["work_description"] = lead.work_description or p.get("work_description")
            p["status"] = lead.status
        db.close()

    result.sort(key=get_estimated_post_date, reverse=True)

    if updated:
        save_last_posts(last_posts)

    clean_result = []
    for p in result:
        clean_result.append(
            {
                "name": p.get("name"),
                "headline": p.get("headline"),
                "company": p.get("company"),
                "role": p.get("role"),
                "about": p.get("about"),
                "work_description": p.get("work_description"),
                "recent_activity": p.get("recent_activity"),
            }
        )
    return clean_result


def fetch_profiles_raw_data() -> List[Dict[str, Any]]:
    profiles = read_profiles()
    last_posts = load_last_posts()
    result: List[Dict[str, Any]] = []

    for url in profiles:
        username = (
            url.split("/in/")[1].split("/")[0].replace("-", " ").title()
            if "/in/" in url
            else url
        )
        entry = last_posts.get(url)

        if isinstance(entry, dict):
            post_text = entry.get("text", "No text found")
            headline = entry.get("headline", "")
            about = entry.get("about", "")
            work_description = entry.get("work_description", "")
            company = entry.get("company", "")
            role = entry.get("role", "")
            email = entry.get("email", "")
        else:
            post_text = entry
            headline = about = work_description = company = role = email = ""

        db = SessionLocal()
        lead = db.query(Lead).filter(Lead.linkedin_url == url).first()
        db.close()

        p_data: Dict[str, Any] = {
            "url": url,
            "name": lead.name if lead else username,
            "headline": headline or (lead.headline if lead else ""),
            "company": company or (lead.company if lead else ""),
            "role": role or (lead.role if lead else ""),
            "about": about or (lead.about if lead else ""),
            "work_description": work_description or (lead.work_description if lead else ""),
            "email": email or (lead.email if lead else ""),
            "status": lead.status if lead else "active",
            "recent_activity": [],
            "has_new_activity": False,
        }

        latest_event = get_latest_interaction_summary_event(lead.id if lead else None)
        if latest_event:
            if "recent_activity" in latest_event.additional_data:
                p_data["recent_activity"] = latest_event.additional_data["recent_activity"]
            p_data["has_new_activity"] = latest_event.additional_data.get("has_new_activity", False)
        elif post_text and post_text != "No activity tracked yet":
            p_data["recent_activity"] = [post_text]

        result.append(p_data)
    return result


def list_profiles_raw() -> List[Dict[str, Any]]:
    return fetch_profiles_raw_data()

