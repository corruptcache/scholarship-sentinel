import os
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Assumes .env file is in the project root directory
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def send_summary_alert(scholarships):
    """Pushes a single message with multiple embeds to Discord, summarizing all new scholarships."""
    if not DISCORD_WEBHOOK_URL:
        print("[!] DISCORD_WEBHOOK_URL not found. Cannot send summary alert.")
        return

    # Filter out scholarships with "Ended" or missing deadlines
    scholarships = [
        s for s in scholarships if s.get("Deadline") and s.get("Deadline") != "Ended"
    ]

    if not scholarships:
        print("[+] No new, valid scholarships to report in summary.")
        return

    # Group scholarships by school
    school_scholarships = {}
    for s in scholarships:
        school = s.get("School", "N/A")
        if school not in school_scholarships:
            school_scholarships[school] = []
        school_scholarships[school].append(s)

    embeds = []
    for school, sch_list in school_scholarships.items():
        # Create a list of (datetime, scholarship) tuples
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
            continue  # No scholarships with valid dates for this school

        # Find the earliest date
        earliest_date = min(scholarships_with_dates, key=lambda x: x[0])[0]

        # Get up to 3 scholarships with that date
        quick_glance_scholarships = [
            s for dt, s in scholarships_with_dates if dt == earliest_date
        ][:3]

        fields = []
        for s in quick_glance_scholarships:
            previous_deadline = s.get("Previous_Deadline")
            if previous_deadline:
                value = f"**DEADLINE EXTENDED!**\n[{s.get('Name', 'N/A')}]({s.get('Link', '#')})\nAmount: {s.get('Amount', 'N/A')} | ~`{previous_deadline}`~ -> **{s.get('Deadline', 'N/A')}**"
            else:
                value = f"[{s.get('Name', 'N/A')}]({s.get('Link', '#')})\nAmount: {s.get('Amount', 'N/A')} | Deadline: {s.get('Deadline', 'N/A')}"
            if len(value) > 1024:
                value = value[:1021] + "..."
            fields.append({"name": "\u200b", "value": value})

        embed = {
            "title": f"🎓 {school} - Quick Glance",
            "description": f"Earliest deadline: **{earliest_date.strftime('%Y-%m-%d')}**\n[View all scholarships on our website](https://corruptcache.github.io/scholarship-sentinel/)",
            "fields": fields,
            "color": 5814783,  # Blue color
            "footer": {"text": "Scholarship Sentinel | Daily Digest"},
        }
        embeds.append(embed)

    if not embeds:
        print("[+] No embeds to send.")
        return

    for embed in embeds:
        payload = {"username": "Scholarship Sentinel", "embeds": [embed]}
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            resp.raise_for_status()
            print(f"[+] Discord summary alert sent for a chunk of scholarships.")
            time.sleep(1)  # sleep for 1 second between each request
        except requests.exceptions.RequestException as e:
            print(f"[!] Failed to send Discord summary alert: {e}")
