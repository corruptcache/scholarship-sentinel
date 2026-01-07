import os
import time
from datetime import datetime
from pathlib import Path

import requests

# --- LOAD ENVIRONMENT ---
try:
    from dotenv import load_dotenv

    script_dir = Path(__file__).parent
    dotenv_path = script_dir.parent / ".env"
    load_dotenv(dotenv_path=dotenv_path)
except ImportError:
    pass

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def simulate_detection():
    # 1. VISUAL PROOF: The Console Log
    # This mimics the exact output of uni_scraper.py so it looks authentic in a screenshot.
    print("[*] Starting Intelligence Scan of All Schools...")
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
    dummy_grants = [
        {
            "School": "CPCC",
            "Name": grant_name + " [SIMULATION]",
            "Amount": "$2,500.00",
            "Deadline": "05/15/2026",
            "Link": "https://cpcc.academicworks.com/opportunities/merancas-technical-careers",
            "First_Seen": timestamp,
        },
        {
            "School": "NC State",
            "Name": "NC State Engineering Scholarship [SIMULATION]",
            "Amount": "$5,000",
            "Deadline": "2026-08-15",
            "Link": "https://ncsu.academicworks.com/opportunities/12345",
            "First_Seen": timestamp,
        },
        {
            "School": "UNCG",
            "Name": "UNCG Business Scholarship [SIMULATION]",
            "Amount": "$2,000",
            "Deadline": "2026-09-01",
            "Link": "https://uncg.academicworks.com/opportunities/67890",
            "First_Seen": timestamp,
        },
        {
            "School": "App State",
            "Name": "App State Computer Science Scholarship [SIMULATION]",
            "Amount": "$3,000",
            "Deadline": "2026-07-20",
            "Link": "https://appstate.academicworks.com/opportunities/13579",
            "First_Seen": timestamp,
        },
    ]

    for dummy_grant in dummy_grants:
        # --- DYNAMIC BRANDING ---
        school_branding = {
            "CPCC": {"color": 5763719, "emoji": "🟢"},
            "UNCC": {"color": 11964228, "emoji": "🟡"},
            "NC State": {"color": 16711680, "emoji": "🐺"},
            "UNCG": {"color": 127, "emoji": "⚔️"},
            "App State": {"color": 0, "emoji": "🏔️"},
            "ECU": {"color": 5046202, "emoji": "🏴‍☠️"},
            "UNCW": {"color": 127, "emoji": "🌊"},
            "Wake Tech": {"color": 48868, "emoji": "🦅"},
            "Fay Tech": {"color": 135, "emoji": "✈️"},
            "Clemson": {"color": 16744448, "emoji": "🐅"},
            "UofSC": {"color": 7506194, "emoji": "🐔"},
            "CofC": {"color": 13421772, "emoji": "🐾"},
            "Gvltec": {"color": 16776960, "emoji": "🔧"},
            "Trident Tech": {"color": 16777215, "emoji": "🔱"},
            "Default": {"color": 808080, "emoji": "🎓"},
        }
        branding = school_branding.get(
            dummy_grant["School"], school_branding["Default"]
        )
        embed_color = branding["color"]
        school_emoji = branding["emoji"]

        payload = {
            "username": "Scholarship Sentinel",
            "embeds": [
                {
                    "title": f"{school_emoji} New {dummy_grant['School']} Grant: {dummy_grant['Name']}",
                    "url": dummy_grant["Link"],
                    "color": embed_color,
                    "fields": [
                        {
                            "name": "Amount",
                            "value": dummy_grant["Amount"],
                            "inline": True,
                        },
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
            print(f"    [*] Alert sent to Discord for {dummy_grant['School']}.")
            time.sleep(1)
        except Exception as e:
            print(
                f"    [!] Failed to send Discord alert for {dummy_grant['School']}: {e}"
            )


if __name__ == "__main__":
    simulate_detection()
