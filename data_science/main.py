# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This file initializes a FastAPI application for Data Science agent
using get_fast_api_app() from ADK. Session service URI and a flag
for a web interface configured via environment variables.
It can then be run using Uvicorn, which listens on a port specified by
the PORT environment variable or defaults to 8080.
This approach offers more flexibility, particularly if you want to
embed Data Science agent within a custom FastAPI application.
It is used for Cloud Run deployment with standard gcloud run deploy command.
"""

import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging

# Load environment variables from .env file
load_dotenv()

logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)

# AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Look one directory up from main.py (so it scans the /app root)
AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# Get session service URI from environment variables
session_uri = os.getenv("SESSION_SERVICE_URI", None)

# Get Enable Web interface serving flag from environment variables
# Set web=True if you intend to serve a web interface, False otherwise
web_interface_enabled = os.getenv("SERVE_WEB_INTERFACE", "False").lower() in (
    "true",
    "1",
)

# Prepare arguments for get_fast_api_app
app_args = {"agents_dir": AGENT_DIR, "web": web_interface_enabled}

# GCS artifact service — required for multi-instance Cloud Run deployments
# Path structure: gs://bucket/{app_name}/{user_id}/{session_id}/{filename}/{version}
artifact_uri = os.getenv("ARTIFACT_SERVICE_URI", None)
if artifact_uri:
    app_args["artifact_service_uri"] = artifact_uri
    logger.log_text(
        f"Using GCS artifact service: {artifact_uri}",
        severity="INFO",
    )
else:
    logger.log_text(
        "ARTIFACT_SERVICE_URI not set. In multi-instance deployments, "
        "charts may fail to load due to instance routing.",
        severity="WARNING",
    )

# Only include session_service_uri if it's provided
if session_uri:
    app_args["session_service_uri"] = session_uri
else:
    logger.log_text(
        "SESSION_SERVICE_URI not provided. Using in-memory session service instead. "
        "All sessions will be lost when the server restarts.",
        severity="WARNING",
    )

# Create FastAPI app with appropriate arguments
app: FastAPI = get_fast_api_app(**app_args)

app.title = "data_science"
app.description = "Data Science Agent"

if __name__ == "__main__":
    # Use the PORT environment variable provided by Cloud Run, defaulting to 8080
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
