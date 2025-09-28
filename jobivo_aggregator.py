"""
jobivo_aggregator.py - Simple FastAPI service to serve job listings for Jobivo

This aggregator provides a set of endpoints to retrieve job offers, save an offer and
hide an offer. It's intended to be run on Render with a command like:

    uvicorn jobivo_aggregator:app --host 0.0.0.0 --port $PORT

Environment variables:
  ALLOWED_ORIGINS: a comma-separated list of domains allowed by CORS.

The service stores saved/hidden job IDs in memory for demonstration purposes. It
returns up to 10 active offers at `/offers` and prevents showing saved or
hidden offers for 90 days.
"""
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict

# Determine allowed origins from environment variable
allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")]

app = FastAPI(title="Jobivo Aggregator")

# Enable CORS middleware with allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for jobs, and for saved/hidden job IDs with timestamps
# These fake jobs simulate results from multiple sources. Each job includes an
# identifier, title, company name, location, description, source and url.
_fake_jobs: List[Dict] = [
    {
        "id": f"job-{i}",
        "title": f"Sample Job {i}",
        "company": "ExampleCorp",
        "location": "Zurich",
        "description": "This is a sample job offer.",
        "source": "demo",
        "url": f"https://example.com/job-{i}",
    }
    for i in range(1, 21)
]

# Keep track of when jobs are saved or hidden so they can be filtered out for 90 days
_saved_jobs: Dict[str, datetime] = {}
_hidden_jobs: Dict[str, datetime] = {}

class JobOffer(BaseModel):
    """
    Job offer returned to the UI. The `source` field identifies which portal
    the job came from and `url` points to the original job listing.
    """
    id: str
    title: str
    company: str
    location: str
    description: str
    source: str
    url: str

class SaveHideResponse(BaseModel):
    message: str

@app.get("/", tags=["Health"])
def read_root():
    return {"message": "Jobivo Aggregator is running."}

@app.get("/offers", response_model=List[JobOffer], tags=["Offers"])
def list_offers(limit: int = 10):
    """
    Retrieve up to `limit` active job offers.
    Excludes offers saved or hidden in the last 90 days.
    This endpoint is primarily for backward‑compatibility. The newer `/search`
    endpoint should be used by the UI for queries.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=90)
    # Remove expired entries from saved/hidden tracking
    for job_dict in (_saved_jobs, _hidden_jobs):
        expired_ids = [job_id for job_id, ts in job_dict.items() if ts < cutoff]
        for job_id in expired_ids:
            del job_dict[job_id]
    available = [job for job in _fake_jobs if job["id"] not in _saved_jobs and job["id"] not in _hidden_jobs]
    return available[:limit]

@app.get("/search", response_model=List[JobOffer], tags=["Offers"])
def search_offers(q: str = "", loc: str = "", radius: int = 0, pensum: str = "", limit: int = 10):
    """
    Perform a simple search over the fake jobs list.

    - **q**: query string to match against title or description (case insensitive)
    - **loc**: location filter; if provided, only jobs containing this location
      string (case insensitive) will be returned.
    - **radius** and **pensum** are accepted for API compatibility but ignored
      in this simple implementation.
    - **limit**: maximum number of jobs to return.

    Returns a list of JobOffer objects excluding any that have been saved or
    hidden in the last 90 days.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=90)
    # Clean up expired saved/hidden entries
    for job_dict in (_saved_jobs, _hidden_jobs):
        expired_ids = [job_id for job_id, ts in job_dict.items() if ts < cutoff]
        for job_id in expired_ids:
            del job_dict[job_id]
    # Filter jobs based on query and location
    def matches(job: Dict) -> bool:
        if job["id"] in _saved_jobs or job["id"] in _hidden_jobs:
            return False
        if q and q.lower() not in (job["title"].lower() + " " + job["description"].lower()):
            return False
        if loc and loc.lower() not in job["location"].lower():
            return False
        return True
    filtered = [job for job in _fake_jobs if matches(job)]
    return filtered[:limit]

@app.post("/save", response_model=SaveHideResponse, tags=["Offers"])
def save_offer(payload: JobOffer):
    """
    Mark a job offer as saved. Expects a JSON body matching `JobOffer`.
    The job will not appear in search results for 90 days.
    """
    job_id = payload.id
    # ensure the job exists in fake data or accept unknown ids
    _saved_jobs[job_id] = datetime.utcnow()
    return SaveHideResponse(message="Job saved successfully")

@app.post("/hide", response_model=SaveHideResponse, tags=["Offers"])
def hide_offer(payload: JobOffer):
    """
    Mark a job offer as hidden. Expects a JSON body matching `JobOffer`.
    The job will not appear in search results for 90 days.
    """
    job_id = payload.id
    _hidden_jobs[job_id] = datetime.utcnow()
    return SaveHideResponse(message="Job hidden successfully")
