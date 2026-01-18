import json
import logging
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
STATE_FILES = [script_dir.parent / "data" / "scholarship_state_search.json"]
GITHUB_REPO_URL = "https://github.com/corruptcache/scholarship-sentinel"


def resolve_user_urn():
    """Determines the Author URN via OIDC or Legacy API with robust checks."""
    if not LINKEDIN_ACCESS_TOKEN:
        logging.error(
            "CRITICAL: LinkedIn Token is missing or expired. Action required in GitHub Secrets."
        )
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
    """Finds items detected or updated in the last 25 hours from scholarship_state.json."""
    fresh_loot = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=25)

    for filename in STATE_FILES:
        if not os.path.exists(filename):
            continue
        try:
            with open(filename, "r") as f:
                data = json.load(f)
            for key, item in data.items():
                if not item.get("Live", False):
                    continue

                # Filter out ended or missing deadlines
                if not item.get("Deadline") or item.get("Deadline") == "Ended":
                    continue

                is_new = False
                is_updated = False

                first_seen_str = item.get("First_Seen")
                if first_seen_str:
                    first_seen_dt = datetime.fromisoformat(first_seen_str)
                    if first_seen_dt.tzinfo is None:
                        first_seen_dt = first_seen_dt.replace(tzinfo=timezone.utc)
                    if first_seen_dt > cutoff_time:
                        is_new = True

                deadline_updated_at_str = item.get("Deadline_Updated_At")
                if deadline_updated_at_str:
                    deadline_updated_at_dt = datetime.fromisoformat(
                        deadline_updated_at_str
                    )
                    if deadline_updated_at_dt.tzinfo is None:
                        deadline_updated_at_dt = deadline_updated_at_dt.replace(
                            tzinfo=timezone.utc
                        )
                    if deadline_updated_at_dt > cutoff_time:
                        is_updated = True

                if is_new or is_updated:
                    fresh_loot.append(item)

        except Exception as e:
            logging.error(f"Error reading state file: {e}")
    return fresh_loot


def generate_hashtags(loot_list):
    """Generates a set of relevant hashtags for the post."""
    hashtags = {"#CyberSecurity", "#Scholarships", "#OSINT", "#IT", "#Automation"}
    for item in loot_list:
        school_tag = f"#{item.get('School', '').replace(' ', '')}"
        hashtags.add(school_tag)
    return hashtags


def create_post_text(loot_list):
    """Creates the main text content for the LinkedIn post."""
    school_scholarships = {}
    for s in loot_list:
        school = s.get("School", "N/A")
        if school not in school_scholarships:
            school_scholarships[school] = []
        school_scholarships[school].append(s)

    total_found = len(loot_list)

    post_text = "🤖 **Automated Scholarship Sentinel Update** 🛡️\n\n"
    post_text += (
        "\"Financial aid isn't a scarcity problem; it's a visibility problem.\"\n\n"
    )
    post_text += f"My automated sentinel just intercepted {total_found} new/updated funding opportunities for NC and SC students. Today's top picks:\n\n"

    for school, sch_list in school_scholarships.items():
        scholarships_with_dates = []
        for s in sch_list:
            deadline_str = s.get("Deadline")
            if not deadline_str or deadline_str in ["Ended", "Check Link", "N/A"]:
                continue

            formats_to_try = ["%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"]
            deadline_dt = None
            for fmt in formats_to_try:
                try:
                    deadline_dt = datetime.strptime(deadline_str, fmt)
                    break
                except ValueError:
                    pass

            if deadline_dt:
                scholarships_with_dates.append((deadline_dt, s))

        if not scholarships_with_dates:
            continue

        earliest_date = min(scholarships_with_dates, key=lambda x: x[0])[0]
        quick_glance_scholarships = [
            s for dt, s in scholarships_with_dates if dt == earliest_date
        ][:3]

        post_text += (
            f"**{school}** - Earliest Deadline: {earliest_date.strftime('%Y-%m-%d')}\n"
        )
        for item in quick_glance_scholarships:
            name = item.get("Name") or item.get("Title", "Unknown Scholarship")
            amount = item.get("Amount", "Full Funding")
            deadline = item.get("Deadline", "Check Link")
            link = item.get("Link", "#")
            previous_deadline = item.get("Previous_Deadline")

            if previous_deadline:
                post_text += f"  • DEADLINE EXTENDED! [{name}]({link}) - {amount} - From {previous_deadline} to {deadline}\n"
            else:
                post_text += f"  • [{name}]({link}) - {amount} - {deadline}\n"
        post_text += "\n"

    post_text += f"🔍 For the full list of {total_found} scholarships, visit our website:\nhttps://corruptcache.github.io/scholarship-sentinel/\n\n"

    post_text += "🚀 **Follow me for daily automated updates** on Cyber Security and IT scholarships in the Carolinas! 🎓\n\n"
    post_text += f"🛠️ **Built with Open Source:** Check out the code, star the repo, or contribute here:\n{GITHUB_REPO_URL}\n\n"

    return post_text


def format_linkedin_post(loot_list):
    """Summarizes scholarships, handles truncation, and adds hashtags."""
    if not loot_list:
        return None

    post_text = create_post_text(loot_list)
    hashtags = generate_hashtags(loot_list)
    hashtag_str = " ".join(hashtags)

    # LinkedIn's character limit is 3000. Let's be safe.
    if len(post_text) + len(hashtag_str) > 2900:
        # Truncate the main post text, leaving space for a note and hashtags
        available_space = 2900 - len(hashtag_str) - 50  # 50 chars for the note
        post_text = (
            post_text[:available_space] + "...\n\n(Post truncated due to length)"
        )

    return f"{post_text}\n{hashtag_str}"


def post_to_linkedin(text, author_urn):
    """Sends the formatted text to the LinkedIn Posts API."""
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
        loot = scholarships
        if loot is None:
            loot = get_fresh_loot()

        if loot:
            logging.info(f"Found {len(loot)} items. Posting digest...")
            post_body = format_linkedin_post(loot)
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
