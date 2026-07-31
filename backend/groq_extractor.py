"""
ImpactChain AI — Phase 1 Step 1.3: Groq Relationship Extraction

Calls Groq API (llama3-70b-8192) with article text and spaCy scaffold
to extract supply-chain relevance, relationships, and economic impact chains.
"""

import json
import asyncio
import logging

from config import GROQ_API_KEY, GROQ_MODEL, FALLBACK_GROQ_MODEL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — verbatim from idk.md Step 1.3
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """You are a supply chain intelligence extraction engine.

You will receive a news article and a set of named entities already extracted by spaCy NER.

Your job is NOT to re-extract organizations, locations, or people. spaCy has already done that.

Your job is ONLY to determine the following:

1. SUPPLY CHAIN RELEVANCE
   Decide if this article is supply-chain relevant. Return true or false.
   Supply chain relevance means the article describes or implies an event that affects
   the movement, price, availability, or production of any physical good, commodity,
   raw material, logistics network, transportation route, or industrial output.
   
   Return true for: commodity disruptions, shipping route issues, factory closures,
   trade sanctions, natural disasters affecting logistics, port closures, energy supply
   changes, agricultural disruptions, semiconductor shortages, fuel price changes,
   labor strikes at logistics or industrial facilities, trade policy changes.
   
   Return true for gray zone cases: political events in commodity-producing regions,
   government policy changes that indirectly restrict trade, elections in resource-heavy
   countries, conflict in regions with major shipping routes.
   
   Return false for: celebrity news, sports, entertainment, purely domestic political
   scandals unrelated to trade or industry, general crime news, health news unrelated
   to industrial or logistics disruption.

2. CONFIDENCE SCORE
   Return a float between 0.0 and 1.0 representing how confident you are in the
   supply-chain relevance judgment. High confidence = clearly relevant or clearly
   irrelevant. Low confidence = genuinely ambiguous.

3. PRIMARY COMMODITIES AFFECTED
   Identify which commodities are affected by the events in this article.
   Do not use a predefined list. Extract from context.
   Common examples: crude oil, natural gas, LNG, semiconductors, lithium, cobalt,
   wheat, corn, soybeans, shipping containers, copper, aluminum, steel, rare earth metals.
   Return as an array. Return null if no commodity is clearly affected.

4. ENTITY ROLES
   For each entity already found by spaCy (organizations and locations), assign a
   supply chain role. Roles must be one of:
   "supplier" — produces or originates the commodity
   "consumer" — buys or uses the commodity
   "logistics_node" — a route, port, canal, or transit point
   "regulatory_body" — controls policy, price, or access
   "disruption_cause" — the entity or actor causing the disruption
   "price_influencer" — influences commodity pricing without directly supplying or consuming
   
   Only assign roles to entities that have a clear supply chain role in THIS article.
   Skip entities that are incidental mentions.

5. RELATIONSHIPS
   Express relationships between entities as triples: [source, relationship_type, target]
   Relationship types must be one of:
   "disrupts", "supplies", "controls_price_of", "depends_on", "routes_through",
   "regulates", "produces", "consumes", "competes_with", "sanctions", "reroutes_around"
   
   Only include relationships that are explicitly stated or strongly implied by the article.
   Do not infer relationships that are not present in the article.

6. ECONOMIC IMPACT CHAIN
   Describe the downstream propagation of this event as an ordered list of steps.
   Start from the triggering event and end at the furthest downstream economic effect
   that is reasonably implied by the article.
   Each step should be a short descriptive phrase.
   Maximum 10 steps.

7. EVENT CATEGORY
   Classify the event as exactly one of:
   war, weather, policy, logistics, industrial, geopolitical, financial, other

Return ONLY a valid JSON object. No explanation text. No markdown formatting. No backticks.
No preamble. No postamble. The response must be directly parseable by Python json.loads()."""


def _force_lowercase_entities(response: dict) -> dict:
    """
    Ensure ALL entity names in the Groq response are lowercase.
    This is critical for consistent entity matching downstream.
    """
    # Lowercase entity_roles keys
    if "entity_roles" in response and isinstance(response["entity_roles"], dict):
        response["entity_roles"] = {
            k.lower(): v.lower() if isinstance(v, str) else v
            for k, v in response["entity_roles"].items()
        }

    # Lowercase primary_commodities
    if "primary_commodities" in response and isinstance(response["primary_commodities"], list):
        response["primary_commodities"] = [
            c.lower() if isinstance(c, str) else c
            for c in response["primary_commodities"]
        ]

    # Lowercase relationship triple source and target
    if "relationships" in response and isinstance(response["relationships"], list):
        normalized_rels = []
        for triple in response["relationships"]:
            if isinstance(triple, (list, tuple)) and len(triple) == 3:
                normalized_rels.append([
                    str(triple[0]).lower(),
                    str(triple[1]).lower(),
                    str(triple[2]).lower(),
                ])
            else:
                normalized_rels.append(triple)
        response["relationships"] = normalized_rels

    # Lowercase event_category
    if "event_category" in response and isinstance(response["event_category"], str):
        response["event_category"] = response["event_category"].lower()

    return response


async def extract_relationships_groq(
    article: dict, spacy_scaffold: dict, max_retries: int = 2
) -> dict | None:
    """
    Call Groq API to extract supply-chain relationships and relevance.

    Args:
        article: Article dictionary from Step 1.1
        spacy_scaffold: Entity scaffold from Step 1.2
        max_retries: Number of retry attempts on failure (default 2)

    Returns:
        Parsed Groq response dict with all entity names lowercased,
        or None if extraction fails.
    """
    article_id = article.get("article_id", "unknown")

    if not GROQ_API_KEY:
        logger.error(f"Article {article_id}: GROQ_API_KEY is not set, cannot extract relationships")
        return None

    # Build article text — trim to 1500 chars to conserve API tokens
    title = article.get("title") or ""
    description = article.get("description") or ""
    content = article.get("content") or ""
    full_text = f"{title}\n\n{description}\n\n{content}".strip()
    if len(full_text) > 1500:
        full_text = full_text[:1500] + "..."

    if not full_text:
        logger.warning(f"Article {article_id}: empty text, skipping Groq extraction")
        return None

    # Build user message
    scaffold_json = json.dumps(spacy_scaffold.get("raw_entities", {}), indent=2)
    user_message = f"Article:\n{full_text}\n\nspaCy Entities Already Extracted:\n{scaffold_json}"

    # Retry loop with automatic model fallback
    last_error = None
    raw_response_text = None
    current_model = GROQ_MODEL

    for attempt in range(max_retries + 1):
        try:
            # Import groq client inside the function to handle missing package gracefully
            from groq import Groq, APIStatusError

            client = Groq(api_key=GROQ_API_KEY)

            logger.info(
                f"Article {article_id}: calling Groq API using model '{current_model}' "
                f"(attempt {attempt + 1}/{max_retries + 1})"
            )

            # Groq client is synchronous — run in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            target_model = current_model
            completion = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=target_model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.1,
                    max_tokens=2048,
                ),
            )

            # Extract response text
            raw_response_text = completion.choices[0].message.content.strip()

            # Log token usage if available
            if hasattr(completion, "usage") and completion.usage:
                logger.info(
                    f"Article {article_id}: Groq tokens — "
                    f"prompt={completion.usage.prompt_tokens}, "
                    f"completion={completion.usage.completion_tokens}, "
                    f"total={completion.usage.total_tokens}"
                )

            # Parse JSON response
            # Handle cases where Groq wraps response in markdown code blocks
            cleaned = raw_response_text
            if cleaned.startswith("```"):
                # Remove markdown fencing
                lines = cleaned.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines)

            parsed = json.loads(cleaned)

            # Force all entity names to lowercase
            parsed = _force_lowercase_entities(parsed)

            logger.info(
                f"Article {article_id}: Groq extraction successful — "
                f"relevant={parsed.get('is_supply_chain_relevant')}, "
                f"confidence={parsed.get('confidence')}"
            )
            return parsed

        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            logger.warning(
                f"Article {article_id}: Groq returned invalid JSON "
                f"(attempt {attempt + 1}): {e}"
            )
            logger.debug(f"Raw Groq response: {raw_response_text}")

        except Exception as e:
            last_error = str(e)
            if "429" in str(e) or "rate_limit_exceeded" in str(e):
                logger.warning(
                    f"Article {article_id}: Groq rate limit hit on model '{current_model}'. "
                    f"Switching fallback model to '{FALLBACK_GROQ_MODEL}'."
                )
                current_model = FALLBACK_GROQ_MODEL
            else:
                logger.warning(
                    f"Article {article_id}: Groq API error "
                    f"(attempt {attempt + 1}): {e}"
                )

        # Backoff before retry (except on last attempt)
        if attempt < max_retries:
            await asyncio.sleep(2)

    # All retries exhausted
    logger.error(
        f"Article {article_id}: Groq extraction failed after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )
    return None
