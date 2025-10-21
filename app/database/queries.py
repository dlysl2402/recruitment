from app.database.client import supabase
from app.database.models import Candidate

def insert_candidate(candidate_data):
  return supabase.table('candidates').insert(candidate_data).execute()

def get_all_candidates():
  return supabase.table('candidates').select("*").execute()



def insert_benchmark_job(job_data):
  return supabase.table('benchmark_jobs').insert(job_data).execute()

def get_all_benchmark_jobs():
  return supabase.table('benchmark_jobs').select("*").execute()

def get_benchmark_job_by_title(title):
  return supabase.table('benchmark_jobs').select("*").eq('title', title).execute()