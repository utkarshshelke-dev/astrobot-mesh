"""Analytics agent — supports two modes:
  - 'json' (default): outputs JSON spec, tools.py renders with matplotlib (fast, no sandbox)
  - 'code_interpreter': uses VertexAiCodeExecutor for advanced charts (sandboxed)
"""
import os
from google.adk.agents import Agent
from google.genai import types
from .prompts import return_instructions_analytics, return_instructions_code_interpreter



def _build_analytics_code_executor():
    """Build VertexAiCodeExecutor only if CODE_INTERPRETER_EXTENSION_NAME is set
    AND points to a real extension. Removes the broken hardcoded fallback that
    pointed to extension 866797370377 (not accessible to nc-ai-chatbot).
    """
    ext = os.getenv("CODE_INTERPRETER_EXTENSION_NAME", "").strip()
    if not ext:
        # No executor — JSON mode will be used regardless
        return None
    try:
        return VertexAiCodeExecutor(
            resource_name=ext,
            optimize_data_file=True,
            stateful=True,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"VertexAiCodeExecutor init failed ({e!r}); falling back to JSON mode."
        )
        return None

ANALYTICS_MODE = os.getenv("ANALYTICS_MODE", "json").lower()

if ANALYTICS_MODE == "code_interpreter":
    from google.adk.code_executors import VertexAiCodeExecutor
    analytics_agent = Agent(
        model=os.getenv("ANALYTICS_AGENT_MODEL", "gemini-2.5-flash"),
        name="analytics_agent",
        instruction=return_instructions_code_interpreter(),
        code_executor=_build_analytics_code_executor(),
        generate_content_config=types.GenerateContentConfig(temperature=0.0),
    )
else:
    # JSON mode — fast, in-process matplotlib via tools.py
    analytics_agent = Agent(
        model=os.getenv("ANALYTICS_AGENT_MODEL", "gemini-2.5-flash"),
        name="analytics_agent",
        instruction=return_instructions_analytics(),
        generate_content_config=types.GenerateContentConfig(temperature=0.0),
    )
