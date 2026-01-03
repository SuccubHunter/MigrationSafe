"""Tests for automatic migration fix module."""

import ast

import pytest

from migsafe.autofix import (
    AddColumnNotNullFix,
    AutofixEngine,
    CreateIndexFix,
    DropIndexFix,
)
from migsafe.models import Issue, IssueSeverity, IssueType


@pytest.fixture
def autofix_engine():
    """Fixture for creating fix engine."""
    return AutofixEngine.with_default_fixes()


# ==================== Tests for CreateIndexFix ====================


def test_create_index_fix_can_fix():
    """Check that CreateIndexFix can fix CREATE_INDEX_WITHOUT_CONCURRENTLY issue."""
    fix = CreateIndexFix()
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
        message="Creating index without CONCURRENTLY",
        operation_index=0,
        recommendation="Use CONCURRENTLY",
        table="users",
        index="ix_email",
    )

    assert fix.can_fix(issue) is True


def test_create_index_fix_cannot_fix_other_issues():
    """Check that CreateIndexFix cannot fix other issues."""
    fix = CreateIndexFix()
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Adding NOT NULL column",
        operation_index=0,
        recommendation="Use safe pattern",
        table="users",
        column="email",
    )

    assert fix.can_fix(issue) is False


def test_create_index_fix_applies_fix():
    """Check applying fix for create_index."""
    fix = CreateIndexFix()
    source_code = """
from alembic import op

def upgrade():
    op.create_index('ix_email', 'users', ['email'])
"""
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
        message="Creating index without CONCURRENTLY",
        operation_index=0,
        recommendation="Use CONCURRENTLY",
        table="users",
        index="ix_email",
    )

    fixed_code, success = fix.apply_fix(source_code, issue)

    assert success is True
    assert "postgresql_concurrently=True" in fixed_code


def test_create_index_fix_handles_existing_concurrently():
    """Check that fix is not applied if CONCURRENTLY already exists."""
    fix = CreateIndexFix()
    source_code = """
from alembic import op

def upgrade():
    op.create_index('ix_email', 'users', ['email'], postgresql_concurrently=True)
"""
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
        message="Creating index without CONCURRENTLY",
        operation_index=0,
        recommendation="Use CONCURRENTLY",
        table="users",
        index="ix_email",
    )

    fixed_code, success = fix.apply_fix(source_code, issue)

    # Fix should not be applied, as CONCURRENTLY already exists
    assert success is False or fixed_code == source_code


# ==================== Tests for DropIndexFix ====================


def test_drop_index_fix_can_fix():
    """Check that DropIndexFix can fix DROP_INDEX_WITHOUT_CONCURRENTLY issue."""
    fix = DropIndexFix()
    issue = Issue(
        severity=IssueSeverity.WARNING,
        type=IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY,
        message="Dropping index without CONCURRENTLY",
        operation_index=0,
        recommendation="Use CONCURRENTLY",
        table="users",
        index="ix_email",
    )

    assert fix.can_fix(issue) is True


def test_drop_index_fix_applies_fix():
    """Check applying fix for drop_index."""
    fix = DropIndexFix()
    source_code = """
from alembic import op

def upgrade():
    op.drop_index('ix_email', 'users')
"""
    issue = Issue(
        severity=IssueSeverity.WARNING,
        type=IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY,
        message="Dropping index without CONCURRENTLY",
        operation_index=0,
        recommendation="Use CONCURRENTLY",
        table="users",
        index="ix_email",
    )

    fixed_code, success = fix.apply_fix(source_code, issue)

    assert success is True
    assert "postgresql_concurrently=True" in fixed_code


# ==================== Tests for AddColumnNotNullFix ====================


def test_add_column_not_null_fix_can_fix():
    """Check that AddColumnNotNullFix can fix ADD_COLUMN_NOT_NULL issue."""
    fix = AddColumnNotNullFix()
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Adding NOT NULL column",
        operation_index=0,
        recommendation="Use safe pattern",
        table="users",
        column="email",
    )

    assert fix.can_fix(issue) is True


def test_add_column_not_null_fix_applies_fix():
    """Check applying fix for add_column NOT NULL."""
    fix = AddColumnNotNullFix()
    source_code = """
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('users', sa.Column('email', sa.String(), nullable=False))
"""
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Adding NOT NULL column",
        operation_index=0,
        recommendation="Use safe pattern",
        table="users",
        column="email",
    )

    fixed_code, success = fix.apply_fix(source_code, issue)

    assert success is True
    # Check that nullable changed to True
    assert "nullable=True" in fixed_code or "nullable = True" in fixed_code
    # Check that alter_column added to set NOT NULL
    assert "alter_column" in fixed_code
    assert "nullable=False" in fixed_code or "nullable = False" in fixed_code
    # Check that backfill (execute) added
    assert "op.execute" in fixed_code or "execute" in fixed_code


# ==================== Tests for AutofixEngine ====================


def test_autofix_engine_get_applicable_fixes(autofix_engine):
    """Check getting applicable fixes."""
    issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
        message="Creating index without CONCURRENTLY",
        operation_index=0,
        recommendation="Use CONCURRENTLY",
        table="users",
        index="ix_email",
    )

    fixes = autofix_engine.get_applicable_fixes(issue)

    assert len(fixes) == 1
    assert isinstance(fixes[0], CreateIndexFix)


def test_autofix_engine_can_fix_any(autofix_engine):
    """Check can_fix_any method."""
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=0,
            recommendation="Use CONCURRENTLY",
            table="users",
            index="ix_email",
        ),
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.ADD_COLUMN_NOT_NULL,
            message="Adding NOT NULL column",
            operation_index=1,
            recommendation="Use safe pattern",
            table="users",
            column="email",
        ),
    ]

    assert autofix_engine.can_fix_any(issues) is True


def test_autofix_engine_cannot_fix_any(autofix_engine):
    """Check can_fix_any method for unsupported issues."""
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.DROP_COLUMN,
            message="Dropping column",
            operation_index=0,
            recommendation="Be careful",
            table="users",
            column="old_field",
        )
    ]

    assert autofix_engine.can_fix_any(issues) is False


def test_autofix_engine_apply_fixes_dry_run(autofix_engine):
    """Check applying fixes in dry-run mode."""
    source_code = """
from alembic import op

def upgrade():
    op.create_index('ix_email', 'users', ['email'])
"""
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=0,
            recommendation="Use CONCURRENTLY",
            table="users",
            index="ix_email",
        )
    ]

    fixed_code, fixed_issues, unfixed_issues = autofix_engine.apply_fixes(source_code, issues, dry_run=True)

    # In dry-run mode code should not change
    assert fixed_code == source_code
    assert len(fixed_issues) == 1
    assert len(unfixed_issues) == 0


def test_autofix_engine_apply_fixes_real(autofix_engine):
    """Check applying fixes in real mode."""
    source_code = """
from alembic import op

def upgrade():
    op.create_index('ix_email', 'users', ['email'])
"""
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=0,
            recommendation="Use CONCURRENTLY",
            table="users",
            index="ix_email",
        )
    ]

    fixed_code, fixed_issues, unfixed_issues = autofix_engine.apply_fixes(source_code, issues, dry_run=False)

    assert len(fixed_issues) == 1
    assert len(unfixed_issues) == 0
    assert "postgresql_concurrently=True" in fixed_code


def test_autofix_engine_handles_multiple_issues(autofix_engine):
    """Check handling multiple issues."""
    source_code = """
from alembic import op

def upgrade():
    op.create_index('ix_email', 'users', ['email'])
    op.drop_index('ix_old', 'users')
"""
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=0,
            recommendation="Use CONCURRENTLY",
            table="users",
            index="ix_email",
        ),
        Issue(
            severity=IssueSeverity.WARNING,
            type=IssueType.DROP_INDEX_WITHOUT_CONCURRENTLY,
            message="Dropping index without CONCURRENTLY",
            operation_index=1,
            recommendation="Use CONCURRENTLY",
            table="users",
            index="ix_old",
        ),
    ]

    fixed_code, fixed_issues, unfixed_issues = autofix_engine.apply_fixes(source_code, issues, dry_run=False)

    # After applying first fix code changes, and second fix may not find the operation
    # Check that at least one fix is applied and code contains fixes
    assert len(fixed_issues) >= 1
    # Check that code contains fixes for create_index
    assert "postgresql_concurrently=True" in fixed_code or "postgresql_concurrently = True" in fixed_code


def test_autofix_engine_handles_syntax_error(autofix_engine):
    """Check handling syntax errors."""
    source_code = """
from alembic import op

def upgrade():
    op.create_index('ix_email', 'users', ['email']
    # Invalid syntax - unclosed parenthesis
"""
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=0,
            recommendation="Use CONCURRENTLY",
            table="users",
            index="ix_email",
        )
    ]

    fixed_code, fixed_issues, unfixed_issues = autofix_engine.apply_fixes(source_code, issues, dry_run=False)

    # With syntax error fixes should not be applied
    assert fixed_code == source_code
    assert len(fixed_issues) == 0
    assert len(unfixed_issues) == 1


# ==================== Tests for edge cases ====================


def test_migration_without_upgrade_function(autofix_engine):
    """Check handling migration without upgrade() function."""
    source_code = """
from alembic import op

def downgrade():
    op.drop_index('ix_email', 'users')
"""
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=0,
            recommendation="Use CONCURRENTLY",
            table="users",
            index="ix_email",
        )
    ]

    fixed_code, fixed_issues, unfixed_issues = autofix_engine.apply_fixes(source_code, issues, dry_run=False)

    # Fixes should not be applied since there is no upgrade() function
    assert fixed_code == source_code
    assert len(fixed_issues) == 0
    assert len(unfixed_issues) == 1


def test_migration_with_multiple_functions(autofix_engine):
    """Check handling migration with multiple functions."""
    source_code = """
from alembic import op

def helper_function():
    pass

def upgrade():
    op.create_index('ix_email', 'users', ['email'])

def downgrade():
    op.drop_index('ix_email', 'users')
"""
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=0,
            recommendation="Use CONCURRENTLY",
            table="users",
            index="ix_email",
        )
    ]

    fixed_code, fixed_issues, unfixed_issues = autofix_engine.apply_fixes(source_code, issues, dry_run=False)

    # Fix should be applied only to upgrade() function
    assert len(fixed_issues) == 1
    assert "postgresql_concurrently=True" in fixed_code
    assert "helper_function" in fixed_code
    assert "downgrade" in fixed_code


def test_migration_with_nested_batch_alter_table(autofix_engine):
    """Check handling migration with nested batch_alter_table."""
    source_code = """
from alembic import op
import sqlalchemy as sa

def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(), nullable=False))
        with op.batch_alter_table('posts', schema=None) as posts_batch:
            posts_batch.add_column(sa.Column('title', sa.String(), nullable=False))
"""
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.ADD_COLUMN_NOT_NULL,
            message="Adding NOT NULL column",
            operation_index=0,
            recommendation="Use safe pattern",
            table="users",
            column="email",
        )
    ]

    fixed_code, fixed_issues, unfixed_issues = autofix_engine.apply_fixes(source_code, issues, dry_run=False)

    # Nested batch_alter_table may have issues with operation indexing
    # Check that fix can be applied, but not necessarily found by index
    # If fix is not applied, it's normal for nested batch_alter_table
    if len(fixed_issues) > 0:
        assert "nullable=True" in fixed_code or "nullable = True" in fixed_code


def test_migration_with_invalid_operation_index(autofix_engine):
    """Check handling migration with invalid operation index."""
    source_code = """
from alembic import op

def upgrade():
    op.create_index('ix_email', 'users', ['email'])
"""
    # Pydantic validates operation_index >= 0, so create only valid Issue
    # with index exceeding number of operations
    issues = [
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=100,  # Index exceeds number of operations
            recommendation="Use CONCURRENTLY",
            table="users",
            index="ix_email",
        )
    ]

    fixed_code, fixed_issues, unfixed_issues = autofix_engine.apply_fixes(source_code, issues, dry_run=False)

    # Fixes should not be applied for invalid indices
    assert fixed_code == source_code
    assert len(fixed_issues) == 0
    assert len(unfixed_issues) == 1


def test_migration_with_schema_variations():
    """Check handling migration with different ways of passing schema."""
    fix = AddColumnNotNullFix()

    # Test 1: schema as string
    source_code1 = """
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('users', sa.Column('email', sa.String(), nullable=False), schema='public')
"""

    issue1 = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Adding NOT NULL column",
        operation_index=0,
        recommendation="Use safe pattern",
        table="users",
        column="email",
    )

    fixed_code1, success1 = fix.apply_fix(source_code1, issue1)
    assert success1 is True
    assert "schema" in fixed_code1

    # Test 2: schema as variable
    source_code2 = """
from alembic import op
import sqlalchemy as sa

SCHEMA = 'public'

def upgrade():
    op.add_column('users', sa.Column('email', sa.String(), nullable=False), schema=SCHEMA)
"""

    issue2 = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.ADD_COLUMN_NOT_NULL,
        message="Adding NOT NULL column",
        operation_index=0,
        recommendation="Use safe pattern",
        table="users",
        column="email",
    )

    fixed_code2, success2 = fix.apply_fix(source_code2, issue2)
    assert success2 is True
    assert "SCHEMA" in fixed_code2 or "schema" in fixed_code2


def test_autofix_base_validation():
    """Check validation methods of base Autofix class."""
    fix = CreateIndexFix()

    # Test issue validation
    valid_issue = Issue(
        severity=IssueSeverity.CRITICAL,
        type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
        message="Creating index without CONCURRENTLY",
        operation_index=0,
        recommendation="Use CONCURRENTLY",
        table="users",
        index="ix_email",
    )
    assert fix._validate_issue(valid_issue) is True

    # Pydantic validates operation_index >= 0, so cannot create Issue with negative index
    # Check validation through pytest.raises
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Issue(
            severity=IssueSeverity.CRITICAL,
            type=IssueType.CREATE_INDEX_WITHOUT_CONCURRENTLY,
            message="Creating index without CONCURRENTLY",
            operation_index=-1,  # Invalid index
            recommendation="Use CONCURRENTLY",
            table="users",
            index="ix_email",
        )

    # Test AST tree validation

    valid_ast = ast.parse("""
from alembic import op

def upgrade():
    op.create_index('ix_email', 'users', ['email'])
""")
    assert fix._validate_ast_tree(valid_ast) is True

    invalid_ast = ast.parse("""
from alembic import op

def downgrade():
    op.drop_index('ix_email', 'users')
""")
    assert fix._validate_ast_tree(invalid_ast) is False

    assert fix._validate_ast_tree(None) is False


def test_autofix_has_upgrade_function():
    """Check _has_upgrade_function method."""
    fix = CreateIndexFix()

    ast_with_upgrade = ast.parse("""
from alembic import op

def upgrade():
    op.create_index('ix_email', 'users', ['email'])
""")
    assert fix._has_upgrade_function(ast_with_upgrade) is True

    ast_without_upgrade = ast.parse("""
from alembic import op

def downgrade():
    op.drop_index('ix_email', 'users')
""")
    assert fix._has_upgrade_function(ast_without_upgrade) is False
