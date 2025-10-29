from urllib.parse import urlparse, unquote
from apify_client import ApifyClient
from dotenv import load_dotenv
import os 

# Load environment variables & initialise client
load_dotenv()
client = ApifyClient(os.getenv("APIFY_API_TOKEN"))

def extract_linkedin_username(url: str) -> str:
  """ 
    Extracts the username from a LinkedIn profile URL
    Works with www, without www, and with query params
  """
  parsed = urlparse(url)

  # Ensure it's a LinkedIn profile path
  if parsed.netloc not in {"linkedin.com", "www.linkedin.com"}:
    raise ValueError("Not a LinkedIn URL")
  
  path = parsed.path.strip("/")

  # Profile URLs are like: /in/username
  if path.startswith("in/"):
    username = path[3:] # Remove 'in/'
    #Remove query params or fragments if any
    username = username.split("?")[0].split("#")[0]
    return unquote(username)  # Handles %20 etc.
  
  raise ValueError("Not a LinkedIn /in/ profile URL")


def scrape_linkedin_profiles(profile_urls, batch_name="batch"):
  """
    Scrape multiple linkedin profiles in one run
  """

  # Initialising run input
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