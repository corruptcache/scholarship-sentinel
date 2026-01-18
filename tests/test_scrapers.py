import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scrapers.blackbaud_scraper import is_opportunity_live


# Test specific logic functions
def test_is_opportunity_live():
    assert is_opportunity_live("05/15/2026")
    assert not is_opportunity_live("Ended")
