import json
import logging
import os
import sys

import requests

# --- PATH SETUP ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# --- LOGGING & CONFIG ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
CONFIG_FILE = os.path.join(project_root, "config", "schools.json")
OUTPUT_FILE = os.path.join(project_root, "docs", "security_audit.json")

# --- SECURITY CHECKS ---
SECURITY_HEADERS = [
    "Content-Security-Policy",
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "X-Frame-Options",
]


def load_target_urls():
    """Loads the legitimate URLs from the schools.json config file."""
    if not os.path.exists(CONFIG_FILE):
        logging.error(f"Config file not found at: {CONFIG_FILE}")
        return []
    with open(CONFIG_FILE, "r") as f:
        schools = json.load(f)
    return list(schools.values())


def audit_headers_and_ssl(url):
    """
    Audits a single URL for SSL and security headers.
    Handles errors gracefully and uses a browser-like User-Agent.
    """
    results = {
        "url": url,
        "ssl_valid": False,
        "headers": {header: False for header in SECURITY_HEADERS},
        "error": None,
    }

    # Define a standard browser User-Agent to avoid being blocked by WAFs
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        # The timeout is crucial for handling non-responsive servers
        response = requests.head(url, timeout=10, headers=headers, allow_redirects=True)
        response.raise_for_status()

        # 1. SSL Check (implicit in requests)
        # If the request didn't throw an SSLError, the cert is trusted.
        results["ssl_valid"] = True

        # 2. Header Checks
        for header in SECURITY_HEADERS:
            if header in response.headers:
                # Basic presence check
                results["headers"][header] = True

                # More specific checks for best practices
                if (
                    header == "X-Content-Type-Options"
                    and response.headers[header].lower() != "nosniff"
                ):
                    results["headers"][header] = False
                elif header == "X-Frame-Options" and response.headers[
                    header
                ].lower() not in ["deny", "sameorigin"]:
                    results["headers"][header] = False

    except requests.exceptions.SSLError as e:
        results["error"] = f"SSL Error: {e}"
        logging.error(f"SSL validation failed for {url}.")
    except requests.exceptions.RequestException as e:
        # Handles timeouts, connection errors, etc.
        results["error"] = f"Connection Error: {e}"
        logging.error(
            f"Could not connect to {url}. It may be offline or blocking requests."
        )

    return results


def calculate_grade(audit_results):
    """Calculates a score and letter grade based on the audit results."""
    score = 0
    max_score = len(SECURITY_HEADERS) + 1  # +1 for the SSL check

    if audit_results["ssl_valid"]:
        score += 1

    for status in audit_results["headers"].values():
        if status:
            score += 1

    # Simple grading scale
    percentage = (score / max_score) * 100
    if percentage >= 90:
        grade = "A"
    elif percentage >= 75:
        grade = "B"
    elif percentage >= 60:
        grade = "C"
    elif percentage >= 40:
        grade = "D"
    else:
        grade = "F"

    return {"score": f"{score}/{max_score}", "grade": grade}


def main():
    """
    Main function to run the security audit.
    """
    logging.info("Starting portal security audit...")
    target_urls = load_target_urls()

    if not target_urls:
        logging.error("No target URLs loaded. Exiting.")
        return

    full_report = []

    print("-" * 70)

    for url in target_urls:
        print(f"Auditing: {url}")
        audit_results = audit_headers_and_ssl(url)

        if audit_results["error"]:
            print(f"  ❌ Could not complete audit. Reason: {audit_results['error']}\n")
            grade_info = {"score": "0/5", "grade": "F"}
        else:
            grade_info = calculate_grade(audit_results)
            print(
                f"  {'✅' if audit_results['ssl_valid'] else '❌'} SSL Certificate: Valid and Trusted"
            )
            for header, present in audit_results["headers"].items():
                print(f"  {'✅' if present else '❌'} Header: {header}")

        final_results = {**audit_results, **grade_info}
        full_report.append(final_results)

        print(f"\n  Score: {grade_info['score']} | Grade: {grade_info['grade']}")
        print("-" * 70)

    # Ensure the output directory exists before writing the file
    output_dir = os.path.dirname(OUTPUT_FILE)
    os.makedirs(output_dir, exist_ok=True)

    # Save the report to a JSON file
    try:
        with open(OUTPUT_FILE, "w") as f:
            json.dump(full_report, f, indent=4)
        logging.info(f"Successfully saved detailed audit report to {OUTPUT_FILE}")
    except IOError as e:
        logging.error(f"Failed to write audit report to file: {e}")


if __name__ == "__main__":
    main()
