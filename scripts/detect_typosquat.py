import json
import logging
import os
import socket
import sys

# --- PATH SETUP ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# --- CONFIGURATION ---
CONFIG_FILE = os.path.join(project_root, "config", "schools.json")


def load_target_domains():
    """Loads the legitimate domains from the schools.json config file."""
    if not os.path.exists(CONFIG_FILE):
        logging.error(f"Config file not found at: {CONFIG_FILE}")
        return []

    with open(CONFIG_FILE, "r") as f:
        schools = json.load(f)

    # Extract just the hostname from the URLs
    domains = []
    for url in schools.values():
        try:
            hostname = url.split("://")[1].split("/")[0]
            domains.append(hostname)
        except IndexError:
            logging.warning(f"Could not parse domain from URL: {url}")
    return domains


def generate_permutations(domain):
    """Generates a list of potential typosquatting permutations for a domain."""
    permutations = set()
    base_name, tld = domain.rsplit(".", 1)

    # 1. Character replacement (homoglyphs)
    replacements = {"o": "0", "l": "1", "i": "l", "a": "4"}
    for char, rep in replacements.items():
        if char in base_name:
            permuted_name = base_name.replace(char, rep)
            permutations.add(f"{permuted_name}.{tld}")

    # 2. Appending common keywords
    suffixes = ["-grant", "-funding", "-scholarships", "-login", "-portal", "-aid"]
    for suffix in suffixes:
        permutations.add(f"{base_name}{suffix}.{tld}")
        # Also try with a different TLD
        permutations.add(f"{base_name}{suffix}.com")
        permutations.add(f"{base_name}{suffix}.org")

    # 3. Adding/removing hyphens
    if "-" in base_name:
        permutations.add(f"{base_name.replace('-', '')}.{tld}")
    else:
        # Add hyphen between first and second part of the name if no hyphen exists
        if "." not in base_name:  # Simple case like 'cpcc'
            # This is a simple assumption, could be improved
            if len(base_name) > 4:
                permutations.add(
                    f"{base_name[: len(base_name) // 2]}-{base_name[len(base_name) // 2 :]}.{tld}"
                )

    # 4. Different Top-Level Domain (TLD)
    common_tlds = ["com", "org", "net", "info", "co"]
    for new_tld in common_tlds:
        if tld != new_tld:
            permutations.add(f"{base_name}.{new_tld}")

    return list(permutations)


def check_domain(domain):
    """
    Performs a DNS lookup to see if a domain is registered and active.
    Returns the IP address if found, otherwise None.
    """
    try:
        ip_address = socket.gethostbyname(domain)
        return ip_address
    except socket.gaierror:
        # This error means the domain does not resolve (NXDOMAIN)
        return None


def main():
    """
    Main function to run the typosquatting detection process.
    """
    logging.info("Starting typosquatting detection script...")
    target_domains = load_target_domains()

    if not target_domains:
        logging.error("No target domains loaded. Exiting.")
        return

    total_detections = 0
    logging.info(f"Loaded {len(target_domains)} legitimate domains to check.")
    print("-" * 50)

    for domain in target_domains:
        logging.info(f"Generating and checking permutations for: {domain}")
        permutations = generate_permutations(domain)
        detections_found = 0

        for perm in permutations:
            ip = check_domain(perm)
            if ip:
                logging.warning(
                    f"[!] Potential Typosquat Detected: {perm} -> resolves to {ip}"
                )
                detections_found += 1
                total_detections += 1

        if detections_found == 0:
            logging.info(
                f"Scan for {domain} is clean. No active typosquats found in generated permutations."
            )
        print("-" * 50)

    if total_detections > 0:
        logging.warning(
            f"\nTotal potential typosquats detected: {total_detections}. Manual review is recommended."
        )
    else:
        logging.info("\nScan complete. No potential typosquats were detected.")


if __name__ == "__main__":
    main()
