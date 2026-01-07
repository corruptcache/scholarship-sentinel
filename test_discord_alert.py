import os
import time
from datetime import datetime

import requests

# --- LOAD ENVIRONMENT ---
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def simulate_detection():
    # 1. VISUAL PROOF: The Console Log
    # This mimics the exact output of uni_scraper.py so it looks authentic in a screenshot.
    print("[*] Starting Intelligence Scan of CPCC...")
    time.sleep(1.5)  # Fake loading time
    print("    [*] Scanning Page 1...")
    time.sleep(0.5)

    # The "Money Shot" for your screenshot
    grant_name = "Merancas Technical Careers Scholarship"
    timestamp = datetime.now().isoformat()

    print(f"        [!!!] NEW TARGET: {grant_name}")
    print(f"              Timestamp (EST): {timestamp}")

    # 2. VISUAL PROOF: The Discord Alert
    if not DISCORD_WEBHOOK_URL:
        print("[!] No Discord Webhook found. Set it in .env to test the alert.")
        return

    # Fake Data Payload
    dummy_grant = {
        "School": "CPCC",
        "Name": grant_name,
        "Amount": "$2,500.00",
        "Deadline": "05/15/2026",
        "Link": "https://cpcc.academicworks.com/opportunities/merancas-technical-careers",
        "First_Seen": timestamp,
    }

    payload = {
        "username": "Scholarship Sentinel",
        "embeds": [
            {
                "title": f"💰 New {dummy_grant['School']} Grant: {dummy_grant['Name']}",
                "url": dummy_grant["Link"],
                "color": 5763719,  # CPCC Green
                "fields": [
                    {"name": "Amount", "value": dummy_grant["Amount"], "inline": True},
                    {
                        "name": "Deadline",
                        "value": dummy_grant["Deadline"],
                        "inline": True,
                    },
                    {
                        "name": "Detected At (EST)",
                        "value": dummy_grant["First_Seen"],
                        "inline": False,
                    },
                ],
                "footer": {
                    "text": f"{dummy_grant['School']} Intelligence Feed • SIMULATION MODE"
                },
            }
        ],
    }

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
        print("    [*] Alert sent to Discord.")
    except Exception as e:
        print(f"    [!] Failed to send Discord alert: {e}")


if __name__ == "__main__":
    simulate_detection()
