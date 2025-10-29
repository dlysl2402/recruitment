from supabase import create_client, Client
import os 
from dotenv import load_dotenv

load_dotenv()

supabase: Client = create_client(
  os.environ.get("SUPABASE_URL"),
  os.environ.get("SUPABASE_KEY")
)