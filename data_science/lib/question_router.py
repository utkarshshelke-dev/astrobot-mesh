"""
Deterministic question router.

Matches a user question to the correct table (performance / pacing / etc)
based on the `applicable_questions` keyword lists in each table's config.

This replaces LLM guesswork on "which table should I query for this?"
"""

from typing import Optional
from .channel_resolver import get_client, load_config_v3


def route_question_to_table(
    question: str,
    client_id: str,
    config: Optional[dict] = None,
    default_table_id: str = "performance",
) -> dict:
    """
    Match user question to the best-fit table based on applicable_questions keywords.

    Returns dict with:
      - table_id: str
      - table_full_path: str
      - rules: list[str]
      - channel_column: str
      - matched_keywords: list[str]
      - confidence: 'high' | 'medium' | 'low' | 'default'
    """
    client = get_client(client_id, config)
    q_lower = question.lower().strip()
    # Tokenize to handle "budget is remaining" → matches "budget remaining"
    q_tokens = set(q_lower.replace("?", " ").replace(",", " ").split())

    def keyword_matches(kw: str, text: str, tokens: set) -> bool:
        kw_l = kw.lower()
        if kw_l in text:
            return True
        # Multi-word keyword: all words must appear in tokens
        kw_words = kw_l.split()
        if len(kw_words) > 1 and all(w in tokens for w in kw_words):
            return True
        return False

    scored = []
    for table in client["tables"]:
        keywords = table.get("applicable_questions", [])
        matched = [kw for kw in keywords if keyword_matches(kw, q_lower, q_tokens)]
        if matched:
            scored.append((table, matched, len(matched)))

    if not scored:
        # fall back to default
        default_table = next(
            (t for t in client["tables"] if t["table_id"] == default_table_id),
            client["tables"][0],
        )
        return {
            "table_id": default_table["table_id"],
            "table_full_path": default_table["table_full_path"],
            "rules": list(default_table.get("rules", [])),
            "channel_column": default_table.get("channel_column", "Channel"),
            "matched_keywords": [],
            "confidence": "default",
            "enabled": default_table.get("enabled", True),
        }

    # Sort: most matches wins
    scored.sort(key=lambda x: x[2], reverse=True)
    best_table, matched, score = scored[0]

    if score >= 3:
        confidence = "high"
    elif score == 2:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "table_id": best_table["table_id"],
        "table_full_path": best_table["table_full_path"],
        "rules": list(best_table.get("rules", [])),
        "channel_column": best_table.get("channel_column", "Channel"),
        "matched_keywords": matched,
        "confidence": confidence,
        "enabled": best_table.get("enabled", True),
    }


def get_applicable_rules(client_id: str, table_id: str, config: Optional[dict] = None) -> list[dict]:
    """
    Return list of {rule_id, description} for all rules applicable to this table.
    Combines table-level rules and global all_tables rules.
    """
    config = config or load_config_v3()
    client = get_client(client_id, config)
    table = next(
        (t for t in client["tables"] if t["table_id"] == table_id),
        None,
    )
    if not table:
        return []

    rule_defs = config.get("_global_rules", {}).get("rule_definitions", {})
    global_rules = config.get("_global_rules", {}).get("all_tables", [])

    rule_ids = list(global_rules) + list(table.get("rules", []))
    # Dedupe preserving order
    seen = set()
    ordered = []
    for r in rule_ids:
        if r not in seen:
            seen.add(r)
            ordered.append(r)

    return [
        {"rule_id": r, "description": rule_defs.get(r, "(no description)")}
        for r in ordered
    ]