import csv
import json
import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
# Use absolute paths relative to the script location to appease linters/IDE resolution
SCRIPT_DIR = Path(__file__).parent
TARGETS = {
    # North Carolina
    "NC State": "https://ncsu.academicworks.com/opportunities",
    "UNCG": "https://uncg.academicworks.com/opportunities",
    "App State": "https://appstate.academicworks.com/opportunities",
    "ECU": "https://ecu.academicworks.com/opportunities",
    "UNCW": "https://uncw.academicworks.com/opportunities",
    "Wake Tech": "https://waketech.academicworks.com/opportunities",
    "Fay Tech": "https://faytechcc.academicworks.com/opportunities",
    "CPCC": "https://cpcc.academicworks.com/opportunities",
    "UNCC": "https://ninerscholars.uncc.edu/opportunities",
    # South Carolina
    "Clemson": "https://clemson.academicworks.com/opportunities",
    "UofSC": "https://sc.academicworks.com/opportunities",
    "CofC": "https://cofc.academicworks.com/opportunities",
    "Gvltec": "https://gvltec.academicworks.com/opportunities",
    "Trident Tech": "https://tridenttech.academicworks.com/opportunities",
}

OUTPUT_FILE = SCRIPT_DIR.parent / "data" / "scholarship_targets.csv"
STATE_FILE = SCRIPT_DIR.parent / "data" / "scholarship_state.json"

KEYWORDS = [
    "cyber",
    "security",
    "technology",
    "computer",
    "it",
    "merancas",
    "network",
    "stem",
    "engineering",
    "data",
    "transfer",
    "robotics",
    "intelligence",
    "defense",
]

# Attempt to load environment variables safely
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=SCRIPT_DIR.parent / ".env")
except (ImportError, ModuleNotFoundError):
    pass

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# --- HELPER FUNCTIONS ---


def get_eastern_time():
    """Returns current time in EST (UTC-5) manually to avoid library overhead."""
    utc_now = datetime.now(timezone.utc)
    est_now = utc_now - timedelta(hours=5)
    return est_now.isoformat()


def clean_text(text):
    """Safely strips and cleans text from HTML elements."""
    if text:
        return text.strip().replace("\n", " ").replace("\r", "")
    return "N/A"


def is_opportunity_live(deadline_text):
    """Checks if the scholarship is still accepting applications."""
    if not deadline_text:
        return True
    dead_indicators = ["ended", "expired", "closed", "past"]
    search_text = deadline_text.lower()
    return not any(ind in search_text for ind in dead_indicators)


def load_state():
    """Loads previous findings to prevent duplicate alerts."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, ValueError):
            return {}
    return {}


def save_state(state_data):
    """Saves the current state to the local JSON file."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=4)
    except IOError as e:
        print(f"[!] Could not save state file: {e}")


def send_discord_alert(scholarship):
    """Pushes a formatted embed to Discord with school-specific branding."""
    if not DISCORD_WEBHOOK_URL:
        return

    sch_school = scholarship.get("School", "Unknown")

    # --- DYNAMIC BRANDING ---
    # Define a dictionary to map schools to their branding
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

    # Get the branding for the school, or use the default
    branding = school_branding.get(sch_school, school_branding["Default"])
    embed_color = branding["color"]
    school_emoji = branding["emoji"]

    payload = {
        "username": "Scholarship Sentinel",
        "embeds": [
            {
                "title": f"{school_emoji} [{sch_school}] New Grant: {scholarship['Name']}",
                "url": scholarship["Link"],
                "color": embed_color,
                "fields": [
                    {
                        "name": "Amount",
                        "value": scholarship.get("Amount", "N/A"),
                        "inline": True,
                    },
                    {
                        "name": "Deadline",
                        "value": scholarship.get("Deadline", "N/A"),
                        "inline": True,
                    },
                    {
                        "name": "Detected At (EST)",
                        "value": scholarship.get("First_Seen", "N/A"),
                        "inline": False,
                    },
                ],
                "footer": {"text": f"{sch_school} Intelligence Feed"},
            }
        ],
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        time.sleep(1)
    except requests.exceptions.RequestException as e:
        print(f"[!] Failed to send Discord alert: {e}")


# --- MAIN LOGIC ---


def scan_opportunities():
    """Orchestrates the scraping of all university portals."""
    seen_history = load_state()
    current_scan_results = {}
    new_findings = []

    for school_name, base_url in TARGETS.items():
        print(f"[*] Starting Scan of {school_name}...")
        page_num = 1
        has_next_page = True

        while has_next_page:
            print(f"    [*] Scanning {school_name} Page {page_num}...")
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                )
            }

            try:
                url = f"{base_url}?page={page_num}"
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code != 200:
                    print(
                        f"    [!] Error fetching page {page_num}: {response.status_code}"
                    )
                    break

                soup = BeautifulSoup(response.text, "html.parser")
                table_rows = soup.select("table tbody tr")
                if not table_rows:
                    break

                for row in table_rows:
                    cols = row.find_all("td")
                    if len(cols) < 3:
                        continue

                    award_amount = clean_text(cols[0].get_text())
                    name_tag = cols[1].find("a")

                    if not name_tag:
                        continue

                    name = clean_text(name_tag.get_text())
                    raw_href = name_tag.get("href", "")
                    link = (
                        raw_href
                        if raw_href.startswith("http")
                        else f"{base_url.replace('/opportunities', '')}{raw_href}"
                    )

                    deadline = clean_text(cols[2].get_text())
                    if not is_opportunity_live(deadline):
                        continue

                    # Keyword Matching
                    desc_preview = clean_text(cols[1].get_text()).replace(name, "")
                    full_text_blob = (name + " " + desc_preview).lower()
                    matched_keywords = [k for k in KEYWORDS if k in full_text_blob]

                    if matched_keywords:
                        current_est_time = get_eastern_time()
                        slug = link.split("/")[-1]
                        scholarship_id = f"{school_name}_{slug}"

                        first_seen = current_est_time
                        if scholarship_id in seen_history:
                            entry = seen_history[scholarship_id]
                            if isinstance(entry, dict):
                                first_seen = entry.get("First_Seen", current_est_time)

                        scholarship_data = {
                            "School": school_name,
                            "Name": name,
                            "Amount": award_amount,
                            "Deadline": deadline,
                            "Link": link,
                            "Match_Reason": ", ".join(matched_keywords),
                            "First_Seen": first_seen,
                            "Last_Seen": current_est_time,
                        }

                        current_scan_results[scholarship_id] = scholarship_data

                        if scholarship_id not in seen_history:
                            print(f"        [!!!] NEW {school_name} TARGET: {name}")
                            new_findings.append(scholarship_data)
                            send_discord_alert(scholarship_data)
                        else:
                            print(f"        [+] Existing {school_name}: {name}")

                # Pagination Check
                next_btn = soup.find("a", class_="next_page")
                if not next_btn or "disabled" in next_btn.get("class", []):
                    has_next_page = False
                else:
                    page_num += 1
                    time.sleep(random.uniform(1.0, 2.5))

            except (requests.exceptions.RequestException, ConnectionError) as e:
                print(f"    [!] Network Error on {school_name} page {page_num}: {e}")
                break
            except Exception as e:
                print(f"    [!] Unexpected Error during scan: {e}")
                break

    # Save State and Export
    seen_history.update(current_scan_results)
    save_state(seen_history)

    if current_scan_results:
        try:
            with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
                fieldnames = [
                    "School",
                    "Name",
                    "Amount",
                    "Deadline",
                    "Link",
                    "Match_Reason",
                    "First_Seen",
                    "Last_Seen",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(current_scan_results.values())
        except IOError as e:
            print(f"[!] Could not export CSV: {e}")

    print(f"[*] Scan Complete. {len(new_findings)} new targets identified.")


if __name__ == "__main__":
    scan_opportunities()
