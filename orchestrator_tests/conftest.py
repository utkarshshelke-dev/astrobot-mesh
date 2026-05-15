"""Shared fixtures and env setup for orchestrator tests."""
import os
import sys
sys.path.insert(0, os.path.expanduser("~/astrobot_mesh"))

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
os.environ.setdefault("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
os.environ.setdefault("ANALYTICS_MODE", "json")
os.environ.setdefault("PA_AGENT_ENDPOINT", "https://persona-aggregator-agent-866797370377.us-central1.run.app")
