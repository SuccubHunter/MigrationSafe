"""JUnit XML formatter for CI system integration."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple
from xml.sax.saxutils import escape as xml_escape

from ..base import AnalyzerResult
from ..models import Issue, IssueSeverity
from .base import Formatter


class JUnitFormatter(Formatter):
    """JUnit XML formatter for CI/CD systems."""

    def _count_issues_by_severity(self, issues: List[Issue]) -> Dict[str, int]:
        """
        Count issues by severity levels.

        Args:
            issues: List of issues to count

        Returns:
            Dictionary with issue counts by levels: {"critical": int, "warning": int}
        """
        critical_count = sum(1 for issue in issues if issue.severity == IssueSeverity.CRITICAL)
        warning_count = sum(1 for issue in issues if issue.severity == IssueSeverity.WARNING)
        return {"critical": critical_count, "warning": warning_count}

    def format(self, results: List[Tuple[Path, AnalyzerResult]]) -> str:
        """Format analysis results as JUnit XML."""
        try:
            root = ET.Element("testsuites")
            root.set("name", "migsafe")
            root.set("tests", str(len(results)))

            # Count total number of issues
            total_failures = 0
            total_errors = 0

            # Handle empty results list
            if not results:
                root.set("failures", "0")
                root.set("errors", "0")
                ET.indent(root, space="  ")
                return ET.tostring(root, encoding="unicode", xml_declaration=True)

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

                # Critical issues = errors, warnings = failures
                counts = self._count_issues_by_severity(filtered_issues)
                critical_count = counts["critical"]
                warning_count = counts["warning"]

                total_errors += critical_count
                total_failures += warning_count

                # Create testsuite for each migration
                testsuite = ET.SubElement(root, "testsuite")
                testsuite.set("name", file_path.name)
                testsuite.set("tests", "1")  # Each migration = one test
                testsuite.set("failures", str(warning_count))
                testsuite.set("errors", str(critical_count))
                testsuite.set("time", "0")

                # Create testcase
                testcase = ET.SubElement(testsuite, "testcase")
                testcase.set("name", file_path.name)
                testcase.set("classname", str(file_path))

                # If there are issues, add failure or error
                if critical_count > 0:
                    error = ET.SubElement(testcase, "error")
                    error.set("type", "critical")
                    error.text = self._format_issues_summary(filtered_issues, critical=True)

                if warning_count > 0:
                    failure = ET.SubElement(testcase, "failure")
                    failure.set("type", "warning")
                    failure.text = self._format_issues_summary(filtered_issues, warning=True)

            root.set("failures", str(total_failures))
            root.set("errors", str(total_errors))

            # Format XML
            ET.indent(root, space="  ")
            return ET.tostring(root, encoding="unicode", xml_declaration=True)
        except ET.ParseError as e:
            raise RuntimeError(f"Error parsing XML: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Error formatting JUnit XML: {e}") from e

    def format_single(self, file_path: Path, result: AnalyzerResult) -> str:
        """Format analysis result for a single file as JUnit XML."""
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

            root = ET.Element("testsuites")
            root.set("name", "migsafe")
            root.set("tests", "1")

            counts = self._count_issues_by_severity(filtered_issues)
            critical_count = counts["critical"]
            warning_count = counts["warning"]

            root.set("failures", str(warning_count))
            root.set("errors", str(critical_count))

            testsuite = ET.SubElement(root, "testsuite")
            testsuite.set("name", file_path.name)
            testsuite.set("tests", "1")
            testsuite.set("failures", str(warning_count))
            testsuite.set("errors", str(critical_count))
            testsuite.set("time", "0")

            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("name", file_path.name)
            testcase.set("classname", str(file_path))

            if critical_count > 0:
                error = ET.SubElement(testcase, "error")
                error.set("type", "critical")
                error.text = self._format_issues_summary(filtered_issues, critical=True)

            if warning_count > 0:
                failure = ET.SubElement(testcase, "failure")
                failure.set("type", "warning")
                failure.text = self._format_issues_summary(filtered_issues, warning=True)

            ET.indent(root, space="  ")
            return ET.tostring(root, encoding="unicode", xml_declaration=True)
        except ET.ParseError as e:
            raise RuntimeError(f"Error parsing XML: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Error formatting JUnit XML: {e}") from e

    def _format_issues_summary(self, issues: List[Issue], critical: bool = False, warning: bool = False) -> str:
        """Format issues summary for JUnit."""
        filtered = issues
        if critical:
            filtered = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        elif warning:
            filtered = [i for i in issues if i.severity == IssueSeverity.WARNING]

        lines = []
        for issue in filtered:
            type_name = self._format_issue_type_name(issue)
            lines.append(f"[{issue.severity.value.upper()}] {xml_escape(type_name)}")
            lines.append(f"  Message: {xml_escape(issue.message)}")
            if issue.table:
                lines.append(f"  Table: {xml_escape(issue.table)}")
            if issue.column:
                lines.append(f"  Column: {xml_escape(issue.column)}")
            if issue.index:
                lines.append(f"  Index: {xml_escape(issue.index)}")
            if issue.recommendation:
                lines.append(f"  Recommendation: {xml_escape(issue.recommendation)}")
            lines.append("")

        return "\n".join(lines)
