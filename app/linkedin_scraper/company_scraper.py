from typing import Optional
from apify_client import ApifyClient
from dotenv import load_dotenv
import os 

# Load environment variables & initialise client
load_dotenv()
client = ApifyClient(os.getenv("APIFY_API_TOKEN"))


def scrape_linkedin_company(
    company_url: str, 
    max_employees: Optional[int] = None, 
    job_title: Optional[str] = None, 
    batch_name: Optional[str] = "batch"):
  """
    Scrape a linkedin company's employee list, returning max_employees amount 
    who has got job_title
  """

  # Initialising run input
  run_input = {
    "identifier": company_url
  }

  if max_employees is not None:
    run_input["max_employees"] = max_employees

  if job_title is not None:
    run_input["job_title"] = job_title

  print(f"Starting batch: {batch_name}")
  print(f"Max profiles to fetch: {max_employees}")

  # Run the actor
  print("Starting the scraper...")
  run = client.actor("apimaestro/linkedin-company-employees-scraper-no-cookies").call(run_input=run_input)

  #Get the results
  print("Scraping completed. Fetching results...")
  items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
  
  return items