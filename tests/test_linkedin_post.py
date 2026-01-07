import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 1. LOAD ENV (Crucial for local testing)
try:
    from dotenv import load_dotenv

    script_dir = Path(__file__).parent
    dotenv_path = script_dir.parent / ".env"
    load_dotenv(dotenv_path=dotenv_path)
except ImportError:
    pass

# 2. IMPORT BOT LOGIC
try:
    import linkedin_poster
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import linkedin_poster


def run_test():
    print("[*] Starting LinkedIn Integration Test...")

    # 3. VERIFY KEYS
    if not os.getenv("LINKEDIN_ACCESS_TOKEN"):
        print("[!] WARNING: LINKEDIN_ACCESS_TOKEN is missing from .env")
        return

    # 4. Create Mock "Fresh" Data
    mock_data = {
        "TEST_ENTRY_001": {
            "Name": "Sentinel Connectivity Test Grant",
            "Amount": "$13,337",
            "Deadline": "2026-12-31",
            "Link": "https://github.com/corruptcache/scholarship-sentinel",
            "Match_Reason": "Integration Test",
            "First_Seen": datetime.now().isoformat(),
            "School": "TEST_LAB",
        }
    }

    # Define the path to the state file
    state_file_path = "data/scholarship_state.json"
    os.makedirs("data", exist_ok=True)

    # Backup existing state
    backup_state = None
    if os.path.exists(state_file_path):
        with open(state_file_path, "r") as f:
            backup_state = f.read()

    # Write Mock Data
    with open(state_file_path, "w") as f:
        json.dump(mock_data, f)

    print(f"[*] Injected mock data into {state_file_path}")

    try:
        # 5. Refresh Module Globals (in case env loaded after import)
        linkedin_poster.LINKEDIN_ACCESS_TOKEN = os.getenv(
            "LINKEDIN_ACCESS_TOKEN", ""
        ).strip()
        linkedin_poster.LINKEDIN_USER_ID = os.getenv("LINKEDIN_USER_ID", "").strip()

        # 6. Run the logic
        loot = linkedin_poster.get_fresh_loot()

        if not loot:
            print("[!] Logic Error: No fresh loot found despite injection.")
            return

        print(f"[*] Detected {len(loot)} fresh items.")
        post_body = linkedin_poster.format_linkedin_post(loot)

        print("\n" + "=" * 40)
        print("PREVIEW OF LINKEDIN POST:")
        print("=" * 40)
        print(post_body)
        print("=" * 40 + "\n")

        # 7. Interactive Send
        confirm = input("Do you want to actually post this to LinkedIn? (y/N): ")
        if confirm.lower() == "y":
            # NO FETCHING. DIRECT ENV LOOKUP.
            user_urn = linkedin_poster.resolve_user_urn()

            if user_urn:
                linkedin_poster.post_to_linkedin(post_body, user_urn)
            else:
                print("[!] Could not find User URN in .env. Aborting post.")
        else:
            print("[*] Post skipped.")

    finally:
        # 8. Cleanup
        if backup_state:
            with open(state_file_path, "w") as f:
                f.write(backup_state)
            print(f"[*] Restored original {state_file_path}")
        else:
            if os.path.exists(state_file_path):
                os.remove(state_file_path)
                print(f"[*] Cleaned up mock state file at {state_file_path}.")


if __name__ == "__main__":
    run_test()
