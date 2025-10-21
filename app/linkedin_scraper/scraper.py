from apify_client import ApifyClient
from dotenv import load_dotenv
import os 

# Load environment variables & initialise client
load_dotenv()
client = ApifyClient(os.getenv("APIFY_API_TOKEN"));

def scrape_linkedin_profiles(profile_urls, batch_name="batch"):
  """
    Scrape multiple linkedin profiles in one run
  """

  run_input = {
    "usernames": profile_urls, 
    "includeEmail": False
  }

  print(f"Starting batch: {batch_name}")
  print(f"Profiles to scrape: {len(profile_urls)}")

  # Run the actor
  print("Starting the scraper...")
  run = client.actor("apimaestro/linkedin-profile-full-sections-scraper").call(run_input=run_input)

  # Get the results
  print("Scraping completed. Fetching results...")
  items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

  return items