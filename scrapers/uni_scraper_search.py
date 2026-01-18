import csv
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Add project root to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from alerts.discord_alert import send_summary_alert
from alerts.linkedin_poster import main as linkedin_main

# --- CONFIGURATION ---
# Use absolute paths relative to the script location to appease linters/IDE resolution
SCRIPT_DIR = Path(__file__).parent
# UNCG: uses auth and different backend for their scholarship portal
# App State: uses auth and different backend for their scholarship portal
# UNCW uses auth and different backend for their scholarship portal
# UNCC uses auth and different backend for their scholarship portal
# "Clemson": "https://clemson.academicworks.com/opportunities",
# Trident Tech uses auth and different backend for their scholarship portal
TARGETS = {
    # North Carolina
    "CPCC": "https://cpcc.academicworks.com/opportunities",
    "CPCC-Flexible": "https://cpcc.academicworks.com/opportunities/flexible",
    "CPCC-External": "https://cpcc.academicworks.com/opportunities/external",
    "NC State": "https://ncsu.academicworks.com/opportunities",
    "NC State-Flexible": "https://ncsu.academicworks.com/opportunities/flexible",
    "ECU": "https://ecu.academicworks.com/opportunities",
    "ECU-External": "https://ecu.academicworks.com/opportunities/external",
    "Wake Tech": "https://waketech.academicworks.com/opportunities",
    "Fay Tech": "https://faytechcc.academicworks.com/opportunities",
    "Fay Tech-External": "https://faytechcc.academicworks.com/opportunities/external",
    # South Carolina
    "UofSC": "https://sc.academicworks.com/opportunities",
    "CofC": "https://cofc.academicworks.com/opportunities",
    "Gvltec": "https://gvltec.academicworks.com/opportunities",
}

OUTPUT_FILE = SCRIPT_DIR.parent / "data" / "scholarship_targets_search.csv"
STATE_FILE = SCRIPT_DIR.parent / "data" / "scholarship_state_search.json"

KEYWORDS = [
    "information+Technology",
    "cyber+security",
    "computer+science",
    "computer+engineering",
    "data+science",
    "artificial+intelligence",
    "machine+learning",
    "software+engineering",
    "software+development",
    "data+analytics",
    "merancas",
    "stem",
    "robotics",
]


# --- HELPER FUNCTIONS ---


def get_eastern_time():
    """Returns current time in EST (UTC-5) manually to avoid library overhead."""
    utc_now = datetime.now(timezone.utc)
    est_now = utc_now - timedelta(hours=5)
    return est_now.isoformat()


def clean_text(text):
    """Safely strips, cleans, and extracts date from text."""
    if not text:
        return "N/A"

    # General cleaning
    cleaned = text.strip().replace("\n", " ").replace("\r", " ")

    # Date extraction
    # First, try to match common date formats
    date_patterns = [
        r"(\d{1,2}/\d{1,2}/\d{4})",  # MM/DD/YYYY
        r"(\d{4}-\d{2}-\d{2})",  # YYYY-MM-DD
        r"([A-Za-z]+\s\d{1,2},\s\d{4})",  # Month DD, YYYY
    ]
    for pattern in date_patterns:
        match = re.search(pattern, cleaned)
        if match:
            return match.group(1)

    # If no date format is found, return the cleaned text
    return cleaned


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


def generate_markdown_page(scholarships):
    """Generates a markdown page with the full list of scholarships."""
    # Group by school
    school_scholarships = {}
    for s in scholarships:
        school = s.get("School", "N/A")
        if school not in school_scholarships:
            school_scholarships[school] = []
        school_scholarships[school].append(s)

    md = "# Scholarship Sentinel - Daily Digest\n\n"
    md += f"Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"

    for school, sch_list in sorted(school_scholarships.items()):
        md += f"## {school}\n\n"
        md += "| Name | Amount | Deadline |\n"
        md += "|------|--------|----------|\n"
        for s in sch_list:
            md += f"| [{s.get('Name', 'N/A')}]({s.get('Link', '#')}) | {s.get('Amount', 'N/A')} | {s.get('Deadline', 'N/A')} |\n"
        md += "\n"

    return md


# --- MAIN LOGIC ---
def scan_opportunities():
    """Orchestrates the scraping of all university portals using keyword search."""
    seen_history = load_state()
    current_scan_results = {}
    new_findings = []
    updated_findings = []

    for school_name, base_url in TARGETS.items():
        print(f"[*] Starting Scan of {school_name}...")
        for keyword in KEYWORDS:
            print(f"  [*] Searching for keyword: '{keyword}'")
            for page_num in range(1, 100):  # Loop through a large number of pages
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/91.0.4472.124 Safari/537.36"
                    )
                }

                try:
                    params = {"utf8": "✓", "term": keyword, "page": page_num}
                    response = requests.get(
                        base_url, headers=headers, timeout=15, params=params
                    )
                    if response.status_code == 404:
                        print(
                            f"    [!] Page {page_num} not found for keyword '{keyword}'. Ending scan."
                        )
                        break
                    if response.status_code != 200:
                        print(
                            f"    [!] Error fetching page {page_num} for keyword '{keyword}': {response.status_code}"
                        )
                        break

                    soup = BeautifulSoup(response.text, "html.parser")
                    table_rows = soup.select("table tbody tr")

                    # Guard clause for "No opportunities matched your search"
                    if len(table_rows) == 1:
                        cols = table_rows[0].find_all("td")
                        if (
                            len(cols) == 1
                            and "No opportunities matched your search"
                            in cols[0].get_text()
                        ):
                            print(
                                f"    [!] No results for '{keyword}' on page {page_num}. Moving to next keyword."
                            )
                            break

                    if not table_rows:
                        print(
                            f"    [!] No table rows found on page {page_num} for '{keyword}'. Ending scan."
                        )
                        break

                    scholarships_found_on_page = False
                    for row in table_rows:
                        cols = row.find_all(["td", "th"])
                        if len(cols) < 3:
                            continue

                        award_amount = clean_text(cols[0].get_text())
                        name_tag = cols[1].find("a")

                        if not name_tag:
                            continue

                        scholarships_found_on_page = True
                        name = clean_text(name_tag.get_text())
                        raw_href = name_tag.get("href", "")
                        link = (
                            raw_href
                            if raw_href.startswith("http")
                            else f"{base_url.replace('/opportunities', '')}{raw_href}"
                        )

                        deadline = clean_text(cols[2].get_text())
                        live = is_opportunity_live(deadline)

                        # Since we searched by keyword, we can assume it's a match
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
                            "Live": live,
                            "Match_Reason": keyword,
                            "First_Seen": first_seen,
                            "Last_Seen": current_est_time,
                        }

                        current_scan_results[scholarship_id] = scholarship_data

                        if scholarship_id not in seen_history:
                            print(f"        [!!!] NEW {school_name} TARGET: {name}")
                            new_findings.append(scholarship_data)

                        else:
                            # It's an existing scholarship, let's check for deadline changes.
                            previous_deadline = seen_history[scholarship_id].get(
                                "Deadline"
                            )
                            if previous_deadline and previous_deadline != deadline:
                                print(
                                    f"        [!!!] DEADLINE CHANGED for {name}: {previous_deadline} -> {deadline}"
                                )
                                scholarship_data["Previous_Deadline"] = (
                                    previous_deadline
                                )
                                updated_findings.append(scholarship_data)
                            else:
                                print(f"        [+] Existing {school_name}: {name}")

                    if not scholarships_found_on_page:
                        print(
                            f"    [!] No valid scholarship data on page {page_num}. Ending scan for '{keyword}'."
                        )
                        break

                    time.sleep(random.uniform(1.0, 2.5))

                except (requests.exceptions.RequestException, ConnectionError) as e:
                    print(
                        f"    [!] Network Error on {school_name} page {page_num} for '{keyword}': {e}"
                    )
                    break
                except Exception as e:
                    print(f"    [!] Unexpected Error during scan: {e}")
                    break
        print(f"  [*] Finished keyword searches for {school_name}.")

    # Send summary alert for new, live scholarships
    live_new_findings = [s for s in new_findings if s.get("Live", False)]
    live_updated_findings = [s for s in updated_findings if s.get("Live", False)]

    all_findings = live_new_findings + live_updated_findings

    if all_findings:
        print(
            f"[*] Sending summary alert for {len(all_findings)} new/updated live scholarships."
        )
        send_summary_alert(all_findings)
        markdown_content = generate_markdown_page(all_findings)
        with open("docs/index.md", "w", encoding="utf-8") as f:
            f.write(markdown_content)
    else:
        print("[*] No new or updated live scholarships found to alert.")

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
                    "Live",
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

    return all_findings


if __name__ == "__main__":
    all_findings = scan_opportunities()
    if all_findings:
        linkedin_main(all_findings)
