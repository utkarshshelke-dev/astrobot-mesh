# orchestrator/__init__.py
"""Astro.bot Orchestrator package."""
import os
from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

from . import agent  # ← ADK eval needs module.agent.root_agent

__all__ = ["agent"]
