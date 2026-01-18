import sys
from pathlib import Path

# Add the parent directory to the sys.path to allow imports from the 'alerts' module.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from alerts.discord_alert import send_summary_alert

import csv


def test_send_summary_alert():
    """
    Tests the send_summary_alert function with a realistic list of scholarships.
    """
    scholarships = []

    # Construct the full path to the CSV file
    script_dir = Path(__file__).parent
    csv_path = script_dir.parent / "data" / "scholarship_targets_search.csv"

    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        # Skip the header row
        next(reader)
        for row in reader:
            scholarships.append(
                {
                    "School": row[0],
                    "Name": row[1],
                    "Amount": row[2],
                    "Deadline": row[3],
                    "Link": row[4],
                }
            )

    send_summary_alert(scholarships)


if __name__ == "__main__":
    test_send_summary_alert()
