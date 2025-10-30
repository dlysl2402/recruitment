"""LinkedIn profile scraping using Apify API."""

import os
from urllib.parse import urlparse, unquote
from typing import List, Dict, Any

from apify_client import ApifyClient
from dotenv import load_dotenv

# Load environment variables and initialize Apify client
load_dotenv()
client = ApifyClient(os.getenv("APIFY_API_TOKEN"))


def extract_linkedin_username(url: str) -> str:
    """Extract username from a LinkedIn profile URL.

    Handles various URL formats:
    - With/without www
    - With query parameters
    - With URL encoding

    Args:
        url: Full LinkedIn profile URL.

    Returns:
        Extracted username string.

    Raises:
        ValueError: If URL is not a valid LinkedIn profile URL.

    Examples:
        >>> extract_linkedin_username("https://linkedin.com/in/johndoe")
        "johndoe"
        >>> extract_linkedin_username("https://www.linkedin.com/in/jane-smith?trk=...")
        "jane-smith"
    """
    parsed_url = urlparse(url)

    if parsed_url.netloc not in {"linkedin.com", "www.linkedin.com"}:
        raise ValueError(f"Not a LinkedIn URL: {url}")

    path = parsed_url.path.strip("/")

    if path.startswith("in/"):
        username = path[3:]  # Remove "in/" prefix
        # Remove query parameters and fragments
        username = username.split("?")[0].split("#")[0]
        return unquote(username)  # Decode URL-encoded characters

    raise ValueError(f"Not a LinkedIn /in/ profile URL: {url}")


def scrape_linkedin_profiles(
    profile_usernames: List[str],
    batch_name: str = "batch"
) -> List[Dict[str, Any]]:
    """Scrape multiple LinkedIn profiles using Apify actor.

    Args:
        profile_usernames: List of LinkedIn usernames to scrape.
        batch_name: Optional name for this scraping batch (for logging).

    Returns:
        List of dictionaries containing scraped profile data.

    Raises:
        Exception: If Apify actor fails or API token is invalid.

    Note:
        Requires APIFY_API_TOKEN environment variable to be set.
    """
    run_input = {
        "usernames": profile_usernames,
        "includeEmail": False
    }

    print(f"Starting batch: {batch_name}")
    print(f"Profiles to scrape: {len(profile_usernames)}")

    print("Starting the scraper...")
    actor_run = client.actor(
        "apimaestro/linkedin-profile-full-sections-scraper"
    ).call(run_input=run_input)

    print("Scraping completed. Fetching results...")
    scraped_items = list(client.dataset(actor_run["defaultDatasetId"]).iterate_items())

    return scraped_items
