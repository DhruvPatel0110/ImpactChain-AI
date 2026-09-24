"""
ImpactChain AI — Relevance Monitor

Tracks article ingestion and semantic filtering statistics over time.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RelevanceMonitor:
    """Track filtering accuracy and distribution over time."""

    def __init__(self):
        self.stats: Dict[str, Any] = {
            "total_ingested": 0,
            "total_relevant": 0,
            "total_filtered": 0,
            "by_disruption_type": {},
            "filtering_ratio": 0.0,
        }

    def record(self, article: dict, is_relevant: bool, score: float, disruption_type: str = "none"):
        """Record an ingestion decision."""
        self.stats["total_ingested"] += 1

        if is_relevant:
            self.stats["total_relevant"] += 1
            dtype = disruption_type or article.get("disruption_type", "unknown")
            if dtype and dtype != "none":
                self.stats["by_disruption_type"][dtype] = (
                    self.stats["by_disruption_type"].get(dtype, 0) + 1
                )
        else:
            self.stats["total_filtered"] += 1

        if self.stats["total_ingested"] > 0:
            self.stats["filtering_ratio"] = round(
                self.stats["total_filtered"] / self.stats["total_ingested"], 4
            )

    def report(self) -> Dict[str, Any]:
        """Print and return summary report."""
        summary = {
            "total_ingested": self.stats["total_ingested"],
            "total_relevant": self.stats["total_relevant"],
            "total_filtered": self.stats["total_filtered"],
            "filtering_ratio": f"{self.stats['filtering_ratio']:.1%}",
            "by_disruption_type": self.stats["by_disruption_type"],
        }
        logger.info(
            f"Ingestion Relevance Stats: Total={summary['total_ingested']}, "
            f"Relevant={summary['total_relevant']}, "
            f"Filtered={summary['total_filtered']} ({summary['filtering_ratio']}), "
            f"Types={summary['by_disruption_type']}"
        )
        return summary

    def get_stats(self) -> Dict[str, Any]:
        """Return raw stats dictionary."""
        return dict(self.stats)

    def reset(self):
        """Reset monitoring stats."""
        self.stats = {
            "total_ingested": 0,
            "total_relevant": 0,
            "total_filtered": 0,
            "by_disruption_type": {},
            "filtering_ratio": 0.0,
        }
