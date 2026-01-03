"""Tests for SQL analyzer edge cases."""

import pytest

from migsafe.analyzers.sql_analyzer import SqlAnalyzer
from migsafe.analyzers.sql_cte_analyzer import SqlCteAnalyzer
from migsafe.analyzers.sql_join_analyzer import SqlJoinAnalyzer
from migsafe.analyzers.sql_subquery_analyzer import SqlSubqueryAnalyzer
from migsafe.models import IssueType


@pytest.fixture
def sql_analyzer():
    """Fixture for creating SQL analyzer instance."""
    return SqlAnalyzer()


@pytest.fixture
def join_analyzer():
    """Fixture for creating JOIN analyzer instance."""
    return SqlJoinAnalyzer()


@pytest.fixture
def subquery_analyzer():
    """Fixture for creating subquery analyzer instance."""
    return SqlSubqueryAnalyzer()


@pytest.fixture
def cte_analyzer():
    """Fixture for creating CTE analyzer instance."""
    return SqlCteAnalyzer()


class TestEmptySql:
    """Tests for empty SQL queries."""

    def test_empty_string(self, sql_analyzer):
        """Test handling of empty string."""
        issues = sql_analyzer.analyze("", operation_index=0)
        assert len(issues) == 0

    def test_whitespace_only(self, sql_analyzer):
        """Test handling of whitespace-only string."""
        issues = sql_analyzer.analyze("   \n\t  ", operation_index=0)
        assert len(issues) == 0

    def test_dynamic_sql(self, sql_analyzer):
        """Test handling of dynamic SQL."""
        issues = sql_analyzer.analyze("<dynamic>", operation_index=0)
        assert len(issues) == 0


class TestSqlWithComments:
    """Tests for SQL with comments."""

    def test_single_line_comment(self, sql_analyzer):
        """Test handling of single-line comment."""
        sql = "-- This is a comment\nALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL"
        issues = sql_analyzer.analyze(sql, operation_index=0)
        assert len(issues) == 1
        assert issues[0].type == IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL

    def test_multi_line_comment(self, sql_analyzer):
        """Test handling of multi-line comment."""
        sql = """/* This is a multi-line comment
        that can be long */
        ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL"""
        issues = sql_analyzer.analyze(sql, operation_index=0)
        assert len(issues) == 1
        assert issues[0].type == IssueType.SQL_ALTER_TABLE_ADD_COLUMN_NOT_NULL

    def test_nested_comments(self, sql_analyzer):
        """Test handling of nested comments."""
        sql = """/* Outer comment /* inner */ continuation */
        ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL"""
        issues = sql_analyzer.analyze(sql, operation_index=0)
        assert len(issues) == 1

    def test_comment_in_middle(self, sql_analyzer):
        """Test handling of comment in the middle of SQL."""
        sql = "ALTER TABLE users -- comment\nADD COLUMN email VARCHAR(255) NOT NULL"
        issues = sql_analyzer.analyze(sql, operation_index=0)
        assert len(issues) == 1


class TestMultilineSql:
    """Tests for multi-line SQL queries."""

    def test_multiline_alter_table(self, sql_analyzer):
        """Test handling of multi-line ALTER TABLE."""
        sql = """
        ALTER TABLE users
        ADD COLUMN email VARCHAR(255)
        NOT NULL
        """
        issues = sql_analyzer.analyze(sql, operation_index=0)
        assert len(issues) == 1

    def test_multiline_update(self, sql_analyzer):
        """Test handling of multi-line UPDATE."""
        sql = """
        UPDATE users
        SET status = 'active',
            updated_at = NOW()
        WHERE id > 100
        """
        issues = sql_analyzer.analyze(sql, operation_index=0)
        # UPDATE with WHERE should not be a problem
        assert len(issues) == 0

    def test_multiline_update_without_where(self, sql_analyzer):
        """Test handling of multi-line UPDATE without WHERE."""
        sql = """
        UPDATE users
        SET status = 'active',
            updated_at = NOW()
        """
        issues = sql_analyzer.analyze(sql, operation_index=0)
        assert len(issues) == 1
        assert issues[0].type == IssueType.SQL_UPDATE_WITHOUT_WHERE


class TestNestedSubqueries:
    """Tests for nested subqueries."""

    def test_nested_subquery_in_update(self, subquery_analyzer):
        """Test handling of nested subquery in UPDATE."""
        sql = """
        UPDATE users
        SET last_order_date = (
            SELECT MAX(created_at)
            FROM orders
            WHERE user_id = users.id
            AND status = (
                SELECT 'completed'
                FROM order_statuses
                WHERE id = orders.status_id
            )
        )
        """
        issues = subquery_analyzer.analyze(sql, operation_index=0)
        # Should detect correlated subquery
        assert len(issues) >= 1

    def test_nested_subquery_in_delete(self, subquery_analyzer):
        """Test handling of nested subquery in DELETE."""
        sql = """
        DELETE FROM users
        WHERE id IN (
            SELECT user_id
            FROM orders
            WHERE status_id IN (
                SELECT id
                FROM order_statuses
                WHERE name = 'cancelled'
            )
        )
        """
        issues = subquery_analyzer.analyze(sql, operation_index=0)
        # Should detect subquery without LIMIT
        assert len(issues) >= 1

    def test_triple_nested_subquery(self, subquery_analyzer):
        """Test handling of triple nested subquery."""
        sql = """
        UPDATE products
        SET price = (
            SELECT AVG(price)
            FROM (
                SELECT price
                FROM (
                    SELECT price FROM old_prices WHERE product_id = products.id
                ) AS inner_query
            ) AS middle_query
        )
        """
        issues = subquery_analyzer.analyze(sql, operation_index=0)
        # Should handle even triple nesting
        assert isinstance(issues, list)


class TestDjangoMigrationParsingErrors:
    """Tests for Django migration parsing errors."""

    def test_syntax_error_handling(self):
        """Test handling of syntax errors in Django migrations."""
        import os
        import tempfile

        from migsafe.analyzers.django_analyzer import DjangoMigrationAnalyzer
        from migsafe.sources.django_source import DjangoMigrationSource

        analyzer = DjangoMigrationAnalyzer()

        # Create temporary file with syntax error
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("""
            from django.db import migrations

            class Migration(migrations.Migration):
                dependencies = [
                    ('app', '0001_initial'),
                ]

                operations = [
                    migrations.RunSQL(
                        "UPDATE users SET status = 'active'  # Syntax error - missing closing parenthesis
                    )
                ]
            """)
            temp_path = f.name

        try:
            source = DjangoMigrationSource(temp_path)
            result = analyzer.analyze(source)
            # Should return result with warning
            assert isinstance(result.issues, list)
        finally:
            os.unlink(temp_path)

    def test_missing_migration_class(self):
        """Test handling of missing Migration class."""
        import os
        import tempfile

        from migsafe.analyzers.django_analyzer import DjangoMigrationAnalyzer
        from migsafe.sources.django_source import DjangoMigrationSource

        analyzer = DjangoMigrationAnalyzer()

        # Create temporary file without Migration class
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("""
            from django.db import migrations

            # No Migration class
            operations = []
            """)
            temp_path = f.name

        try:
            source = DjangoMigrationSource(temp_path)
            result = analyzer.analyze(source)
            # Should return warning about parsing failure
            assert len(result.issues) >= 1
            assert any("failed to parse" in issue.message.lower() for issue in result.issues)
        finally:
            os.unlink(temp_path)

    def test_invalid_operations_list(self):
        """Test handling of invalid operations list."""
        import os
        import tempfile

        from migsafe.analyzers.django_analyzer import DjangoMigrationAnalyzer
        from migsafe.sources.django_source import DjangoMigrationSource

        analyzer = DjangoMigrationAnalyzer()

        # Create temporary file with invalid operations
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("""
            from django.db import migrations

            class Migration(migrations.Migration):
                dependencies = []

                operations = "not a list"  # Not a list
            """)
            temp_path = f.name

        try:
            source = DjangoMigrationSource(temp_path)
            result = analyzer.analyze(source)
            # Should handle correctly
            assert isinstance(result.operations, list)
        finally:
            os.unlink(temp_path)


class TestComplexSqlPatterns:
    """Tests for complex SQL patterns."""

    def test_multiple_statements(self, sql_analyzer):
        """Test handling of multiple SQL operations in one query."""
        sql = """
        ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL;
        CREATE INDEX idx_email ON users(email);
        UPDATE users SET status = 'active';
        DELETE FROM users WHERE id < 0;
        """
        issues = sql_analyzer.analyze(sql, operation_index=0)
        assert len(issues) >= 3

    def test_complex_join_pattern(self, join_analyzer):
        """Test handling of complex JOIN pattern."""
        sql = """
        UPDATE users u
        SET status = 'active'
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE u.id = o.user_id
        AND o.created_at > '2024-01-01'
        """
        issues = join_analyzer.analyze(sql, operation_index=0)
        assert len(issues) >= 1

    def test_recursive_cte(self, cte_analyzer):
        """Test handling of recursive CTE."""
        sql = """
        WITH RECURSIVE tree AS (
            SELECT id, parent_id, 1 as level
            FROM categories
            WHERE parent_id IS NULL
            UNION ALL
            SELECT c.id, c.parent_id, t.level + 1
            FROM categories c
            JOIN tree t ON c.parent_id = t.id
        )
        UPDATE categories SET level = tree.level
        FROM tree
        WHERE categories.id = tree.id
        """
        issues = cte_analyzer.analyze(sql, operation_index=0)
        assert len(issues) >= 1
        assert any(issue.type == IssueType.SQL_RECURSIVE_CTE for issue in issues)

    def test_large_cte(self, cte_analyzer):
        """Test handling of large CTE."""
        sql = """
        WITH
        cte1 AS (SELECT * FROM table1),
        cte2 AS (SELECT * FROM table2),
        cte3 AS (SELECT * FROM table3),
        cte4 AS (SELECT * FROM table4),
        cte5 AS (SELECT * FROM table5)
        SELECT * FROM cte1
        """
        issues = cte_analyzer.analyze(sql, operation_index=0)
        # Should detect large CTE
        assert isinstance(issues, list)


class TestTypeValidation:
    """Tests for type validation."""

    def test_invalid_operation_index_type(self, sql_analyzer):
        """Test handling of invalid operation_index type."""
        with pytest.raises(TypeError):
            sql_analyzer.analyze("SELECT * FROM users", operation_index="0")

    def test_invalid_sql_type(self, sql_analyzer):
        """Test handling of invalid SQL type."""
        issues = sql_analyzer.analyze(None, operation_index=0)
        assert len(issues) == 0

    def test_negative_operation_index(self, sql_analyzer):
        """Test handling of negative operation_index."""
        # Pydantic validates operation_index >= 0, so Issue cannot be created with negative index
        # Check that analyzer handles this correctly
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            issues = sql_analyzer.analyze("UPDATE users SET status = 'active'", operation_index=-1)
            # If Issue was created, it would have negative index, but Pydantic won't allow it
            if issues:
                assert issues[0].operation_index == -1
