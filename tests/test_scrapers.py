import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scrapers.blackbaud_scraper import is_opportunity_live


# Test specific logic functions
def test_is_opportunity_live():
    assert is_opportunity_live("05/15/2026")
    assert not is_opportunity_live("Ended")


# TODO: Test network logic without hitting the internet
# def test_scraper_response(requests_mock):
#     # Mock the URL to return fake HTML
#     requests_mock.get("https://cpcc.academicworks.com/opportunities", text="<html>...</html>")
#
#     # Now run your scraper function (you would need to refactor scan_opportunities to accept a single URL to test easily)
#     # result = scan_opportunities_for_url("CPCC")
#     # assert result is not None
