import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# --- CONFIGURATION & PATHS ---
script_dir = Path(__file__).parent
env_path = script_dir.parent / ".env"
load_dotenv(dotenv_path=env_path)

LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
# Standardize the state file path
STATE_FILE = script_dir.parent / "data" / "scholarship_state_search.json"
GITHUB_REPO_URL = "https://github.com/corruptcache/scholarship-sentinel"


def resolve_user_urn():
    """Determines the Author URN via OIDC or Legacy API with robust checks."""
    if not LINKEDIN_ACCESS_TOKEN:
        logging.error("CRITICAL: LinkedIn Token is missing or expired.")
        return None
    headers = {"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}"}
    try:
        response = requests.get(
            "https://api.linkedin.com/v2/userinfo", headers=headers, timeout=10
        )
        if response.status_code == 200:
            return f"urn:li:person:{response.json().get('sub')}"
    except Exception:
        pass
    try:
        response = requests.get(
            "https://api.linkedin.com/v2/me", headers=headers, timeout=10
        )
        if response.status_code == 200:
            return f"urn:li:person:{response.json().get('id')}"
    except Exception:
        pass
    return None


def get_fresh_loot(state_file):
    """
    TICKET 1 FIX: Finds items detected in the last 24 hours.
    This is simpler and more aligned with a 'daily' digest.
    """
    if not os.path.exists(state_file):
        logging.error(f"State file not found at {state_file}")
        return []

    with open(state_file, "r") as f:
        data = json.load(f)

    now = datetime.now(timezone.utc)
    fresh = []
    for uid, item in data.items():
        try:
            # Ensure First_Seen is timezone-aware for correct comparison
            detected_at = datetime.fromisoformat(item["First_Seen"]).replace(
                tzinfo=timezone.utc
            )
            if (now - detected_at).total_seconds() < 86400:  # 24 hours
                fresh.append(item)
        except (KeyError, TypeError):
            # Skip items missing 'First_Seen' or with invalid format
            continue
    return fresh


def to_bold_unicode(text):
    """Converts a string to its bold Unicode equivalent for LinkedIn posts."""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    bold_chars = "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
    translation_table = str.maketrans(chars, bold_chars)
    return text.translate(translation_table)


def create_post_text(fresh_loot):
    """
    TICKET 1 FIX: Formats a professional LinkedIn post with top 3 overall picks.
    """
    if not fresh_loot:
        return None

    # Sort ALL fresh findings by deadline urgency (closest first)
    def date_sorter(x):
        try:
            return datetime.strptime(x["Deadline"], "%m/%d/%Y")
        except (ValueError, TypeError):
            # Send items with bad/missing deadlines to the bottom of the list
            return datetime(2099, 12, 31)

    sorted_loot = sorted(fresh_loot, key=date_sorter)
    top_picks = sorted_loot[:3]

    post = f"🤖 {to_bold_unicode('Automated Scholarship Sentinel Update')} 🛡️\n\n"
    post += "\"Financial aid isn't a scarcity problem; it's a visibility problem.\"\n\n"
    post += f"I've detected {len(fresh_loot)} new funding opportunities for NC students. Here are the top picks with imminent deadlines:\n\n"

    for item in top_picks:
        title = f"[{item.get('School', 'N/A')}] {item.get('Name', 'N/A')}"
        post += f"💰 {to_bold_unicode(title)}\n"
        post += f"   • Value: {item.get('Amount', 'N/A')}\n"
        post += f"   • Deadline: {item.get('Deadline', 'N/A')}\n"
        post += f"   • Link: {item.get('Link', '#')}\n\n"

    if len(fresh_loot) > 3:
        post += f"🔍 ...and {len(fresh_loot) - 3} other grants detected today!\n\n"

    post += "🚀 Follow for daily automated updates. Built with Open Source Intelligence.\n\n"
    # Static, relevant hashtags
    post += "#Scholarships #CyberSecurity #OSINT #InfoSec #FinancialAid #StudentSuccess"

    return post


def post_to_linkedin(text, author_urn):
    """Sends the formatted text to the LinkedIn Posts API."""
    # Truncate here to be safe, as the final text is assembled just before this.
    if len(text) > 3000:
        text = text[:2950] + "... (post truncated)"

    api_url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202601",
    }
    payload = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED"},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        if response.status_code == 201:
            logging.info("LinkedIn Post Successful!")
        else:
            logging.error(f"Post Failed: {response.status_code}\n{response.text}")
    except Exception as e:
        logging.error(f"Connection Error: {e}")


def main(scholarships=None):
    """Main function to run the LinkedIn poster bot."""
    logging.info("Waking up Scholarship Sentinel social bot...")
    user_urn = resolve_user_urn()

    if user_urn:
        # If scholarships are passed directly (e.g., from the main scraper), use them.
        # Otherwise, find the fresh loot ourselves.
        loot = scholarships if scholarships is not None else get_fresh_loot(STATE_FILE)

        if loot:
            logging.info(f"Found {len(loot)} items. Posting digest...")
            post_body = create_post_text(loot)
            if post_body:
                post_to_linkedin(post_body, user_urn)
            else:
                logging.info("Post body is empty. Staying quiet.")
        else:
            logging.info("No new intel today. Staying quiet.")
    else:
        logging.warning("Aborting. Could not determine User ID.")


if __name__ == "__main__":
    main()
