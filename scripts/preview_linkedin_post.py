import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# --- PATH SETUP ---
# Add the project root to the Python path to allow importing from 'alerts'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from alerts.linkedin_alert import create_post_text

STATE_FILE = os.path.join(project_root, "data", "scholarship_state_search.json")


def get_mock_data():
    """Returns a list of dummy scholarship data for testing."""
    now = datetime.now(timezone.utc)
    future_deadline_1 = (now + timedelta(days=7)).strftime("%m/%d/%Y")
    future_deadline_2 = (now + timedelta(days=14)).strftime("%m/%d/%Y")
    future_deadline_3 = (now + timedelta(days=21)).strftime("%m/%d/%Y")

    return [
        {
            "School": "University of Mocking",
            "Name": "The Early Bird Scholarship (New)",
            "Amount": "$1,000",
            "Deadline": future_deadline_1,
            "Link": "#",
            "First_Seen": now.isoformat(),
        },
        {
            "School": "Test State University",
            "Name": "Advanced Procrastinator's Grant (Updated)",
            "Amount": "$2,500",
            "Deadline": future_deadline_3,
            "Link": "#",
            "Deadline_Updated_At": now.isoformat(),
            "Previous_Deadline": (now + timedelta(days=1)).strftime("%m/%d/%Y"),
        },
        {
            "School": "University of Mocking",
            "Name": "Steady Eddie Award",
            "Amount": "$500",
            "Deadline": future_deadline_2,
            "Link": "#",
        },
        {
            "School": "Data Science Institute",
            "Name": "The Data Wrangler's Prize",
            "Amount": "Full Tuition",
            "Deadline": future_deadline_1,
            "Link": "#",
        },
    ]


def load_live_data():
    """Loads all live scholarships from the state file."""
    if not os.path.exists(STATE_FILE):
        print("Warning: State file not found. No live data to preview.")
        return []
    try:
        with open(STATE_FILE, "r") as f:
            state_data = json.load(f)

        # Simulate "fresh loot" by taking all live items
        live_loot = [
            item
            for item in state_data.values()
            if item.get("Live") and item.get("Deadline") != "Ended"
        ]
        return live_loot
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading state file: {e}")
        return []


def main():
    """Main function to generate and print the LinkedIn post preview."""
    parser = argparse.ArgumentParser(
        description="Generate a preview of the LinkedIn scholarship post."
    )
    parser.add_argument(
        "--live-data",
        action="store_true",
        help="Use live data from the state file instead of mock data.",
    )
    args = parser.parse_args()

    if args.live_data:
        print("--- [Using LIVE data from state file] ---")
        scholarship_data = load_live_data()
    else:
        print("--- [Using MOCK test data] ---")
        scholarship_data = get_mock_data()

    if not scholarship_data:
        print("\nNo scholarship data available to generate a preview.")
        return

    # Generate the post text
    post_body = create_post_text(scholarship_data)
    char_count = len(post_body)

    # Print the preview
    print("\n" + "--- [LINKEDIN POST PREVIEW START] ---" + "\n")
    print(post_body)
    print("--- [LINKEDIN POST PREVIEW END] ---" + "\n")
    print(f"Total Character Count: {char_count} (LinkedIn limit is 3000)")


if __name__ == "__main__":
    main()
