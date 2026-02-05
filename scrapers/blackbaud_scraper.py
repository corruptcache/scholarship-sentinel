import csv
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Add project root to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from alerts.discord_alert import send_summary_alert
from alerts.linkedin_alert import main as linkedin_main

# --- LOGGING CONFIGURATION ---
LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "sentinel.log"
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

# --- CONFIGURATION ---
# Use absolute paths relative to the script location to appease linters/IDE resolution
SCRIPT_DIR = Path(__file__).parent


def build_target_urls():
    with open("config/schools.json", "r") as f:
        base_targets = json.load(f)

    final_targets = {}
    logging.info("Dynamically discovering target URLs...")
    for school_name, base_url in base_targets.items():
        # The base URL is always a target
        final_targets[school_name] = base_url
        logging.info(f"Added base target: {school_name} - {base_url}")

        suffixes = ["flexible", "external"]
        for suffix in suffixes:
            url_to_check = f"{base_url}/{suffix}"
            try:
                response = requests.head(url_to_check, timeout=10)
                if response.status_code == 200:
                    target_name = f"{school_name}-{suffix.capitalize()}"
                    final_targets[target_name] = url_to_check
                    logging.info(
                        f"Discovered and added: {target_name} - {url_to_check}"
                    )
                else:
                    logging.warning(
                        f"Checked {url_to_check} - Status: {response.status_code}"
                    )
            except requests.RequestException as e:
                logging.error(f"Error checking {url_to_check}: {e}")
    logging.info("Target discovery complete.")
    return final_targets


TARGETS = build_target_urls()

OUTPUT_FILE = SCRIPT_DIR.parent / "data" / "scholarship_targets_search.csv"
STATE_FILE = SCRIPT_DIR.parent / "data" / "scholarship_state_search.json"


def load_keywords():
    with open("config/keywords.json", "r") as f:
        return json.load(f)


KEYWORDS = load_keywords()


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
        logging.error(f"Could not save state file: {e}")


def sanitize_and_prune_state(state_data):
    """
    Removes expired, corrupt, or incomplete entries from the state dictionary.
    This combines sanitization and pruning into a single, efficient pass.
    """
    pruned_count = 0
    sanitized_count = 0
    today = datetime.now().date()

    # Define invalid string values for cleaning
    invalid_strings = ["", "n/a", "check link", "varies"]

    for scholarship_id in list(state_data.keys()):
        scholarship = state_data.get(scholarship_id, {})
        name = scholarship.get("Name", "").strip()
        amount = scholarship.get("Amount", "").strip()
        deadline_str = scholarship.get("Deadline", "").strip()

        # 1. Sanitize: Check for missing critical data
        if (
            not name
            or amount.lower() in invalid_strings
            or deadline_str.lower() in invalid_strings
        ):
            logging.warning(
                f"Sanitizing corrupt entry: '{name}' (ID: {scholarship_id}). Reason: Missing critical data."
            )
            del state_data[scholarship_id]
            sanitized_count += 1
            continue

        # 2. Prune: Check for explicitly ended status
        if deadline_str.lower() in ["ended", "expired", "closed"]:
            logging.info(f"Pruning '{name}' due to ended status: {deadline_str}")
            del state_data[scholarship_id]
            pruned_count += 1
            continue

        # 3. Prune: Check for past deadline dates
        try:
            deadline_dt = datetime.strptime(deadline_str, "%m/%d/%Y").date()
            if deadline_dt < today:
                logging.info(f"Pruning '{name}' due to past deadline: {deadline_str}")
                del state_data[scholarship_id]
                pruned_count += 1
        except (ValueError, TypeError):
            # If it's a different date format, we log it but don't prune unless it's a known invalid string.
            logging.debug(
                f"Could not parse deadline '{deadline_str}' for '{name}'. It will not be pruned by date."
            )

    if sanitized_count > 0:
        logging.info(f"Sanitized {sanitized_count} incomplete records from the state.")
    if pruned_count > 0:
        logging.info(f"Pruned {pruned_count} expired entries from the state.")
    if sanitized_count == 0 and pruned_count == 0:
        logging.info("No entries to sanitize or prune. State is clean.")

    return state_data


def generate_markdown_page(state_data):
    """Generates a markdown page with the full list of live scholarships."""
    live_scholarships = []
    today = datetime.now().date()

    # 1. Filter for live scholarships
    for scholarship in state_data.values():
        if not scholarship.get("Live", False):
            continue

        deadline_str = scholarship.get("Deadline", "")
        is_active = False

        # Try to parse the deadline for accurate comparison
        try:
            deadline_dt = datetime.strptime(deadline_str, "%m/%d/%Y").date()
            if deadline_dt >= today:
                is_active = True
        except ValueError:
            # If parsing fails, it's likely a non-standard deadline like "Check Link" or "N/A"
            # We'll consider these active to be safe.
            if deadline_str.lower() not in ["ended", "expired", "closed"]:
                is_active = True

        if is_active:
            live_scholarships.append(scholarship)

    # 2. Sort the data
    def sort_key(s):
        deadline_str = s.get("Deadline", "")
        # Try to parse the deadline for accurate sorting
        for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"]:
            try:
                deadline_dt = datetime.strptime(deadline_str, fmt)
                # Return a date object for comparison
                return (s.get("School", "N/A"), deadline_dt)
            except ValueError:
                pass
        # Fallback for unparseable or "N/A" deadlines: sort them last
        return (s.get("School", "N/A"), datetime.max)

    sorted_scholarships = sorted(live_scholarships, key=sort_key)

    # Group by school for rendering
    school_scholarships = {}
    for s in sorted_scholarships:
        school = s.get("School", "N/A")
        if school not in school_scholarships:
            school_scholarships[school] = []
        school_scholarships[school].append(s)

    # 3. Generate Markdown content
    md = "# Scholarship Sentinel - Live Catalog\n\n"
    md += f"Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
    md += "This page contains all currently live scholarships detected by the sentinel.\n\n"

    for school, sch_list in school_scholarships.items():
        md += f"## {school}\n\n"
        md += "| Name | Amount | Deadline |\n"
        md += "|------|--------|----------|\n"
        for s in sch_list:
            md += f"| [{s.get('Name', 'N/A')}]({s.get('Link', '#')}) | {s.get('Amount', 'N/A')} | {s.get('Deadline', 'N/A')} |\n"
        md += "\n"

    return md


def load_user_agents():
    """Loads a list of User-Agent strings from the config file."""

    ua_file = SCRIPT_DIR.parent / "config" / "user_agents.json"

    try:
        with open(ua_file, "r") as f:
            return json.load(f)

    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"Could not load user agents file: {e}. Using a default.")

        return [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]


USER_AGENTS = load_user_agents()


def get_random_headers():
    """Returns a dictionary of headers with a randomized User-Agent."""

    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
    }


# --- MAIN LOGIC ---


def scan_opportunities():
    """Orchestrates the scraping of all university portals using keyword search."""
    seen_history = load_state()
    # Run sanitization and pruning pre-flight check on existing data
    seen_history = sanitize_and_prune_state(seen_history)

    current_scan_results = {}

    new_findings = []

    updated_findings = []

    for school_name, base_url in TARGETS.items():
        logging.info(f"Starting Scan of {school_name}...")

        parsed_base_url = urlparse(base_url)

        base_link = f"{parsed_base_url.scheme}://{parsed_base_url.netloc}"

        for keyword in KEYWORDS:
            logging.info(f"Searching for keyword: '{keyword}'")

            for page_num in range(1, 100):  # Loop through a large number of pages
                try:
                    # Get fresh, random headers for each request

                    headers = get_random_headers()

                    params = {"utf8": "✓", "term": keyword, "page": page_num}

                    response = requests.get(
                        base_url, headers=headers, timeout=15, params=params
                    )

                    if response.status_code == 404:
                        logging.warning(
                            f"Page {page_num} not found for keyword '{keyword}'. Ending scan."
                        )

                        break

                    if response.status_code != 200:
                        logging.error(
                            f"Error fetching page {page_num} for keyword '{keyword}': {response.status_code}"
                        )

                        break

                    soup = BeautifulSoup(response.text, "html.parser")

                    scholarship_items = soup.select(".grid-item")

                    # Gracefully handle pages with no results

                    if not scholarship_items:
                        if soup.find(
                            text=re.compile("No opportunities matched your search")
                        ):
                            logging.info(
                                f"No results for '{keyword}' on page {page_num}. Moving to next keyword."
                            )

                        else:
                            logging.warning(
                                f"No scholarship items found on page {page_num} for '{keyword}'. Ending scan for this keyword."
                            )

                        break

                    scholarships_found_on_page = False

                    for item in scholarship_items:
                        name_tag = item.find("a")

                        if not name_tag:
                            continue

                        scholarships_found_on_page = True

                        name = clean_text(name_tag.get_text())

                        raw_href = name_tag.get("href", "")

                        link = (
                            raw_href
                            if raw_href.startswith("http")
                            else f"{base_link}{raw_href}"
                        )

                        dl_element = item.find("dl")

                        deadline = "N/A"

                        award_amount = "N/A"

                        if dl_element:
                            for dt in dl_element.find_all("dt"):
                                if dt.get_text(strip=True) == "Deadline":
                                    dd = dt.find_next_sibling("dd")

                                    if dd:
                                        deadline = clean_text(dd.get_text())

                                elif dt.get_text(strip=True) == "Award":
                                    dd = dt.find_next_sibling("dd")

                                    if dd:
                                        award_amount = clean_text(dd.get_text())

                        live = is_opportunity_live(deadline)

                        current_est_time = get_eastern_time()

                        slug = link.split("/")[-1]

                        scholarship_id = f"{school_name}_{slug}"

                        first_seen = seen_history.get(scholarship_id, {}).get(
                            "First_Seen", current_est_time
                        )

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
                            "Deadline_Updated_At": None,
                        }

                        current_scan_results[scholarship_id] = scholarship_data

                        if scholarship_id not in seen_history:
                            logging.warning(f"NEW {school_name} TARGET: {name}")

                            new_findings.append(scholarship_data)

                        else:
                            previous_deadline = seen_history[scholarship_id].get(
                                "Deadline"
                            )

                            if previous_deadline and previous_deadline != deadline:
                                logging.warning(
                                    f"DEADLINE CHANGED for {name}: {previous_deadline} -> {deadline}"
                                )

                                scholarship_data["Previous_Deadline"] = (
                                    previous_deadline
                                )

                                scholarship_data["Deadline_Updated_At"] = (
                                    current_est_time
                                )

                                updated_findings.append(scholarship_data)

                            else:
                                logging.info(f"Existing {school_name}: {name}")

                    if not scholarships_found_on_page:
                        logging.warning(
                            f"No valid scholarship data on page {page_num}. Ending scan for '{keyword}'."
                        )

                        break

                    time.sleep(random.uniform(1.0, 2.5))

                except (requests.exceptions.RequestException, ConnectionError) as e:
                    logging.error(
                        f"Network Error on {school_name} page {page_num} for '{keyword}': {e}"
                    )

                    break

                except Exception as e:
                    logging.error(f"Unexpected Error during scan: {e}")

                    break

        logging.info(f"Finished keyword searches for {school_name}.")

    # Add new findings to the history before saving
    seen_history.update(current_scan_results)
    save_state(seen_history)

    # Generate and save the markdown page with all live scholarships

    logging.info("Generating new markdown page for GitHub...")

    markdown_content = generate_markdown_page(seen_history)

    with open("docs/index.md", "w", encoding="utf-8") as f:
        f.write(markdown_content)

    if current_scan_results:
        try:
            # Write the updated, clean data to the CSV

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
                    "Deadline_Updated_At",
                    "Previous_Deadline",
                ]

                writer = csv.DictWriter(f, fieldnames=fieldnames)

                writer.writeheader()

                writer.writerows(seen_history.values())

        except IOError as e:
            logging.error(f"Could not export CSV: {e}")

    logging.info(f"Scan Complete. {len(new_findings)} new targets identified.")

    all_findings = new_findings + updated_findings

    return all_findings


if __name__ == "__main__":
    all_findings = scan_opportunities()
    if all_findings:
        linkedin_main(all_findings)
