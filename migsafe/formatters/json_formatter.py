"""JSON formatter for analysis results output."""

import json
from pathlib import Path
from typing import Any

from .. import __version__
from ..base import AnalyzerResult
from .base import Formatter


class JsonFormatter(Formatter):
    """JSON formatter for machine-readable output."""

    def format(self, results: list[tuple[Path, AnalyzerResult]]) -> str:
        """Format analysis results as JSON."""
        try:
            output: dict[str, Any] = {
                "version": __version__,
                "summary": {"total_migrations": len(results), "total_issues": 0, "critical": 0, "warning": 0, "ok": 0},
                "migrations": [],
            }

            for file_path, result in results:
                # Data validation
                if not isinstance(file_path, Path):
                    raise TypeError(f"file_path must be Path, got {type(file_path)}")
                if not isinstance(result, AnalyzerResult):
                    raise TypeError(f"result must be AnalyzerResult, got {type(result)}")

                filtered_issues = self.filter_issues(result.issues)

                # Validate issues
                for issue in filtered_issues:
                    if issue.operation_index < 0:
                        raise ValueError(f"operation_index must be >= 0, got {issue.operation_index}")

                # Update statistics
                output["summary"]["total_issues"] += len(filtered_issues)
                for issue in filtered_issues:
                    output["summary"][issue.severity.value] += 1

                # Add migration information
                migration_data = {
                    "file": str(file_path),
                    "file_name": file_path.name,
                    "operations_count": len(result.operations),
                    "issues_count": len(filtered_issues),
                    "issues": [self._issue_to_dict(issue) for issue in filtered_issues],
                }
                output["migrations"].append(migration_data)

            return json.dumps(output, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Data validation error when formatting JSON: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Error formatting JSON: {e}") from e

    def format_single(self, file_path: Path, result: AnalyzerResult) -> str:
        """Format analysis result for a single file as JSON."""
        try:
            # Data validation
            if not isinstance(file_path, Path):
                raise TypeError(f"file_path must be Path, got {type(file_path)}")
            if not isinstance(result, AnalyzerResult):
                raise TypeError(f"result must be AnalyzerResult, got {type(result)}")

            filtered_issues = self.filter_issues(result.issues)

            # Validate issues
            for issue in filtered_issues:
                if issue.operation_index < 0:
                    raise ValueError(f"operation_index must be >= 0, got {issue.operation_index}")

            output = {
                "file": str(file_path),
                "file_name": file_path.name,
                "operations_count": len(result.operations),
                "issues_count": len(filtered_issues),
                "issues": [self._issue_to_dict(issue) for issue in filtered_issues],
            }

            return json.dumps(output, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Data validation error when formatting JSON: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Error formatting JSON: {e}") from e

    def _issue_to_dict(self, issue) -> dict[str, Any]:
        """Convert Issue to dictionary."""
        return {
            "severity": issue.severity.value,
            "type": issue.type.value,
            "message": issue.message,
            "operation_index": issue.operation_index,
            "recommendation": issue.recommendation,
            "table": issue.table,
            "column": issue.column,
            "index": issue.index,
        }
