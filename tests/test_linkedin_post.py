import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from alerts.linkedin_poster import create_post_text
from alerts.linkedin_poster import main as linkedin_main


def test_create_post_text_quick_glance():
    """Tests the quick glance logic in the post text creation."""
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

    post_text = create_post_text(scholarships)

    assert "**CPCC** - Earliest Deadline: 2027-01-10" in post_text
    assert "Test 2" in post_text
    assert "DEADLINE EXTENDED!" in post_text
    assert "**NC State**" in post_text
    assert "For the full list of 4 scholarships" in post_text


def test_linkedin_main_no_loot(requests_mock, monkeypatch):
    """Tests the main function when there are no scholarships."""
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "test_token")
    requests_mock.get("https://api.linkedin.com/v2/userinfo", text='{"sub": "123"}')

    linkedin_main([])

    # The userinfo is called, but no post is made
    assert requests_mock.call_count == 1
    assert "userinfo" in requests_mock.last_request.url


def test_linkedin_main_with_loot(requests_mock, monkeypatch):
    """Tests the main function when there are scholarships."""
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "test_token")
    requests_mock.get("https://api.linkedin.com/v2/userinfo", text='{"sub": "123"}')
    requests_mock.post("https://api.linkedin.com/rest/posts", text="ok")

    scholarships = [
        {
            "School": "CPCC",
            "Name": "Test",
            "Amount": "$1",
            "Deadline": "01/15/2027",
            "Link": "http://a.com",
        }
    ]

    linkedin_main(scholarships)

    assert requests_mock.call_count == 2
    assert "posts" in requests_mock.last_request.url
    payload = requests_mock.last_request.json()
    assert "Test" in payload["commentary"]
