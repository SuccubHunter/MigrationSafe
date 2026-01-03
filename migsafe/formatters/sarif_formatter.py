"""SARIF formatter for integration with GitHub Security and other tools."""

import json
import logging
from pathlib import Path
from typing import Any

from .. import __version__
from ..base import AnalyzerResult
from ..models import Issue, IssueSeverity, IssueType
from .base import Formatter

logger = logging.getLogger(__name__)


class SarifFormatter(Formatter):
    """SARIF formatter for OASIS Static Analysis Results Interchange Format standard."""

    # SARIF version 2.1.0
    SARIF_VERSION = "2.1.0"

    # Full mapping IssueType -> MIGXXX
    ISSUE_TYPE_TO_RULE_ID = {
        IssueType.ADD_COLUMN_NOT_NULL: "MIG001",
        IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY: "MIG002",
        IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY: "MIG003",
        IssueType.DROP_COLUMN: "MIG004",
        IssueType.ALTER_COLUMN_TYPE: "MIG005",
        IssueType.EXECUTE_RAW_SQL: "MIG006",
        # SQL patterns
        IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL: "MIG007",
        IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY: "MIG008",
        IssueType.SQL_DROP_TABLE: "MIG009",
        IssueType.SQL_DROP_COLUMN: "MIG010",
        IssueType.SQL_ALTER_COLUMN_TYPE: "MIG011",
        IssueType.SQL_UPDATE_WITHOUT_WHERE: "MIG012",
        IssueType.SQL_DELETE_WITHOUT_WHERE: "MIG013",
        IssueType.SQL_INSERT_WITHOUT_BATCHING: "MIG014",
        IssueType.SQL_LOCK_TABLE: "MIG015",
        IssueType.SQL_TRUNCATE_TABLE: "MIG016",
        IssueType.SQL_BATCH_MIGRATION: "MIG017",
        # JOIN operations
        IssueType.SQL_UPDATE_WITH_JOIN: "MIG018",
        IssueType.SQL_DELETE_WITH_JOIN: "MIG019",
        # Subqueries
        IssueType.SQL_CORRELATED_SUBQUERY: "MIG020",
        IssueType.SQL_SUBQUERY_IN_UPDATE: "MIG021",
        IssueType.SQL_SUBQUERY_IN_DELETE: "MIG022",
        IssueType.SQL_SUBQUERY_WITHOUT_LIMIT: "MIG023",
        # CTE
        IssueType.SQL_RECURSIVE_CTE: "MIG024",
        IssueType.SQL_LARGE_CTE: "MIG025",
        IssueType.SQL_CTE_IN_MIGRATION: "MIG026",
    }

    def format(self, results: list[tuple[Path, AnalyzerResult]]) -> str:
        """Format analysis results as SARIF."""
        try:
            # Data validation
            if not isinstance(results, list):
                raise TypeError(f"results must be a list, got {type(results)}")

            for file_path, result in results:
                if not isinstance(file_path, Path):
                    raise TypeError(f"file_path must be Path, got {type(file_path)}")
                if not isinstance(result, AnalyzerResult):
                    raise TypeError(f"result must be AnalyzerResult, got {type(result)}")

            sarif = {
                "$schema": f"https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-{self.SARIF_VERSION}.json",
                "version": self.SARIF_VERSION,
                "runs": [self._create_run(results)],
            }

            return json.dumps(sarif, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Data validation error when formatting SARIF: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Error formatting SARIF: {e}") from e

    def format_single(self, file_path: Path, result: AnalyzerResult) -> str:
        """Format analysis result for a single file as SARIF."""
        # Data validation
        if not isinstance(file_path, Path):
            raise TypeError(f"file_path must be Path, got {type(file_path)}")
        if not isinstance(result, AnalyzerResult):
            raise TypeError(f"result must be AnalyzerResult, got {type(result)}")

        return self.format([(file_path, result)])

    def _create_run(self, results: list[tuple[Path, AnalyzerResult]]) -> dict[str, Any]:
        """Create run object for SARIF."""
        tool = {
            "driver": {
                "name": "migsafe",
                "version": __version__,
                "informationUri": "https://github.com/SuccubHunter/migsafe",
                "rules": self._create_rules(),
            }
        }

        artifacts: list[dict[str, Any]] = []
        results_list: list[dict[str, Any]] = []

        for file_path, result in results:
            # Add artifact (file)
            artifact_index = len(artifacts)
            artifacts.append({"location": {"uri": str(file_path)}})

            # Filter issues
            filtered_issues = self.filter_issues(result.issues)

            # Validate issues
            for issue in filtered_issues:
                if issue.operation_index < 0:
                    raise ValueError(f"operation_index must be >= 0, got {issue.operation_index}")

            # Create results for each issue
            for issue in filtered_issues:
                results_list.append(self._create_result(issue, file_path, artifact_index))

        return {"tool": tool, "artifacts": artifacts, "results": results_list}

    def _create_rules(self) -> list[dict[str, Any]]:
        """Create rules for all issue types."""
        rules = []

        # Use centralized mapping for rule_id
        rule_mapping = {
            IssueType.ADD_COLUMN_NOT_NULL: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.ADD_COLUMN_NOT_NULL],
                "name": "Add Column Not Null",
                "shortDescription": {"text": "Adding column with NOT NULL without default value"},
                "fullDescription": {
                    "text": ("Adding a column with NOT NULL constraint without a default value can lock the table in production.")
                },
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG001",
            },
            IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY],
                "name": "Create Index Without Concurrently",
                "shortDescription": {"text": "Creating index without CONCURRENTLY"},
                "fullDescription": {
                    "text": "Creating an index without using CONCURRENTLY locks the table for writes in PostgreSQL."
                },
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG002",
            },
            IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY],
                "name": "Drop Index Without Concurrently",
                "shortDescription": {"text": "Dropping index without CONCURRENTLY"},
                "fullDescription": {"text": "Dropping an index without using CONCURRENTLY can lock the table."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG003",
            },
            IssueType.DROP_COLUMN: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.DROP_COLUMN],
                "name": "Drop Column",
                "shortDescription": {"text": "Dropping column from table"},
                "fullDescription": {"text": "Dropping a column can lead to data loss and requires caution."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG004",
            },
            IssueType.ALTER_COLUMN_TYPE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.ALTER_COLUMN_TYPE],
                "name": "Alter Column Type",
                "shortDescription": {"text": "Changing column type"},
                "fullDescription": {"text": "Changing column type can lock the table and lead to data loss."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG005",
            },
            IssueType.EXECUTE_RAW_SQL: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.EXECUTE_RAW_SQL],
                "name": "Execute Raw SQL",
                "shortDescription": {"text": "Executing raw SQL"},
                "fullDescription": {"text": "Executing raw SQL makes analysis difficult and can be unsafe."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG006",
            },
            # SQL patterns
            IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL],
                "name": "SQL Alter Table Add Column Not Null",
                "shortDescription": {"text": "SQL: Adding column with NOT NULL without default value"},
                "fullDescription": {
                    "text": ("SQL operation ALTER TABLE ADD COLUMN with NOT NULL without default value can lock the table.")
                },
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG007",
            },
            IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_CREATE_INDEX_WITHOUT_CONCURRENTLY],
                "name": "SQL Create Index Without Concurrently",
                "shortDescription": {"text": "SQL: Creating index without CONCURRENTLY"},
                "fullDescription": {"text": "SQL operation CREATE INDEX without CONCURRENTLY locks the table for writes."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG008",
            },
            IssueType.SQL_DROP_TABLE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_DROP_TABLE],
                "name": "SQL Drop Table",
                "shortDescription": {"text": "SQL: Dropping table"},
                "fullDescription": {"text": "SQL operation DROP TABLE removes the table and all data. Requires special caution."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG009",
            },
            IssueType.SQL_DROP_COLUMN: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_DROP_COLUMN],
                "name": "SQL Drop Column",
                "shortDescription": {"text": "SQL: Dropping column"},
                "fullDescription": {"text": "SQL operation ALTER TABLE DROP COLUMN removes the column and all its data."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG010",
            },
            IssueType.SQL_ALTER_COLUMN_TYPE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_ALTER_COLUMN_TYPE],
                "name": "SQL Alter Column Type",
                "shortDescription": {"text": "SQL: Changing column type"},
                "fullDescription": {
                    "text": ("SQL operation ALTER TABLE ALTER COLUMN TYPE can lock the table and lead to data loss.")
                },
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG011",
            },
            IssueType.SQL_UPDATE_WITHOUT_WHERE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_UPDATE_WITHOUT_WHERE],
                "name": "SQL Update Without Where",
                "shortDescription": {"text": "SQL: UPDATE without WHERE"},
                "fullDescription": {
                    "text": "SQL operation UPDATE without WHERE clause will update all rows in the table, which can be dangerous."  # noqa: E501
                },
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG012",
            },
            IssueType.SQL_DELETE_WITHOUT_WHERE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_DELETE_WITHOUT_WHERE],
                "name": "SQL Delete Without Where",
                "shortDescription": {"text": "SQL: DELETE without WHERE"},
                "fullDescription": {
                    "text": "SQL operation DELETE without WHERE clause will delete all rows in the table, which is extremely dangerous."  # noqa: E501
                },
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG013",
            },
            IssueType.SQL_INSERT_WITHOUT_BATCHING: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_INSERT_WITHOUT_BATCHING],
                "name": "SQL Insert Without Batching",
                "shortDescription": {"text": "SQL: INSERT without batching"},
                "fullDescription": {
                    "text": "SQL operation INSERT without batching can be inefficient with large amounts of data."
                },
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG014",
            },
            IssueType.SQL_LOCK_TABLE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_LOCK_TABLE],
                "name": "SQL Lock Table",
                "shortDescription": {"text": "SQL: Table locking"},
                "fullDescription": {"text": "SQL operation LOCK TABLE locks the table and can lead to performance issues."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG015",
            },
            IssueType.SQL_TRUNCATE_TABLE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_TRUNCATE_TABLE],
                "name": "SQL Truncate Table",
                "shortDescription": {"text": "SQL: Truncating table"},
                "fullDescription": {
                    "text": "SQL operation TRUNCATE TABLE removes all data from the table. Requires special caution."
                },
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG016",
            },
            IssueType.SQL_BATCH_MIGRATION: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_BATCH_MIGRATION],
                "name": "SQL Batch Migration",
                "shortDescription": {"text": "SQL: Batch migration"},
                "fullDescription": {"text": "Batch migration can be unsafe with large volumes of data."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG017",
            },
            # JOIN operations
            IssueType.SQL_UPDATE_WITH_JOIN: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_UPDATE_WITH_JOIN],
                "name": "SQL Update With Join",
                "shortDescription": {"text": "SQL: UPDATE with JOIN"},
                "fullDescription": {"text": "SQL operation UPDATE with JOIN can be complex and potentially dangerous."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG018",
            },
            IssueType.SQL_DELETE_WITH_JOIN: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_DELETE_WITH_JOIN],
                "name": "SQL Delete With Join",
                "shortDescription": {"text": "SQL: DELETE with JOIN"},
                "fullDescription": {"text": "SQL operation DELETE with JOIN can be complex and potentially dangerous."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG019",
            },
            # Subqueries
            IssueType.SQL_CORRELATED_SUBQUERY: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_CORRELATED_SUBQUERY],
                "name": "SQL Correlated Subquery",
                "shortDescription": {"text": "SQL: Correlated subquery"},
                "fullDescription": {"text": "Correlated subqueries can be inefficient and slow down migration execution."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG020",
            },
            IssueType.SQL_SUBQUERY_IN_UPDATE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_SUBQUERY_IN_UPDATE],
                "name": "SQL Subquery In Update",
                "shortDescription": {"text": "SQL: Subquery in UPDATE"},
                "fullDescription": {"text": "Subqueries in UPDATE can be inefficient and potentially dangerous."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG021",
            },
            IssueType.SQL_SUBQUERY_IN_DELETE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_SUBQUERY_IN_DELETE],
                "name": "SQL Subquery In Delete",
                "shortDescription": {"text": "SQL: Subquery in DELETE"},
                "fullDescription": {"text": "Subqueries in DELETE can be inefficient and potentially dangerous."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG022",
            },
            IssueType.SQL_SUBQUERY_WITHOUT_LIMIT: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_SUBQUERY_WITHOUT_LIMIT],
                "name": "SQL Subquery Without Limit",
                "shortDescription": {"text": "SQL: Subquery without LIMIT"},
                "fullDescription": {"text": "Subqueries without LIMIT can process large amounts of data and be inefficient."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG023",
            },
            # CTE
            IssueType.SQL_RECURSIVE_CTE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_RECURSIVE_CTE],
                "name": "SQL Recursive CTE",
                "shortDescription": {"text": "SQL: Recursive CTE"},
                "fullDescription": {"text": "Recursive CTEs can be complex and potentially dangerous in migrations."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG024",
            },
            IssueType.SQL_LARGE_CTE: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_LARGE_CTE],
                "name": "SQL Large CTE",
                "shortDescription": {"text": "SQL: Large CTE"},
                "fullDescription": {"text": "Large CTEs can be inefficient and consume a lot of memory."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG025",
            },
            IssueType.SQL_CTE_IN_MIGRATION: {
                "id": self.ISSUE_TYPE_TO_RULE_ID[IssueType.SQL_CTE_IN_MIGRATION],
                "name": "SQL CTE In Migration",
                "shortDescription": {"text": "SQL: CTE in migration"},
                "fullDescription": {"text": "Using CTEs in migrations can be complex and requires additional attention."},
                "helpUri": "https://github.com/SuccubHunter/migsafe/docs/rules/MIG026",
            },
        }

        for _issue_type, rule_data in rule_mapping.items():
            rules.append(
                {
                    "id": rule_data["id"],
                    "name": rule_data["name"],
                    "shortDescription": rule_data["shortDescription"],
                    "fullDescription": rule_data["fullDescription"],
                    "helpUri": rule_data["helpUri"],
                    "properties": {"category": "migration-safety"},
                }
            )

        return rules

    def _create_result(self, issue: Issue, file_path: Path, artifact_index: int) -> dict[str, Any]:
        """Create result object for issue."""
        # Data validation
        if not isinstance(issue, Issue):
            raise TypeError(f"issue must be Issue, got {type(issue)}")
        if not isinstance(file_path, Path):
            raise TypeError(f"file_path must be Path, got {type(file_path)}")
        if not isinstance(artifact_index, int) or artifact_index < 0:
            raise ValueError(f"artifact_index must be non-negative int, got {artifact_index}")

        # Map severity to SARIF level
        level_mapping = {IssueSeverity.CRITICAL: "error", IssueSeverity.WARNING: "warning", IssueSeverity.OK: "note"}

        # Get rule ID by issue type from centralized mapping
        rule_id = self.ISSUE_TYPE_TO_RULE_ID.get(issue.type)
        if rule_id is None:
            # Log warning for unknown types
            logger.warning(f"Unknown issue type for SARIF: {issue.type}. Using fallback.")
            rule_id = f"UNKNOWN_{issue.type.value.upper()}"

        result = {
            "ruleId": rule_id,
            "level": level_mapping.get(issue.severity, "note"),
            "message": {"text": issue.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"index": artifact_index, "uri": str(file_path)},
                        "region": {
                            "startLine": 1,  # SARIF requires at least startLine
                            "startColumn": 1,
                        },
                    }
                }
            ],
        }

        # Add additional properties
        properties = {}
        if issue.table:
            properties["table"] = issue.table
        if issue.column:
            properties["column"] = issue.column
        if issue.index:
            properties["index"] = issue.index
        if issue.recommendation:
            properties["recommendation"] = issue.recommendation
        properties["operation_index"] = str(issue.operation_index)

        if properties:
            result["properties"] = properties

        return result
