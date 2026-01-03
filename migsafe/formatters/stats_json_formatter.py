"""JSON formatter for migration statistics."""

import json
from datetime import datetime
from typing import Any

from .. import __version__
from ..stats import MigrationStats
from .base import StatsFormatter


class StatsJsonFormatter(StatsFormatter):
    """JSON formatter for statistics."""

    def format(self, stats: MigrationStats, recommendations: list[dict[str, Any]]) -> str:
        """
        Format statistics as JSON.

        Args:
            stats: Statistics object
            recommendations: List of recommendations

        Returns:
            JSON string
        """
        data = {
            "version": __version__,
            "generated_at": datetime.now().isoformat(),
            "summary": stats.get_summary(),
            "migrations": stats.migrations,
            "top_issues": stats.get_top_issues(limit=10),
            "top_rules": stats.get_top_rules(limit=10),
            "recommendations": recommendations,
        }

        return json.dumps(data, ensure_ascii=False, indent=2)
