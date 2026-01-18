import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from alerts.discord_alert import send_summary_alert

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/123/abc"


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setattr("alerts.discord_alert.DISCORD_WEBHOOK_URL", DISCORD_WEBHOOK_URL)


def test_send_summary_alert_quick_glance(requests_mock, mock_env):
    """Tests the quick glance logic in the summary alert."""
    requests_mock.post(DISCORD_WEBHOOK_URL, text="ok")

    scholarships = [
        {
            "School": "CPCC",
            "Name": "Test 1",
            "Amount": "$1",
            "Deadline": "01/15/2027",
            "Link": "http://a.com",
        },
        {
            "School": "CPCC",
            "Name": "Test 2",
            "Amount": "$2",
            "Deadline": "01/10/2027",
            "Link": "http://b.com",
        },
        {
            "School": "CPCC",
            "Name": "Test 3",
            "Amount": "$3",
            "Deadline": "01/10/2027",
            "Link": "http://c.com",
            "Previous_Deadline": "01/01/2027",
        },
        {
            "School": "NC State",
            "Name": "Test 4",
            "Amount": "$4",
            "Deadline": "02/01/2027",
            "Link": "http://d.com",
        },
    ]

    send_summary_alert(scholarships)

    assert requests_mock.call_count == 2  # one for each school

    history = requests_mock.request_history
    # The order of embeds is not guaranteed, so we check both
    if history[0].json()["embeds"][0]["title"] == "🎓 CPCC - Quick Glance":
        cpcc_payload = history[0].json()
        ncstate_payload = history[1].json()
    else:
        cpcc_payload = history[1].json()
        ncstate_payload = history[0].json()

    assert len(cpcc_payload["embeds"][0]["fields"]) == 2  # Test 2 and 3
    assert "Test 2" in cpcc_payload["embeds"][0]["fields"][0]["value"]
    assert "DEADLINE EXTENDED!" in cpcc_payload["embeds"][0]["fields"][1]["value"]

    assert ncstate_payload["embeds"][0]["title"] == "🎓 NC State - Quick Glance"
    assert len(ncstate_payload["embeds"][0]["fields"]) == 1
