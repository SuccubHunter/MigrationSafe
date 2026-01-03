"""HTML formatter for analysis results output."""

import html
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from ..base import AnalyzerResult
from ..models import Issue, IssueSeverity
from .base import Formatter


class HtmlFormatter(Formatter):
    """HTML formatter for beautiful display in browser."""

    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alembic Migration Analysis Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .summary {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary-stats {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }}
        .stat {{
            flex: 1;
            min-width: 150px;
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }}
        .stat-critical {{
            background-color: #fee;
            border-left: 4px solid #e74c3c;
        }}
        .stat-warning {{
            background-color: #fff8e1;
            border-left: 4px solid #f39c12;
        }}
        .stat-ok {{
            background-color: #e8f5e9;
            border-left: 4px solid #27ae60;
        }}
        .migration {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .migration-header {{
            font-size: 1.2em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .issue {{
            margin: 15px 0;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid;
        }}
        .issue-critical {{
            background-color: #fee;
            border-color: #e74c3c;
        }}
        .issue-warning {{
            background-color: #fff8e1;
            border-color: #f39c12;
        }}
        .issue-ok {{
            background-color: #e8f5e9;
            border-color: #27ae60;
        }}
        .issue-header {{
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .issue-details {{
            margin: 10px 0;
            color: #666;
        }}
        .issue-recommendation {{
            margin-top: 10px;
            padding: 10px;
            background-color: #f9f9f9;
            border-radius: 4px;
            font-style: italic;
        }}
        .no-issues {{
            text-align: center;
            padding: 40px;
            color: #27ae60;
            font-size: 1.2em;
        }}
    </style>
</head>
<body>
    <h1>📊 Alembic Migration Analysis Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <div class="summary-stats">
            <div class="stat stat-critical">
                <div style="font-size: 2em; font-weight: bold; color: #e74c3c;">{critical_count}</div>
                <div>Critical</div>
            </div>
            <div class="stat stat-warning">
                <div style="font-size: 2em; font-weight: bold; color: #f39c12;">{warning_count}</div>
                <div>Warnings</div>
            </div>
            <div class="stat stat-ok">
                <div style="font-size: 2em; font-weight: bold; color: #27ae60;">{ok_count}</div>
                <div>Informational</div>
            </div>
            <div class="stat">
                <div style="font-size: 2em; font-weight: bold; color: #3498db;">{total_migrations}</div>
                <div>Migrations</div>
            </div>
        </div>
        <p style="margin-top: 15px; color: #666;">
            Analysis date: {timestamp}
        </p>
    </div>
    {migrations_html}
</body>
</html>
"""

    def format(self, results: List[Tuple[Path, AnalyzerResult]]) -> str:
        """Format analysis results as HTML."""
        try:
            # Calculate statistics
            total_critical = 0
            total_warning = 0
            total_ok = 0

            migrations_html_parts = []

            for file_path, result in results:
                filtered_issues = self.filter_issues(result.issues)

                for issue in filtered_issues:
                    if issue.severity == IssueSeverity.CRITICAL:
                        total_critical += 1
                    elif issue.severity == IssueSeverity.WARNING:
                        total_warning += 1
                    elif issue.severity == IssueSeverity.OK:
                        total_ok += 1

                migrations_html_parts.append(self._format_migration(file_path, result, filtered_issues))

            migrations_html = "\n".join(migrations_html_parts)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return self.HTML_TEMPLATE.format(
                critical_count=total_critical,
                warning_count=total_warning,
                ok_count=total_ok,
                total_migrations=len(results),
                timestamp=timestamp,
                migrations_html=migrations_html,
            )
        except Exception as e:
            raise RuntimeError(f"Error formatting HTML: {e}") from e

    def format_single(self, file_path: Path, result: AnalyzerResult) -> str:
        """Format analysis result for a single file as HTML."""
        try:
            # Data validation
            if not isinstance(file_path, Path):
                raise TypeError(f"file_path must be Path, got {type(file_path)}")
            if not isinstance(result, AnalyzerResult):
                raise TypeError(f"result must be AnalyzerResult, got {type(result)}")

            filtered_issues = self.filter_issues(result.issues)
            return self._format_migration(file_path, result, filtered_issues)
        except Exception as e:
            raise RuntimeError(f"Error formatting HTML: {e}") from e

    def _format_migration(self, file_path: Path, result: AnalyzerResult, issues: List[Issue]) -> str:
        """Format a single migration."""
        # Data validation
        if not isinstance(file_path, Path):
            raise TypeError(f"file_path must be Path, got {type(file_path)}")
        if not isinstance(result, AnalyzerResult):
            raise TypeError(f"result must be AnalyzerResult, got {type(result)}")
        if not isinstance(issues, list):
            raise TypeError(f"issues must be a list, got {type(issues)}")

        # Validate issues
        for issue in issues:
            if issue.operation_index < 0:
                raise ValueError(f"operation_index must be >= 0, got {issue.operation_index}")
        if not issues:
            escaped_file_name = html.escape(file_path.name)
            return f"""
    <div class="migration">
        <div class="migration-header">📄 {escaped_file_name}</div>
        <div class="no-issues">✅ No issues found! Migration is safe.</div>
    </div>
"""

        issues_html = []
        for issue in issues:
            severity_class = f"issue-{issue.severity.value}"
            emoji = {IssueSeverity.CRITICAL: "🔴", IssueSeverity.WARNING: "🟡", IssueSeverity.OK: "🟢"}.get(issue.severity, "⚪")

            type_name = self._format_issue_type_name(issue)

            details = []
            if issue.table:
                details.append(f"<strong>Table:</strong> {html.escape(issue.table)}")
            if issue.column:
                details.append(f"<strong>Column:</strong> {html.escape(issue.column)}")
            if issue.index:
                details.append(f"<strong>Index:</strong> {html.escape(issue.index)}")
            details.append(f"<strong>Operation:</strong> #{issue.operation_index + 1}")

            details_html = "<br>".join(details) if details else ""

            recommendation_html = ""
            if issue.recommendation:
                # Escape HTML and replace line breaks with <br>
                escaped_rec = html.escape(issue.recommendation)
                escaped_rec = escaped_rec.replace("\n", "<br>")
                recommendation_html = f"""
            <div class="issue-recommendation">
                <strong>Recommendation:</strong><br>
                {escaped_rec}
            </div>
"""

            # Escape all user data
            escaped_message = html.escape(issue.message)
            escaped_type_name = html.escape(type_name)

            issues_html.append(f"""
        <div class="issue {severity_class}">
            <div class="issue-header">
                {emoji} [{issue.severity.value.upper()}] {escaped_type_name}
            </div>
            <div class="issue-details">
                {details_html}
            </div>
            <div style="margin-top: 10px;">
                <strong>Message:</strong> {escaped_message}
            </div>
            {recommendation_html}
        </div>
""")

        # Escape file path
        escaped_file_path = html.escape(str(file_path))
        escaped_file_name = html.escape(file_path.name)

        return f"""
    <div class="migration">
        <div class="migration-header">📄 {escaped_file_name}</div>
        <div style="color: #666; margin-bottom: 15px;">
            Path: {escaped_file_path}<br>
            Operations: {len(result.operations)} | Issues: {len(issues)}
        </div>
        {"".join(issues_html)}
    </div>
"""
