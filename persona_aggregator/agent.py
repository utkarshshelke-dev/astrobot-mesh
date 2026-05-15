# persona_aggregator/agent.py
"""
Persona Aggregator Agent — §3 Global Definition, Local Execution.

Architecture:
  - Each persona is a standalone LlmAgent sub-agent with Google Search
  - ParallelAgent runs all relevant personas simultaneously per client
  - SequentialAgent: Gather → Synthesize
  - Persona Manager synthesizes outputs into one structured recommendation
  - §3.2: Firestore junction mapping enforces per-client persona authorisation
  - §3.4: RLHF logs partitioned by Client ID — not Persona ID

Clients and their personas:
  NPI:       high_net_worth_luxury_seeker, dink_couple, legacy_family
  Venetian:  affluent_experience_seeker, group_trip_planner,
             incentive_motivated_traveler, gourmet_traveler,
             culinary_content_creator, premium_event_traveler,
             modern_family_vacationer, spontaneous_luxury_escapist,
             cultured_weekend_indulger
  WinnDixie: mallory, maria, carol, amy

All 6 ADK callbacks implemented:
  before_agent_callback — §3.2 authorisation check, ephemeral context init
  after_agent_callback  — RLHF tagging partitioned by client_id
  before_tool_callback  — persona scope validation
  after_tool_callback   — response isolation check
  before_model_callback — client context injection
  after_model_callback  — token tracking per client
"""

import logging
import os
from datetime import date
from typing import Any, Optional

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import BaseTool, ToolContext
try:
    from google.adk.tools.google_search import google_search
except ImportError:
    try:
        from google.adk.tools import google_search
    except ImportError:
        from google.genai.tools import google_search
from google.cloud import firestore
from google.genai import types

from shared.utils.config import GEMINI_MODEL, PROJECT_ID, FIRESTORE_DB

logger = logging.getLogger(__name__)

_fs: Optional[firestore.Client] = None

VALID_CLIENTS = {"NPI", "Venetian", "WinnDixie"}

_DEFAULT_CLIENT_PERSONA_MAP = {
    "NPI": [
        "high_net_worth_luxury_seeker",
        "dink_couple",
        "legacy_family",
    ],
    "Venetian": [
        "affluent_experience_seeker",
        "group_trip_planner",
        "incentive_motivated_traveler",
        "gourmet_traveler",
        "culinary_content_creator",
        "premium_event_traveler",
        "modern_family_vacationer",
        "spontaneous_luxury_escapist",
        "cultured_weekend_indulger",
    ],
    "WinnDixie": [
        "mallory",
        "maria",
        "carol",
        "amy",
    ],
}

_persona_model = os.getenv("PERSONA_AGENT_MODEL", GEMINI_MODEL)


def _get_fs() -> firestore.Client:
    global _fs
    if _fs is None:
        _fs = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB)
    return _fs


def _get_authorised_personas(client_id: str) -> list[str]:
    """§3.2: Retrieves authorised persona list from Firestore. Falls back to defaults."""
    try:
        doc = (
            _get_fs()
            .collection("persona_authorisation")
            .document(client_id)
            .get()
        )
        if doc.exists:
            personas = doc.to_dict().get("authorised_personas", [])
            if personas:
                logger.info("§3.2 Firestore auth | client=%s | personas=%s", client_id, personas)
                return personas
    except Exception as e:
        logger.warning("§3.2 Firestore lookup failed: %s — using defaults", e)
    defaults = _DEFAULT_CLIENT_PERSONA_MAP.get(client_id, [])
    logger.info("§3.2 Default auth | client=%s | personas=%s", client_id, defaults)
    return defaults


# ══════════════════════════════════════════════════════════════════════════════
# PERSONA PROMPTS — NPI
# ══════════════════════════════════════════════════════════════════════════════

def _npi_hnw_prompt() -> str:
    return """
    You are the "High-Net-Worth Luxury Seeker" persona for NPI (Nassau Paradise Island).
    You represent top-tier spenders who prioritize exclusivity, service, and prestige.
    Properties you favor: The Ocean Club, Rosewood. Least price-sensitive segment.

    WHO YOU ARE:
    Ages 25-64 (core 45+). HHI top 5-10% ($250K+). Major US hubs: NYC, Miami,
    Charlotte, Dallas, London. 3+ international trips/year.
    Booking window: 45-90 days (longer for premium suites).
    Interests: Private aviation, fine dining, yachting, wellness/spas, high-stakes gaming.

    USE GOOGLE SEARCH to research current luxury travel trends, the property, or
    anything that makes your response more grounded and authentic.

    ALWAYS RETURN:
    1) Persona verdict: [Strong fit / Partial / Weak]
    2) Key motivations (2 bullets)
    3) Likely objections (2 bullets)
    4) Best angles (3 bullets): specific hooks + wording cues
    5) Recommended channels (2-3) + why
    6) Booking window guidance + retarget cadence
    7) One example headline + one CTA (luxury tone — no discounts)
    """


def _npi_dink_prompt() -> str:
    return """
    You are the "DINK Couple (Dual Income, No Kids)" persona for NPI.
    You drive the Couples segment — social scene, nightlife, romance, aesthetics.

    WHO YOU ARE:
    Ages 25-44. HHI ~$150K. Urban centers, Northeast US, Toronto/Montreal.
    2+ trips/year, heavy long-weekender (3-4 days).
    Booking window: 15-30 days (currently compressing).
    Interests: Nightlife, mixology, fitness, adult-only pools, Insta-worthy excursions
    (Exuma pigs, Pearl Island). Canada is fastest-growing market 2026.

    USE GOOGLE SEARCH to find trending NPI experiences, Insta-worthy spots, or
    CAD-friendly angles.

    ALWAYS RETURN:
    1) Persona verdict: [Strong / Partial / Weak]
    2) Vibe score (1-10) + why (1 line)
    3) Best creative directions (3 bullets): scene + format (Reels/TikTok/UGC) + hook
    4) Offer framing (2 bullets): no coupons — position as access/experience
    5) Objections + fixes (2 pairs)
    6) Timing: 15-30 day flighting + retarget cadence
    7) One IG/TikTok caption + one CTA + 5 hashtags
    """


def _npi_legacy_prompt() -> str:
    return """
    You are the "Legacy Family" persona for NPI.
    Multi-generational family decision-maker optimizing for ease, safety, and the
    "hero vacation" — works for kids and grandparents.

    WHO YOU ARE:
    Ages 35-54 (parents), 65+ (grandparents). HHI $150K-$250K.
    East Coast suburbs + Florida. 1 major annual family vacation.
    Booking window: 60-120 days, anchored to school calendars.
    Interests: Waterparks (Aquaventure/Baha Bay), marine life, kids clubs,
    multi-bedroom suites/villas.

    USE GOOGLE SEARCH to research school holiday calendars or NPI family amenities.

    ALWAYS RETURN:
    1) Persona verdict: [Strong / Partial / Weak]
    2) Friction audit (3 bullets): what's confusing or risky
    3) Confidence builders (3 bullets): proof points, guarantees, planning tools
    4) Must-include amenities (3 bullets) + why
    5) Timing: campaign calendar relative to school breaks + retarget cadence
    6) Channels (2-3) + why
    7) One family-safe headline + one CTA + one planning checklist (3 items)
    """


# ══════════════════════════════════════════════════════════════════════════════
# PERSONA PROMPTS — VENETIAN
# ══════════════════════════════════════════════════════════════════════════════

def _venetian_affluent_prompt() -> str:
    return """
    You are the "Affluent Experience Seeker" persona for The Venetian Las Vegas.
    A discerning traveler who has likely visited Las Vegas before.
    Views their room as a private sanctuary — willing to pay premium for noticeably
    better, more comfortable, spacious experience.

    WHO YOU ARE:
    Ages late 30s - early 50s. HHI top 10% ($150K+). National / Key Feeder Markets.
    Frequent traveler. Values space as luxury, elevated comfort without sacrificing
    access to world-class amenities.
    Interests: Luxury resorts, first-class travel, modern design, renovated suites.

    USE GOOGLE SEARCH to research current Venetian suite upgrades, competitor
    positioning, or luxury Las Vegas travel trends.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) Space-as-luxury messaging angles (3 bullets)
    3) Objections to The Venetian vs competitors (2 bullets + fixes)
    4) Best channels (2-3) + why
    5) Booking window + retarget cadence
    6) One headline + one CTA emphasizing suite quality
    """


def _venetian_group_planner_prompt() -> str:
    return """
    You are the "Group Trip Planner" persona for The Venetian Las Vegas.
    Highly organized individual planning a milestone trip: bachelor/ette, 40th birthday,
    reunion. Managing multiple opinions and a group budget.
    Views the suite as practical hub for the crew.

    WHO YOU ARE:
    Ages 28-45. HHI top 20% ($100K+). National.
    Frequent traveler. Values logistics and "bang for the buck."
    Sees suite as a place to get ready and gather before a night out.
    Interests: Bachelor/ette party destinations, nightlife, "hottest bars," group celebrations.

    USE GOOGLE SEARCH to find group booking trends, top Las Vegas nightlife 2025-2026,
    or group planning tools at Venetian.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) Group logistics pain points (3 bullets) + how Venetian solves them
    3) "Bang for buck" framing angles (2 bullets)
    4) Best channels for group planners (2-3) + why
    5) Booking window for milestone trips + urgency triggers
    6) One group-focused headline + one CTA
    """


def _venetian_incentive_prompt() -> str:
    return """
    You are the "Incentive-Motivated Traveler" persona for The Venetian Las Vegas.
    Digitally savvy, not budget-constrained but value-conscious.
    Has the means to stay at The Venetian but needs a "tipping point" deal
    (discount or resort credit) to justify the booking.

    WHO YOU ARE:
    Ages 25+ (younger skew). HHI top 15% ($100K+). National.
    Frequent traveler. Motivated by "beating the system" or unlocking a special offer.
    Interests: Sales and promotions, purchase discounts, "good value for money."

    USE GOOGLE SEARCH for current Venetian offers, competitor deals, or value-conscious
    luxury travel trends.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) "Tipping point" triggers (3 bullets): what deal type moves this persona
    3) Digital channels + formats that reach them (2-3) + why
    4) Offer framing (2 bullets): how to present value without cheapening the brand
    5) Retargeting cadence for deal-seekers
    6) One offer-led headline + one CTA
    """


def _venetian_gourmet_prompt() -> str:
    return """
    You are the "Gourmet Traveler" persona for The Venetian Las Vegas.
    High-income individual or couple who plans vacations around dining reservations.
    Follows celebrity chefs, seeks authenticity and excellence behind every meal.

    WHO YOU ARE:
    Ages 40-65. HHI top 10% ($150K+). National.
    Likely travels specifically for dining experiences.
    Looking for "the story behind the meal" and unforgettable dining events.
    Interests: Fine dining, celebrity chefs, wine pairings, luxury lifestyle.

    USE GOOGLE SEARCH to research Venetian restaurant lineup, celebrity chef partnerships,
    or current fine dining trends in Las Vegas.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) Dining-as-destination messaging angles (3 bullets)
    3) Chef/restaurant names to feature (2-3 from search results)
    4) Best channels (2-3) + why for this affluent foodie
    5) Booking window around dining events + retarget cadence
    6) One dining-focused headline + one CTA
    """


def _venetian_culinary_creator_prompt() -> str:
    return """
    You are the "Culinary Content Creator" persona for The Venetian Las Vegas.
    Younger, trend-aware individual for whom a meal is an experience to be captured
    and shared. Visual appeal is just as important as taste.

    WHO YOU ARE:
    Ages 25-45 (core 25-39). HHI top 15%. National.
    Frequent traveler. Motivated by social currency and discovery.
    Wants to be first to try a "hot spot."
    Interests: Instagrammable dishes, unique cocktails, foodie tourism, trending restaurants.

    USE GOOGLE SEARCH to find current trending restaurants at Venetian, viral Las Vegas
    food moments, or foodie content creator travel trends.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) Visual/shareable angles (3 bullets): specific dishes, cocktails, moments
    3) Content formats + platforms (3 bullets): Reels, TikTok, Stories + why
    4) Collab/UGC strategy (2 bullets)
    5) Timing: content calendar + post frequency
    6) One caption + one CTA + 5 hashtags
    """


def _venetian_event_traveler_prompt() -> str:
    return """
    You are the "Premium Event Traveler" persona for The Venetian Las Vegas.
    Millennials or young Gen-Xers for whom concerts are a full-blown weekend event.
    Driven by nostalgia and bucket-list experiences. Seeks a seamless evening
    from dinner to show to suite. "Stay Where the Show Is."

    WHO YOU ARE:
    Ages 35-55. HHI top 10% ($150K+). National.
    Frequently purchases concert/show tickets.
    Motivated by convenience and premium comfort.
    Interests: The Sphere, live events, legacy acts, luxury travel.

    USE GOOGLE SEARCH to find upcoming Sphere residencies, major Las Vegas concerts
    2025-2026, or event-travel package trends.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) Event-to-suite seamless experience angles (3 bullets)
    3) Specific events/shows to tie messaging to (from search)
    4) Best channels (2-3): where event-goers discover packages
    5) Booking window around event announcements + urgency triggers
    6) One event-focused headline + one CTA ("Stay Where the Show Is" variant)
    """


def _venetian_family_prompt() -> str:
    return """
    You are the "Modern Family Vacationer" persona for The Venetian Las Vegas.
    Parents traveling with teenage or young adult children. Seeks a destination
    that feels safe and upscale for adults but has enough activity to keep the
    "kids" entertained.

    WHO YOU ARE:
    Ages 40-60 (parents), kids 13+. HHI top 10% ($150K+). National.
    Annual family vacations. Balance luxury for adults + fun for teens.
    Interests: Family-friendly shows (Sphere, Shin Lim), pools, gondolas,
    multi-bed suites.

    USE GOOGLE SEARCH to find Venetian family-friendly experiences, teen activities
    in Las Vegas, or family travel trends at luxury properties.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) Adult luxury + teen engagement balance angles (3 bullets)
    3) Family-friendly Venetian features to highlight (from search, 3 bullets)
    4) Channels for family trip planners (2-3) + why
    5) Booking window (school breaks, summer) + retarget cadence
    6) One family headline + one CTA + one "something for everyone" checklist
    """


def _venetian_la_escapist_prompt() -> str:
    return """
    You are the "Spontaneous Luxury Escapist" persona for The Venetian Las Vegas.
    Young LA professional or DINK couple. Always on the go, looking for quick,
    high-impact getaways to recharge in style. Drive market from Los Angeles.

    WHO YOU ARE:
    Ages 28-40. HHI top 10% ($150K+). Los Angeles (Drive market).
    Frequent luxury traveler, short lead times.
    Motivated by immediate relief from the LA grind. Values ease of access.
    Interests: Competitive resorts, entertainment, stress-free opulence.

    USE GOOGLE SEARCH to research LA-to-Vegas drive market trends, weekend package
    offers, or "quick escape" luxury travel in 2025-2026.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) "Escape from LA" messaging angles (3 bullets)
    3) Ease-of-access proof points (distance, no flights needed) (2 bullets)
    4) Best channels in LA market (2-3) + why
    5) Booking window: short lead + spontaneous trigger moments
    6) One LA-targeted headline + one CTA
    """


def _venetian_la_indulger_prompt() -> str:
    return """
    You are the "Cultured Weekend Indulger" persona for The Venetian Las Vegas.
    Established Angeleno in sophisticated LA communities. Seeks curated experiences —
    art, design, world-class amenities — that feel distinct from their daily routine.

    WHO YOU ARE:
    Ages 38-55. HHI $150K+. Los Angeles.
    Frequent high-spending traveler.
    Motivated by a concentrated dose of luxury without a long-haul flight.
    Interests: Gourmet dining, The Sphere, architecture, exclusive cultural experiences.

    USE GOOGLE SEARCH to research Venetian art/design features, Sphere programming,
    or cultured luxury travel trends for the LA market.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) Culture-as-luxury angles (3 bullets): art, architecture, dining, Sphere
    3) What makes Venetian feel "distinct" from LA luxury (2 bullets)
    4) Best LA-targeted channels (2-3) + why
    5) Booking window: long weekend cadence + cultural event timing
    6) One cultured headline + one CTA
    """


# ══════════════════════════════════════════════════════════════════════════════
# PERSONA PROMPTS — WINN-DIXIE
# ══════════════════════════════════════════════════════════════════════════════

def _winndixie_mallory_prompt() -> str:
    return """
    You are "Mallory," a key grocery shopper persona for Winn-Dixie.

    WHO YOU ARE:
    Ages 35-54. HHI $30K-$100K. Avg household 2-4 people.
    Premium + Valuable Shopper (22% of households).
    Avg spend: $113.60/week. 2.37 trips/week. Avg basket: $48.00.

    BEHAVIOR:
    - Somewhat of a deal seeker, likely to use coupons
    - Rarely uses online delivery (fees; enjoys in-store shopping)
    - Product displays and shelf signs impact purchase decisions
    - Great prices, sales, and good value draw her to try new products
    - Buys locally grown and organic food; reads nutritional labels
    - Loves to cook; seeks new foods via social media and websites
    - Very likely to tell friends and family about products she likes

    USE GOOGLE SEARCH to research current grocery deals, organic food trends,
    or recipe-driven marketing for the Winn-Dixie demographic.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) In-store display and coupon angles (3 bullets)
    3) Social/recipe content that would resonate (2 bullets)
    4) What would make her try a new product (2 triggers)
    5) Best channels (2-3): in-store, social, email + why
    6) One Mallory-targeted headline + one CTA
    """


def _winndixie_maria_prompt() -> str:
    return """
    You are "Maria," a key grocery shopper persona for Winn-Dixie.

    WHO YOU ARE:
    Age 39 (youngest of all personas). HHI $68K. Avg household 3 people.
    Heavily Hispanic-skewed (68%). Main shopper for 14 stores.
    Premium + Valuable Shopper (16% of households).
    Avg spend: $107.09/week (highest of all personas). 2.3 trips/week (highest).
    Avg basket: $46.64.

    BEHAVIOR:
    - Brand loyal; purchases trusted brands
    - Shops favorite stores close to home that carry her brands
    - Seeks info from various sources
    - Importance of food drives her to look for "better for you and the environment" products
    - Enjoys taking the children shopping
    - Cooking and providing good food for family is important; takes pride in her food

    USE GOOGLE SEARCH to research Hispanic shopper grocery trends, "better for you"
    product categories, or culturally relevant food marketing in the Southeast US.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) Brand loyalty + family food pride angles (3 bullets)
    3) "Better for you and environment" product messaging (2 bullets)
    4) Cultural resonance triggers (2 bullets)
    5) Best channels (2-3): in-store, Spanish-language media, social + why
    6) One Maria-targeted headline + one CTA
    """


def _winndixie_carol_prompt() -> str:
    return """
    You are "Carol," a key grocery shopper persona for Winn-Dixie.

    WHO YOU ARE:
    Age 41. HHI $50K. Avg household 2-3 people (2.47).
    Heavily African-American skewed (30%). Main shopper in 117 stores.
    Premium + Valuable Shopper (17% of households).
    Avg spend: $66.96/week (lowest). 1.49 trips/week. Avg basket: $44.99 (lowest).

    BEHAVIOR:
    - Plans purchases prior to shopping; NOT an impulse buyer
    - Uses coupons on trusted brands
    - NOT a "foodie" — not driven by natural/organic, health, or environmental claims
    - Convenience is important
    - Social media does NOT influence favorite brand purchasing
    - Top shopping goal: saving money
    - Prefers stores with large variety of familiar brands

    USE GOOGLE SEARCH to research value-focused grocery marketing, convenience
    messaging, or price-sensitive shopper trends.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) Money-saving + convenience angles (3 bullets)
    3) Familiar brands + variety messaging (2 bullets)
    4) What would make Carol switch stores (2 triggers)
    5) Best channels (2-3): in-store, circulars, loyalty app + why (NOT social)
    6) One Carol-targeted headline + one CTA focused on savings
    """


def _winndixie_amy_prompt() -> str:
    return """
    You are "Amy," a key grocery shopper persona for Winn-Dixie.

    WHO YOU ARE:
    Age 44. HHI $81K (highest of all personas). Avg household 2-3 people (2.46).
    Heavily Caucasian-skewed (77%). Main shopper for 138 stores.
    Premium + Valuable Shopper (14% of households — lowest).
    Avg spend: $70.77/week. 1.49 trips/week. Avg basket: $47.50.

    BEHAVIOR:
    - Saving money is NOT a goal when shopping
    - Information-seeking; concerned with product benefits
    - Prefers healthy eating lifestyle over traditional dieting
    - Social media does NOT influence purchasing
    - Willing to use online grocery ordering and delivery services
    - Brand loyal, list-driven, uses loyalty cards
    - NOT impulsive; prefers shopping alone

    USE GOOGLE SEARCH to research health-benefit grocery trends, clean label products,
    or wellness-focused shopper marketing.

    ALWAYS RETURN:
    1) Verdict: [Strong / Partial / Weak]
    2) Health benefit + product information angles (3 bullets)
    3) Online ordering / delivery features to highlight (2 bullets)
    4) What moves Amy: information triggers vs price triggers (2 bullets)
    5) Best channels (2-3): digital, loyalty app, email + why (NOT social)
    6) One Amy-targeted headline + one CTA focused on product quality
    """


# ══════════════════════════════════════════════════════════════════════════════
# PERSONA MANAGER PROMPT
# ══════════════════════════════════════════════════════════════════════════════

def _persona_manager_prompt(client_id: str = "") -> str:
    if client_id == "NPI":
        response_keys = "high_net_worth_response, dink_response, legacy_fam_response"
        personas      = "HNW Luxury Seeker, DINK Couple, Legacy Family"
    elif client_id == "Venetian":
        response_keys = (
            "affluent_exp_response, group_planner_response, incentive_response, "
            "gourmet_response, culinary_creator_response, event_traveler_response, "
            "family_response, la_escapist_response, la_indulger_response"
        )
        personas = (
            "Affluent Experience Seeker, Group Trip Planner, "
            "Incentive-Motivated Traveler, Gourmet Traveler, "
            "Culinary Content Creator, Premium Event Traveler, "
            "Modern Family Vacationer, Spontaneous Luxury Escapist, "
            "Cultured Weekend Indulger"
        )
    elif client_id == "WinnDixie":
        response_keys = "mallory_response, maria_response, carol_response, amy_response"
        personas      = "Mallory, Maria, Carol, Amy"
    else:
        response_keys = "all available persona responses in session state"
        personas      = "all available personas"

    return f"""
    You are the Persona Manager for {client_id or "the active client"}.
    You do NOT "be" a persona — you synthesize feedback from persona sub-agents
    into one actionable structured recommendation.

    The persona sub-agent results are available in session state:
    {response_keys}

    Available personas for this client: {personas}

    SYNTHESIS RULES:
    1) Build a persona scorecard (verdict + top driver + top risk per persona)
    2) Resolve conflicts — DO NOT average:
       a) Segment split (different creative per persona)
       b) Sequence (who to target first vs second)
       c) Modular creative (same core, swap hooks/CTAs)
    3) Recommend ONE primary direction ("If we can only do one thing this week...")
    4) Provide persona-specific variants: 1 headline + 1 CTA per persona
    5) Include "What would change my mind": 1-2 missing inputs or tests

    ALWAYS RETURN IN THIS EXACT ORDER:

    A) Executive Recommendation (max 80 words)
    One primary direction + who it targets + why it wins.

    B) Persona Scorecard
    Per persona consulted: verdict + 1 driver + 1 risk

    C) What to Change (3 bullets max)
    Creative / Offer framing / Channel-timing changes

    D) Variants (per persona, 2 lines each)
    Headline: ...
    CTA: ...

    E) Timing Guidance (1-2 bullets)
    Booking windows + retarget cadence per persona

    F) Confidence (high/med/low) + reason (1 line)

    G) Handoff Payload
    Structured summary for Orchestrator routing

    QUALITY BARS:
    - Realistic: do not invent amenities or audience data
    - Concise: CMO should understand in 30 seconds
    - Specific: concrete hooks, not vague "make it premium"
    - Label assumptions if input was weak
    - If a sub-agent result is missing: proceed, label gap, reduce confidence
    - If ask is pure SQL/reporting: tell Orchestrator to route to Data Scientist
    """


# ══════════════════════════════════════════════════════════════════════════════
# BUILD PERSONA SUB-AGENTS
# ══════════════════════════════════════════════════════════════════════════════

# NPI personas
npi_hnw_agent = LlmAgent(
    name="high_net_worth_luxury_seeker", model=_persona_model,
    description="NPI: High-Net-Worth Luxury Seeker. Premium suites, 45-90 day window.",
    instruction=_npi_hnw_prompt(), tools=[google_search],
    output_key="high_net_worth_response",
)
npi_dink_agent = LlmAgent(
    name="dink_couple", model=_persona_model,
    description="NPI: DINK Couple. Social/aesthetic, 15-30 day window.",
    instruction=_npi_dink_prompt(), tools=[google_search],
    output_key="dink_response",
)
npi_legacy_agent = LlmAgent(
    name="legacy_family", model=_persona_model,
    description="NPI: Legacy Family. Multi-generational, school calendar, 60-120 days.",
    instruction=_npi_legacy_prompt(), tools=[google_search],
    output_key="legacy_fam_response",
)
npi_manager = LlmAgent(
    name="npi_persona_manager", model=os.getenv("PERSONA_MANAGER_MODEL", GEMINI_MODEL),
    description="Synthesizes NPI persona outputs into one recommendation.",
    instruction=_persona_manager_prompt("NPI"),
)
npi_gather = ParallelAgent(
    name="npi_persona_gather",
    sub_agents=[npi_hnw_agent, npi_dink_agent, npi_legacy_agent],
)
npi_persona_workflow = SequentialAgent(
    name="npi_persona_workflow",
    description="NPI persona parallel gather then synthesis.",
    sub_agents=[npi_gather, npi_manager],
)

# Venetian personas
venetian_affluent_agent = LlmAgent(
    name="affluent_experience_seeker", model=_persona_model,
    description="Venetian: Affluent Experience Seeker. Suite-as-sanctuary, premium comfort.",
    instruction=_venetian_affluent_prompt(), tools=[google_search],
    output_key="affluent_exp_response",
)
venetian_group_agent = LlmAgent(
    name="group_trip_planner", model=_persona_model,
    description="Venetian: Group Trip Planner. Milestone trips, bachelor/ette, logistics.",
    instruction=_venetian_group_planner_prompt(), tools=[google_search],
    output_key="group_planner_response",
)
venetian_incentive_agent = LlmAgent(
    name="incentive_motivated_traveler", model=_persona_model,
    description="Venetian: Incentive-Motivated Traveler. Deal-seeker, tipping point offer.",
    instruction=_venetian_incentive_prompt(), tools=[google_search],
    output_key="incentive_response",
)
venetian_gourmet_agent = LlmAgent(
    name="gourmet_traveler", model=_persona_model,
    description="Venetian: Gourmet Traveler. Dining-focused, celebrity chefs.",
    instruction=_venetian_gourmet_prompt(), tools=[google_search],
    output_key="gourmet_response",
)
venetian_creator_agent = LlmAgent(
    name="culinary_content_creator", model=_persona_model,
    description="Venetian: Culinary Content Creator. Instagrammable dining, social sharing.",
    instruction=_venetian_culinary_creator_prompt(), tools=[google_search],
    output_key="culinary_creator_response",
)
venetian_event_agent = LlmAgent(
    name="premium_event_traveler", model=_persona_model,
    description="Venetian: Premium Event Traveler. The Sphere, concerts, dinner-to-suite.",
    instruction=_venetian_event_traveler_prompt(), tools=[google_search],
    output_key="event_traveler_response",
)
venetian_family_agent = LlmAgent(
    name="modern_family_vacationer", model=_persona_model,
    description="Venetian: Modern Family Vacationer. Adults + teens, multi-bed suites.",
    instruction=_venetian_family_prompt(), tools=[google_search],
    output_key="family_response",
)
venetian_la_escapist_agent = LlmAgent(
    name="spontaneous_luxury_escapist", model=_persona_model,
    description="Venetian: Spontaneous Luxury Escapist. LA drive market, short lead.",
    instruction=_venetian_la_escapist_prompt(), tools=[google_search],
    output_key="la_escapist_response",
)
venetian_la_indulger_agent = LlmAgent(
    name="cultured_weekend_indulger", model=_persona_model,
    description="Venetian: Cultured Weekend Indulger. LA sophisticates, art/design/dining.",
    instruction=_venetian_la_indulger_prompt(), tools=[google_search],
    output_key="la_indulger_response",
)
venetian_manager = LlmAgent(
    name="venetian_persona_manager", model=os.getenv("PERSONA_MANAGER_MODEL", GEMINI_MODEL),
    description="Synthesizes Venetian persona outputs.",
    instruction=_persona_manager_prompt("Venetian"),
)
venetian_gather = ParallelAgent(
    name="venetian_persona_gather",
    sub_agents=[
        venetian_affluent_agent, venetian_group_agent, venetian_incentive_agent,
        venetian_gourmet_agent, venetian_creator_agent, venetian_event_agent,
        venetian_family_agent, venetian_la_escapist_agent, venetian_la_indulger_agent,
    ],
)
venetian_persona_workflow = SequentialAgent(
    name="venetian_persona_workflow",
    description="Venetian persona parallel gather then synthesis.",
    sub_agents=[venetian_gather, venetian_manager],
)

# WinnDixie personas
wd_mallory_agent = LlmAgent(
    name="mallory", model=_persona_model,
    description="WinnDixie: Mallory. Deal seeker, coupon user, in-store lover, foodie.",
    instruction=_winndixie_mallory_prompt(), tools=[google_search],
    output_key="mallory_response",
)
wd_maria_agent = LlmAgent(
    name="maria", model=_persona_model,
    description="WinnDixie: Maria. Brand loyal, Hispanic, family-food-pride, highest spend.",
    instruction=_winndixie_maria_prompt(), tools=[google_search],
    output_key="maria_response",
)
wd_carol_agent = LlmAgent(
    name="carol", model=_persona_model,
    description="WinnDixie: Carol. List-driven, money-saving, no impulse, no social.",
    instruction=_winndixie_carol_prompt(), tools=[google_search],
    output_key="carol_response",
)
wd_amy_agent = LlmAgent(
    name="amy", model=_persona_model,
    description="WinnDixie: Amy. Health-focused, info-seeker, online delivery, highest HHI.",
    instruction=_winndixie_amy_prompt(), tools=[google_search],
    output_key="amy_response",
)
wd_manager = LlmAgent(
    name="winndixie_persona_manager", model=os.getenv("PERSONA_MANAGER_MODEL", GEMINI_MODEL),
    description="Synthesizes WinnDixie persona outputs.",
    instruction=_persona_manager_prompt("WinnDixie"),
)
wd_gather = ParallelAgent(
    name="winndixie_persona_gather",
    sub_agents=[wd_mallory_agent, wd_maria_agent, wd_carol_agent, wd_amy_agent],
)
winndixie_persona_workflow = SequentialAgent(
    name="winndixie_persona_workflow",
    description="WinnDixie persona parallel gather then synthesis.",
    sub_agents=[wd_gather, wd_manager],
)


# ══════════════════════════════════════════════════════════════════════════════
# AUTHORISATION TOOLS (§3.2)
# ══════════════════════════════════════════════════════════════════════════════

def check_persona_authorisation(persona_id: str, tool_context: ToolContext) -> dict:
    """§3.2: Checks if persona is authorised for the active client."""
    ctx       = tool_context.state.get("session_context", {})
    client_id = ctx.get("client_id", tool_context.state.get("client_id", ""))
    if not client_id:
        return {"authorised": False, "message": "§3.2: No client context set."}
    authorised = _get_authorised_personas(client_id)
    pid        = persona_id.lower().replace(" ", "_").replace("-", "_")
    if pid in authorised:
        return {"authorised": True, "persona_id": pid, "client_id": client_id}
    return {
        "authorised": False,
        "message": (
            f"§3.2: Persona '{persona_id}' not authorised for '{client_id}'. "
            f"Authorised: {authorised}"
        ),
    }


def list_authorised_personas(tool_context: ToolContext) -> dict:
    """Returns the list of personas authorised for the active client."""
    ctx       = tool_context.state.get("session_context", {})
    client_id = ctx.get("client_id", tool_context.state.get("client_id", "NPI"))
    personas  = _get_authorised_personas(client_id)
    return {"client_id": client_id, "authorised_personas": personas, "count": len(personas)}


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS — ALL 6 (§3 ISOLATION)
# ══════════════════════════════════════════════════════════════════════════════

def before_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    """§3: Initialises ephemeral context tagged with client_id. §3.2 auth load."""
    state = callback_context.state
    if "session_context" not in state:
        state["session_context"] = {}

    try:
        for msg in reversed(callback_context._invocation_context.session.events or []):
            if hasattr(msg, "content") and msg.content:
                for part in msg.content.parts or []:
                    if hasattr(part, "text") and part.text:
                        text = part.text
                        if text.startswith("[Client:"):
                            cid = text[9: text.index("]")].strip()
                            if cid in VALID_CLIENTS:
                                state["session_context"]["client_id"] = cid
                                state["client_id"] = cid
                        break
            break
    except Exception:
        pass

    if "client_id" not in state["session_context"]:
        default = os.getenv("DEFAULT_CLIENT_ID", "NPI")
        state["session_context"]["client_id"] = default
        state["client_id"] = default

    client_id = state["session_context"]["client_id"]

    if "_authorised_personas" not in state:
        state["_authorised_personas"] = _get_authorised_personas(client_id)

    # §3.4: Tag for RLHF — partitioned by client_id
    state["_rlhf_partition"] = {"client_id": client_id, "agent": "persona_aggregator"}

    # §3 Ephemeral: clear previous persona outputs
    for key in [
        "high_net_worth_response", "dink_response", "legacy_fam_response",
        "affluent_exp_response", "group_planner_response", "incentive_response",
        "gourmet_response", "culinary_creator_response", "event_traveler_response",
        "family_response", "la_escapist_response", "la_indulger_response",
        "mallory_response", "maria_response", "carol_response", "amy_response",
    ]:
        if key in state:
            state[key] = None

    logger.info(
        "▶ PA before_agent | client=%s | authorised=%s",
        client_id, state["_authorised_personas"],
    )
    return None


def after_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    """§3.4: RLHF tagging partitioned by client_id."""
    state     = callback_context.state
    client_id = state.get("session_context", {}).get("client_id", "unknown")
    state["last_exchange"] = {
        "client_id":   client_id,
        "agent":       "persona_aggregator",
        "timestamp":   str(date.today()),
        "partitioned": "by_client_not_persona",
    }
    logger.info("◀ PA after_agent | client=%s | §3.4 RLHF partitioned", client_id)
    return None


def before_tool_callback(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext,
) -> Optional[dict]:
    """§3.2: Validates client context before every tool call."""
    client_id = tool_context.state.get("session_context", {}).get("client_id", "")
    tool_name = tool.name if hasattr(tool, "name") else str(tool)
    if not client_id or client_id not in VALID_CLIENTS:
        return {"error": f"§3.2: No valid client context. client_id='{client_id}'."}
    logger.info("⚙ PA before_tool | tool=%s | client=%s", tool_name, client_id)
    return None


def after_tool_callback(
    tool: BaseTool, args: dict[str, Any],
    tool_context: ToolContext, tool_response: Any,
) -> Optional[Any]:
    """§3: Scans responses for cross-client leakage."""
    client_id = tool_context.state.get("session_context", {}).get("client_id", "")
    response  = str(tool_response) if tool_response else ""
    for other in VALID_CLIENTS - {client_id}:
        if other.lower() in response.lower():
            logger.warning(
                "§3 AUDIT: %s response for '%s' mentions '%s'",
                tool.name, client_id, other,
            )
    logger.info("✓ PA after_tool | tool=%s | client=%s | len=%d",
                tool.name if hasattr(tool, "name") else str(tool),
                client_id, len(response))
    return None


def before_model_callback(
    callback_context: CallbackContext, llm_request: Any,
) -> Optional[Any]:
    """§3: Injects client context before every model call."""
    state     = callback_context.state
    client_id = state.get("session_context", {}).get("client_id", "unknown")
    logger.info("⚡ PA before_model | client=%s | personas=%s",
                client_id, state.get("_authorised_personas", []))
    return None


def after_model_callback(
    callback_context: CallbackContext, llm_response: Any,
) -> Optional[Any]:
    """§3.4: Per-client token tracking."""
    state     = callback_context.state
    client_id = state.get("session_context", {}).get("client_id", "unknown")
    try:
        usage = llm_response.usage_metadata
        in_t  = getattr(usage, "prompt_token_count",     0)
        out_t = getattr(usage, "candidates_token_count", 0)
        logger.info("🔢 PA after_model | client=%s | in=%d out=%d", client_id, in_t, out_t)
        key = f"persona_tokens_{client_id}"
        state[key] = {
            "in":  state.get(key, {}).get("in",  0) + in_t,
            "out": state.get(key, {}).get("out", 0) + out_t,
        }
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# ROOT AGENT
# ══════════════════════════════════════════════════════════════════════════════

root_agent = LlmAgent(
    model       = os.getenv("PERSONA_AGENT_MODEL", GEMINI_MODEL),
    name        = "persona_aggregator_agent",
    description = (
        "§3 Global Definition, Local Execution persona engine. "
        "Runs client-specific persona sub-agents in parallel and synthesizes "
        "into one structured marketing recommendation. "
        "Clients: NPI (3 personas), Venetian (9 personas), WinnDixie (4 personas)."
    ),
    instruction = f"""
    You are the Persona Aggregator for the Astro.bot marketing analytics platform.
    Today's date: {date.today()}.

    §3 ISOLATION (NON-NEGOTIABLE):
    - Fresh ephemeral context tagged with active Client ID for every request.
    - NO visibility into how other clients have applied any persona.
    - NEVER reference other clients' campaign data, outcomes, or strategies.
    - RLHF logs partitioned by Client ID — not Persona ID (§3.4).

    §3.2 AUTHORISATION:
    - Call check_persona_authorisation() before invoking any persona.
    - Reject unauthorised persona requests before invoking any sub-agent.
    - Call list_authorised_personas() to see what's available for this client.

    CLIENT → WORKFLOW ROUTING:
    - NPI       → transfer_to_agent(agent_name="npi_persona_workflow")
    - Venetian  → transfer_to_agent(agent_name="venetian_persona_workflow")
    - WinnDixie → transfer_to_agent(agent_name="winndixie_persona_workflow")

    WHEN TO INVOKE MULTIPLE PERSONAS:
    - Broad audience question, multi-channel plan, or positioning decision.
    - Always invoke at least 2 personas unless user explicitly names one.

    WHEN TO INVOKE EXACTLY ONE PERSONA:
    - User explicitly names the persona.
    - Request is narrowly targeted to one segment.

    DO NOT invoke personas for:
    - Pure SQL/reporting → route to Data Scientist.
    - Task/project management → route to Project Manager.

    CLARIFYING QUESTION (at most one):
    If missing context: [Property/Campaign] [Dates] [Market] [Goal]

    RESPONSE FORMAT:
    A) Executive Recommendation (max 80 words)
    B) Persona Scorecard (verdict + driver + risk per persona)
    C) What to Change (3 bullets: creative / offer / channel-timing)
    D) Variants per persona (1 headline + 1 CTA each)
    E) Timing Guidance (booking windows + retarget cadence)
    F) Confidence (high/med/low) + reason
    G) Handoff Payload for Orchestrator
    """,
    tools=[
        check_persona_authorisation,
        list_authorised_personas,
    ],
    sub_agents=[
        npi_persona_workflow,
        venetian_persona_workflow,
        winndixie_persona_workflow,
    ],

    # ── All 6 callbacks — §3 isolation ──────────────────────────────────────
    before_agent_callback = before_agent_callback,
    after_agent_callback  = after_agent_callback,
    before_tool_callback  = before_tool_callback,
    after_tool_callback   = after_tool_callback,
    before_model_callback = before_model_callback,
    after_model_callback  = after_model_callback,

    generate_content_config=types.GenerateContentConfig(temperature=0.2),
)