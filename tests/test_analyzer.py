"""Tests for AST analyzer of Alembic migrations."""

from migsafe.analyzer import analyze_migration


def test_add_column():
    """Test simple add_column operation."""
    src = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "add_column"
    assert ops[0].table == "users"
    assert ops[0].column == "email"
    assert ops[0].nullable is False


def test_add_column_nullable():
    """Test add_column with nullable=True."""
    src = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "add_column"
    assert ops[0].table == "users"
    assert ops[0].column == "email"
    assert ops[0].nullable is True


def test_drop_column():
    """Test drop_column operation."""
    src = """
def upgrade():
    op.drop_column("users", "email")
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "drop_column"
    assert ops[0].table == "users"
    assert ops[0].column == "email"


def test_create_index():
    """Test create_index operation."""
    src = """
def upgrade():
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        postgresql_concurrently=False
    )
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "create_index"
    assert ops[0].index == "ix_users_email"
    assert ops[0].table == "users"
    assert ops[0].concurrently is False


def test_create_index_concurrently():
    """Test create_index with concurrently=True."""
    src = """
def upgrade():
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        postgresql_concurrently=True
    )
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "create_index"
    assert ops[0].index == "ix_users_email"
    assert ops[0].table == "users"
    assert ops[0].concurrently is True


def test_drop_index():
    """Test drop_index operation."""
    src = """
def upgrade():
    op.drop_index("ix_users_email", "users", postgresql_concurrently=False)
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "drop_index"
    assert ops[0].index == "ix_users_email"
    assert ops[0].table == "users"
    assert ops[0].concurrently is False


def test_execute():
    """Test execute operation with SQL string."""
    src = """
def upgrade():
    op.execute("UPDATE users SET email = ''")
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "execute"
    assert ops[0].raw_sql == "UPDATE users SET email = ''"


def test_execute_multiline():
    """Test execute with multiline SQL."""
    src = '''
def upgrade():
    op.execute("""
        UPDATE users
        SET email = ''
        WHERE email IS NULL
    """)
'''
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "execute"
    assert "UPDATE users" in ops[0].raw_sql
    assert "SET email" in ops[0].raw_sql


def test_batch_alter_table():
    """Test batch_alter_table with internal add_column operation."""
    src = """
def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(), nullable=True))
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "add_column"
    assert ops[0].table == "users"
    assert ops[0].column == "email"
    assert ops[0].nullable is True


def test_batch_alter_table_multiple_ops():
    """Test batch_alter_table with multiple operations."""
    src = """
def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(), nullable=True))
        batch_op.drop_column("old_field")
"""
    ops = analyze_migration(src)

    assert len(ops) == 2
    assert ops[0].type == "add_column"
    assert ops[0].table == "users"
    assert ops[0].column == "email"

    assert ops[1].type == "drop_column"
    assert ops[1].table == "users"
    assert ops[1].column == "old_field"


def test_multiple_operations_order():
    """Test preserving operation order."""
    src = """
def upgrade():
    op.add_column("users", sa.Column("email", sa.String(), nullable=False))
    op.create_index("ix_users_email", "users", ["email"])
    op.execute("UPDATE users SET email = 'test'")
"""
    ops = analyze_migration(src)

    assert len(ops) == 3
    assert ops[0].type == "add_column"
    assert ops[1].type == "create_index"
    assert ops[2].type == "execute"


def test_variable_context():
    """Test using variables in context."""
    src = """
def upgrade():
    table_name = "users"
    op.add_column(table_name, sa.Column("email", sa.String(), nullable=False))
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "add_column"
    assert ops[0].table == "users"
    assert ops[0].column == "email"


def test_string_concatenation():
    """Test string concatenation."""
    src = """
def upgrade():
    table = "user" + "s"
    op.add_column(table, sa.Column("email", sa.String(), nullable=False))
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "add_column"
    assert ops[0].table == "users"


def test_no_upgrade_function():
    """Test handling file without upgrade() function."""
    src = """
def downgrade():
    op.drop_column("users", "email")
"""
    ops = analyze_migration(src)

    assert len(ops) == 0


def test_empty_upgrade():
    """Test empty upgrade() function."""
    src = """
def upgrade():
    pass
"""
    ops = analyze_migration(src)

    assert len(ops) == 0


def test_invalid_syntax():
    """Test handling syntactically invalid code."""
    src = """
def upgrade():
    op.add_column("users"  # unclosed parenthesis
"""
    ops = analyze_migration(src)

    # Should return empty list without exception
    assert isinstance(ops, list)
    assert len(ops) == 0


def test_execute_dynamic_sql():
    """Test execute with dynamic SQL (not a string literal)."""
    src = """
def upgrade():
    sql = "SELECT 1"
    op.execute(sql)
"""
    ops = analyze_migration(src)

    assert len(ops) == 1
    assert ops[0].type == "execute"
    # Should extract value from variable
    assert ops[0].raw_sql == "SELECT 1"


def test_complex_migration():
    """Test complex migration with different operations."""
    src = """
def upgrade():
    # Add column
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))

    # Create index
    op.create_index("ix_users_email", "users", ["email"], postgresql_concurrently=False)

    # Update data
    op.execute("UPDATE users SET email = '' WHERE email IS NULL")

    # Batch operations
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("phone", sa.String(), nullable=True))
"""
    ops = analyze_migration(src)

    assert len(ops) == 4

    assert ops[0].type == "add_column"
    assert ops[0].table == "users"
    assert ops[0].column == "email"

    assert ops[1].type == "create_index"
    assert ops[1].index == "ix_users_email"

    assert ops[2].type == "execute"
    assert "UPDATE users" in ops[2].raw_sql

    assert ops[3].type == "add_column"
    assert ops[3].table == "users"
    assert ops[3].column == "phone"
