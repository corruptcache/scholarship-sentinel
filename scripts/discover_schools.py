import json
import logging

import requests

# --- CONFIGURATION ---
DOMAIN = "academicworks.com"
OUTPUT_FILE = "discovered_schools.json"

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def discover_subdomains():
    """
    Uses Certificate Transparency logs via crt.sh to discover subdomains.
    """
    logging.info(
        f"Querying Certificate Transparency logs for subdomains of '{DOMAIN}'..."
    )
    url = f"https://crt.sh/?q=%.{DOMAIN}&output=json"
    subdomains = set()

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes

        data = response.json()

        for entry in data:
            # The 'name_value' often contains the full FQDN
            name = entry.get("name_value", "")
            # Sometimes there are multiple domains in one entry, separated by newlines
            names = name.split("\\n") if isinstance(name, str) else [name]
            for sub in names:
                if sub.endswith(f".{DOMAIN}") and not sub.startswith("*"):
                    subdomains.add(sub.strip())

        logging.info(f"Found {len(subdomains)} unique subdomains.")
        return list(subdomains)

    except requests.exceptions.RequestException as e:
        logging.error(f"Error querying crt.sh: {e}")
        return []
    except json.JSONDecodeError:
        logging.error(
            "Failed to decode JSON response from crt.sh. The service might be down or returned an unexpected response."
        )
        return []


def format_for_config(subdomains):
    """
    Formats the list of subdomains into a dictionary suitable for config/schools.json.
    """
    logging.info("Formatting discovered subdomains for the config file...")
    school_config = {}
    # Exclude common non-school keywords to improve the quality of the output
    exclude_list = [
        "www",
        "mail",
        "support",
        "help",
        "demo",
        "sandbox",
        "staging",
        "test",
        "ftp",
        "cpanel",
    ]

    for sub in sorted(subdomains):
        # Create a user-friendly name from the subdomain
        subdomain_part = sub.split(".")[0]

        if subdomain_part.lower() in exclude_list:
            logging.info(f"Excluding common subdomain: {sub}")
            continue

        school_key = subdomain_part.upper()

        # In case of more complex subdomains like "my.school.academicworks.com"
        # we can make the key more descriptive.
        if len(school_key) <= 2:  # Often short names are part of a larger name
            parts = sub.split(".")
            if len(parts) > 2:
                school_key = "-".join(parts[:-2]).upper()

        url = f"https://{sub}/opportunities"
        school_config[school_key] = url

    return school_config


def main():
    """
    Main function to discover, format, and save school URLs.
    """
    print("--- Starting School Discovery via Certificate Transparency ---")

    subdomains = discover_subdomains()

    if not subdomains:
        print(
            "\nNo subdomains were discovered. This could be a temporary issue with the CT log service."
        )
        print("Please try again later.")
        return

    formatted_schools = format_for_config(subdomains)

    try:
        with open(OUTPUT_FILE, "w") as f:
            json.dump(formatted_schools, f, indent=4)
        logging.info(
            f"Successfully saved {len(formatted_schools)} schools to '{OUTPUT_FILE}'."
        )

        print("\n--- Discovery Complete! ---")
        print(f"\n1. Open the newly created '{OUTPUT_FILE}' file.")
        print(
            "2. Review the list and remove any 'test', 'sandbox', 'staging', or otherwise unwanted domains."
        )
        print("3. Copy the desired entries from the file.")
        print("4. Paste them into your main 'config/schools.json' file.")
        print("\nThis process ensures your main config remains clean and curated.")

    except IOError as e:
        logging.error(f"Failed to write to output file '{OUTPUT_FILE}': {e}")


if __name__ == "__main__":
    main()
