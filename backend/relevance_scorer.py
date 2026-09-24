"""
ImpactChain AI — Dynamic Relevance Scorer

Judges if a news article is actually about a real supply chain disruption using Groq
semantic analysis (rather than static entity keyword lists).
"""

import json
import logging
import asyncio
from typing import Optional, List, Dict, Any

from config import GROQ_API_KEY, GROQ_MODEL, FALLBACK_GROQ_MODEL

logger = logging.getLogger(__name__)

_RELEVANCE_PROMPT = """Analyze this article and judge if it describes an actual SUPPLY CHAIN DISRUPTION.

Headline: {headline}
Summary: {summary}
Mentioned entities: {entities}

Answer ONLY with a valid JSON object (no markdown formatting, no backticks, no preamble):
{{
    "relevant": true,
    "score": 0.95,
    "reason": "brief explanation of supply chain disruption",
    "disruption_type": "geopolitical",
    "affected_domains": ["oil", "semiconductors", "shipping"]
}}

Allowed values for disruption_type:
- "geopolitical" (wars, embargos, sanctions, trade bans, state conflict)
- "natural_disaster" (earthquakes, hurricanes, floods, extreme weather)
- "industrial_failure" (factory fires/explosions, power outages, equipment breakdowns)
- "logistics" (port congestions, canal blockages, shipping route reroutes, freight strikes)
- "commodity_crisis" (critical material shortages, abrupt price spikes, supply quotas)
- "economic_shock" (tariff hikes, severe regulatory halts, export curbs)
- "none" (if not relevant)

Guidelines for RELEVANT articles (relevant: true, score >= 0.5):
- Describes actual disruption: war, embargo, strike, natural disaster, factory explosion, export ban
- Impacts supply chain: mentions shortage, price spike, route blocked, production halted, supply bottleneck
- Actionable intelligence: readers can understand downstream economic or industrial consequences

Guidelines for IRRELEVANT articles (relevant: false, score < 0.5):
- Technology feature / entertainment article mentioning a company or tech (e.g., "Ed Sheeran concert hologram semiconductor tech")
- Standard product launch, consumer gadget reviews, or corporate promotional news
- Historical or educational content
- General domestic politics, election gossip, celebrity news without physical trade/supply chain impact
- Pure market speculation or opinion without confirmed disruption

BE STRICT. Only mark as relevant if a clear supply chain impact or risk exists.
"""


class RelevanceScorer:
    """
    Judges if an article is actually about supply chain disruption.
    Uses Groq for semantic understanding (not keyword matching).
    """

    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or GROQ_API_KEY
        self.cache: Dict[str, Dict[str, Any]] = {}

    def _build_cache_key(self, headline: str, entities: List[str]) -> str:
        entities_str = ",".join(sorted(str(e).strip().lower() for e in (entities or [])))
        return f"{headline.strip().lower()}:{entities_str}"

    def score_article(
        self,
        headline: str,
        summary: str,
        entities: Optional[List[str]] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Synchronously judge relevance of an article using Groq with caching and fallback.

        Returns:
        {
            "relevant": bool,
            "score": float (0-1),
            "reason": str,
            "disruption_type": str or None,
            "affected_domains": list
        }
        """
        entities = entities or []
        cache_key = self._build_cache_key(headline, entities)
        if cache_key in self.cache:
            logger.debug(f"RelevanceScorer cache hit for '{headline[:40]}...'")
            return self.cache[cache_key]

        if not self.groq_api_key:
            logger.warning("RelevanceScorer: GROQ_API_KEY not configured. Defaulting to fallback.")
            return {
                "relevant": False,
                "score": 0.0,
                "reason": "GROQ_API_KEY not configured",
                "disruption_type": "none",
                "affected_domains": [],
            }

        entities_text = ", ".join(entities) if entities else "None specified"
        prompt = _RELEVANCE_PROMPT.format(
            headline=headline or "No headline",
            summary=(summary or "No summary")[:1500],
            entities=entities_text,
        )

        from groq import Groq

        client = Groq(api_key=self.groq_api_key)
        current_model = GROQ_MODEL
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {"role": "system", "content": "You are a supply chain disruption intelligence evaluator. Respond with pure JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=350,
                )

                result_text = response.choices[0].message.content.strip()

                # Clean markdown fencing if present
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()

                parsed = json.loads(result_text)

                # Validate expected fields
                relevant = bool(parsed.get("relevant", False))
                score = float(parsed.get("score", 0.0))
                reason = str(parsed.get("reason", "")).strip()
                disruption_type = str(parsed.get("disruption_type", "none")).strip().lower()
                affected_domains = parsed.get("affected_domains") or []
                if isinstance(affected_domains, list):
                    affected_domains = [str(d).strip().lower() for d in affected_domains if d]
                else:
                    affected_domains = []

                if not relevant and disruption_type == "none":
                    pass
                elif not relevant and score < 0.5:
                    pass

                result = {
                    "relevant": relevant,
                    "score": round(max(0.0, min(1.0, score)), 3),
                    "reason": reason,
                    "disruption_type": disruption_type if relevant else "none",
                    "affected_domains": affected_domains if relevant else [],
                }

                self.cache[cache_key] = result
                return result

            except json.JSONDecodeError as e:
                last_error = f"JSON parse error: {e}"
                logger.warning(f"RelevanceScorer: Failed to parse JSON (attempt {attempt + 1}): {e}")
            except Exception as e:
                last_error = str(e)
                if "429" in str(e) or "rate_limit" in str(e).lower():
                    logger.warning(f"RelevanceScorer: Rate limit on '{current_model}', switching to '{FALLBACK_GROQ_MODEL}'")
                    current_model = FALLBACK_GROQ_MODEL
                else:
                    logger.warning(f"RelevanceScorer error (attempt {attempt + 1}): {e}")

        logger.error(f"RelevanceScorer: All attempts failed for '{headline[:40]}...'. Error: {last_error}")
        return {
            "relevant": False,
            "score": 0.0,
            "reason": f"Scoring error: {last_error}",
            "disruption_type": "none",
            "affected_domains": [],
        }

    async def score_article_async(
        self,
        headline: str,
        summary: str,
        entities: Optional[List[str]] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Asynchronously score an article without blocking the event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.score_article(headline, summary, entities, max_retries),
        )

    def batch_score(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Score multiple articles in sequence.
        """
        results = []
        for item in articles:
            headline = item.get("headline") or item.get("title") or ""
            summary = item.get("summary") or item.get("description") or item.get("content") or ""
            entities = item.get("entities") or []
            relevance = self.score_article(headline, summary, entities)
            results.append({
                "article": item,
                "relevance": relevance,
            })
        return results

    def clear_cache(self):
        """Clear in-memory cache."""
        self.cache.clear()
