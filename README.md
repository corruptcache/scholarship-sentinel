Scholarship Sentinel: Open Source Grant Intelligence 🛡️

"Financial aid isn't a scarcity problem; it's a visibility problem."

Scholarship Sentinel is an automated Open Source Intelligence (OSINT) architecture designed to democratize access to workforce development funding. By monitoring institutional databases 24/7, it eliminates the "information asymmetry" that keeps students in debt.

🏗️ The Architecture

Most students check scholarship portals once a semester. This system runs a sentinel every morning.

This project uses a Serverless CI/CD Pipeline (GitHub Actions) to execute a specialized intelligence sweep:

The Sentinel: Monitors the AcademicWorks portals for CPCC and UNCC. It uses behavioral analysis (timestamp tracking) to detect "Zombie Grants"—funds re-listed mid-semester that human observers miss.

The Signal: When new funding is detected, the system pipes a rich-text payload to a Discord Webhook (Real-time).

The Community: A secondary bot formats the intelligence into a LinkedIn update to inform the wider student body.

Data Flow

graph LR
    A[GitHub Action Cron] --> B[Uni Scraper]
    B -->|Scrape| C[CPCC/UNCC Portal]
    
    B --> F{State Analysis}
    F -->|Compare| G[scholarship_state.json]
    
    G -->|New Loot?| H[Notification Layer]
    H -->|Real-time| I[Discord Webhook]
    H -->|Community| J[LinkedIn Bot]
    
    G -->|Persistence| K[Commit to Repo]


🛠️ The Toolkit

This repository contains distinct modules for targeted intelligence gathering:

Module

Target

Technique

uni_scraper.py

CPCC & UNCC

BeautifulSoup scraping of Blackbaud portals. Features Timezone-Adjusted Timestamping to track administrative schedules.

linkedin_poster.py

Social Signal

Automates community distribution via the LinkedIn UGC API.

🧪 Testing & Integration

To verify connectivity and formatting without waiting for the daily cron job, use the included test scripts:

Script

Purpose

test_discord_alert.py

Simulates a scholarship detection to verify Discord Webhook connectivity and embed styling.

test_linkedin_post.py

Injects mock data into the local state and generates a preview of the LinkedIn post. Optionally posts to your feed.

🚀 Deployment

Option 1: The "Serverless" Method (Recommended)

This project is optimized for GitHub Actions. You do not need a server.

Fork this Repository.

Configure Secrets: Go to Settings -> Secrets and variables -> Actions and add:

DISCORD_WEBHOOK_URL: Your Discord Webhook.

LINKEDIN_ACCESS_TOKEN: Your LinkedIn API access token.

Enable the Workflow: Go to the "Actions" tab and enable the scan.

Done: The bot will now run every morning at 08:00 UTC.

Option 2: Local Execution (Home Lab)

To run this on your own machine (or Raspberry Pi):

# 1. Clone the repo
git clone [https://github.com/corruptcache/scholarship-sentinel.git](https://github.com/corruptcache/scholarship-sentinel.git)

# 2. Install Dependencies
pip install -r requirements.txt

# 3. Set Environment Variables (.env file)
# DISCORD_WEBHOOK_URL=[https://discord.com/api/webhooks/](https://discord.com/api/webhooks/)...

# 4. Run the Scanner
python uni_scraper.py


📊 Sample Output

The "New Grant" Alert (Discord)

The bot detects a grant added at 4:45 PM on a Friday.

⚖️ Ethical Design

This tool is designed with Responsible Automation principles:

Rate Limiting: All scripts include time.sleep() delays to prevent server load.

Passive Recon: The GitHub Action runs only once per day, respecting standard robots.txt crawl frequencies.

Public Benefit: The data collected is not sold or gated. It is open-sourced to improve financial literacy for the student community.

📄 License

This project is open-source under the MIT License.
Built for the Cyber Community. 2026.
