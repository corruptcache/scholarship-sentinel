import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# 1. ROBUST ENVIRONMENT LOADING
script_dir = Path(__file__).parent
env_path = script_dir.parent / ".env"
load_dotenv(dotenv_path=env_path)

# --- CONFIGURATION ---
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
STATE_FILES = [script_dir.parent / "data" / "scholarship_state.json"]
GITHUB_REPO_URL = "https://github.com/corruptcache/scholarship-sentinel"


def resolve_user_urn():
    """Determines the Author URN via OIDC or Legacy API with robust checks."""
    if not LINKEDIN_ACCESS_TOKEN:
        print("[!] No Access Token found. Cannot resolve URN.")
        return None

    headers = {"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}"}

    # Try OIDC endpoint (Modern)
    try:
        response = requests.get(
            "https://api.linkedin.com/v2/userinfo", headers=headers, timeout=10
        )
        if response.status_code == 200:
            return f"urn:li:person:{response.json().get('sub')}"
    except Exception:
        pass

    # Fallback to Legacy Me endpoint
    try:
        response = requests.get(
            "https://api.linkedin.com/v2/me", headers=headers, timeout=10
        )
        if response.status_code == 200:
            return f"urn:li:person:{response.json().get('id')}"
    except Exception:
        pass

    return None


def get_fresh_loot():
    """Finds items detected in the last 25 hours from scholarship_state.json."""
    fresh_loot = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=25)

    for filename in STATE_FILES:
        if not os.path.exists(filename):
            continue
        try:
            with open(filename, "r") as f:
                data = json.load(f)
            for key, item in data.items():
                first_seen_str = item.get("First_Seen")
                if not first_seen_str:
                    continue

                first_seen_dt = datetime.fromisoformat(first_seen_str)
                if first_seen_dt.tzinfo is None:
                    first_seen_dt = first_seen_dt.replace(tzinfo=timezone.utc)

                if first_seen_dt > cutoff_time:
                    fresh_loot.append(item)
        except Exception as e:
            print(f"[!] Error reading state file: {e}")
    return fresh_loot


def format_linkedin_post(loot_list):
    """Summarizes scholarships with school tags, brand tagline, and community CTAs."""
    if not loot_list:
        return None

    display_items = loot_list[:3]
    total_found = len(loot_list)

    # Automated Disclosure and Brand Tagline
    post_text = "🤖 **Automated Scholarship Sentinel Update** 🛡️\n\n"
    post_text += (
        "\"Financial aid isn't a scarcity problem; it's a visibility problem.\"\n\n"
    )
    post_text += f"My automated sentinel just intercepted {total_found} new funding opportunities for NC and SC students. Today's top picks:\n\n"

    for item in display_items:
        # School Tagging ([CPCC] or [UNCC])
        school = item.get("School", "NC")
        name = item.get("Name") or item.get("Title", "Unknown Scholarship")
        amount = item.get("Amount", "Full Funding")
        deadline = item.get("Deadline", "Check Link")

        post_text += f"💰 **[{school}] {name}**\n   • Value: {amount}\n   • Deadline: {deadline}\n\n"

    if total_found > 3:
        post_text += f"🔍 ...and {total_found - 3} more detected today!\n\n"

    # CTAs
    post_text += "🚀 **Follow me for daily automated updates** on Cyber Security and IT scholarships in the Carolinas! 🎓\n\n"
    post_text += f"🛠️ **Built with Open Source:** Check out the code, star the repo, or contribute here:\n{GITHUB_REPO_URL}\n\n"

    # Dynamic Hashtags
    hashtags = {"#CyberSecurity", "#Scholarships", "#OSINT", "#IT", "#Automation"}
    for item in loot_list:
        school_tag = f"#{item.get('School', '').replace(' ', '')}"
        hashtags.add(school_tag)

    post_text += " ".join(hashtags)
    return post_text


def post_to_linkedin(text, author_urn):
    """Sends the formatted text to the LinkedIn Posts API."""
    api_url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202501",
    }

    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        if response.status_code == 201:
            print("[*] LinkedIn Post Successful!")
        else:
            print(f"[!] Post Failed: {response.status_code}\n{response.text}")
    except Exception as e:
        print(f"[!] Connection Error: {e}")


if __name__ == "__main__":
    print("[*] Waking up Scholarship Sentinel social bot...")
    user_urn = resolve_user_urn()

    if user_urn:
        loot = get_fresh_loot()
        if loot:
            print(f"[*] Found {len(loot)} items. Posting digest...")
            post_body = format_linkedin_post(loot)
            post_to_linkedin(post_body, user_urn)
        else:
            print("[*] No new intel today. Staying quiet.")
    else:
        print("[!] Aborting. Could not determine User ID.")
