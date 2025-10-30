"""LinkedIn company employee scraping using Apify API."""

import os
from typing import Optional, List, Dict, Any

from apify_client import ApifyClient
from dotenv import load_dotenv

# Load environment variables and initialize Apify client
load_dotenv()
client = ApifyClient(os.getenv("APIFY_API_TOKEN"))


def scrape_linkedin_company(
    company_url: str,
    max_employees: Optional[int] = None,
    job_title: Optional[str] = None,
    batch_name: Optional[str] = "batch"
) -> List[Dict[str, Any]]:
    """Scrape employee list from a LinkedIn company page.

    Args:
        company_url: LinkedIn company page URL.
        max_employees: Maximum number of employee profiles to scrape.
        job_title: Filter employees by job title (case-insensitive substring match).
        batch_name: Optional name for this scraping batch (for logging).

    Returns:
        List of dictionaries containing employee profile information.
        Each dict includes "profile_url" and other employee details.

    Raises:
        Exception: If Apify actor fails or API token is invalid.

    Note:
        Requires APIFY_API_TOKEN environment variable to be set.
    """
    run_input = {
        "identifier": company_url
    }

    if max_employees is not None:
        run_input["max_employees"] = max_employees

    if job_title is not None:
        run_input["job_title"] = job_title

    print(f"Starting batch: {batch_name}")
    print(f"Max profiles to fetch: {max_employees}")

    print("Starting the scraper...")
    actor_run = client.actor(
        "apimaestro/linkedin-company-employees-scraper-no-cookies"
    ).call(run_input=run_input)

    print("Scraping completed. Fetching results...")
    employee_items = list(client.dataset(actor_run["defaultDatasetId"]).iterate_items())

    return employee_items
