"""Settings shared by the app and the offline tools.

Everything here comes from the A5 Conductor Brief: the competitive set and the
three sources (Part 3), the thresholds (Parts 4-5) and the A4 models.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERIFIED_DIR = ROOT / "data" / "verified"
LABELS_DIR = ROOT / "data" / "classified"
SAMPLES_DIR = ROOT / "samples"

BRANDS = ["Databricks", "Snowflake", "Google BigQuery", "Microsoft Fabric"]
BRAND_PREFIX = {"Databricks": "DBX", "Snowflake": "SNOW", "Google BigQuery": "BQ", "Microsoft Fabric": "FAB"}

# What the classifier treats as each company's core areas when it scores a threat.
# The Databricks line is word for word the A4 prompt, so the A4 labels stay comparable.
CORE_AREAS = {
    "Databricks": "AI/agents, lakehouse, data engineering",
    "Snowflake": "AI/agents, cloud data warehouse, data sharing and apps",
    "Google BigQuery": "AI/agents, serverless data warehouse, analytics on Google Cloud",
    "Microsoft Fabric": "AI/Copilot, unified analytics with Power BI, OneLake",
}

# source_type -> (short label, folder under data/verified)
SOURCES = {
    "news": ("Press coverage", "google_news"),
    "official_blog": ("Company blogs", "official_blogs"),
    "developer_forum": ("Developer forums", "hacker_news"),
}

THEMES = {
    "ai_agents": "AI & agents",
    "data_platform": "Data platform & lakehouse",
    "analytics_bi": "Analytics & BI",
    "data_engineering": "Data engineering",
    "governance_security": "Governance & security",
    "performance_cost": "Performance & cost",
    "partnerships_ecosystem": "Partners & ecosystem",
    "funding_business": "Funding & business",
    "developer_experience": "Developer experience",
    "other": "Other",
}
SENTIMENTS = ["positive", "neutral", "negative"]

# The A3 snapshot every brief is built from (A3 run 20260928T061721).
SNAPSHOT_RUN = "20260928T061721"
SNAPSHOT_DATE = "2026-09-28"
TIMEZONE = "America/Los_Angeles"

CLASSIFIER_MODEL = os.getenv("MADISON_CLASSIFIER_MODEL", "gpt-4.1-mini")
STRATEGIST_MODEL = os.getenv("MADISON_STRATEGIST_MODEL", "gpt-4.1")
CLASSIFIER_BATCH = 10

# Data-contract thresholds (Conductor Brief Parts 3-5).
HN_MIN_THREADS = 5            # below this, no developer-sentiment claims for a brand
BLOG_MIN_SPAN_DAYS = 14       # a company's own posts should cover at least two weeks
MIN_FOCUS_RECORDS = 3         # three "why we win" points need something to stand on
MIN_COMPETITOR_RECORDS = 2
NEAR_DUPLICATE_RATIO = 0.9
TOP_EVIDENCE = 8              # records per brand handed to the strategist

# Guard rails for a public demo that spends real API money.
QUESTION_MAX_CHARS = 300
UPLOAD_MAX_ROWS = 100
UPLOAD_MAX_BYTES = 2_000_000
DAILY_RUN_LIMIT = int(os.getenv("MADISON_DAILY_RUN_LIMIT", "150"))
HOURLY_RUNS_PER_VISITOR = int(os.getenv("MADISON_HOURLY_RUNS_PER_VISITOR", "12"))
