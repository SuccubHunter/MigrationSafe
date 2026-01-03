"""Tests for DjangoOperationConverter."""

import ast

from migsafe.analyzers.django_converter import DjangoOperationConverter


def test_converter_createmodel_to_add_table():
    """Convert CreateModel to add_table."""
    code = "migrations.CreateModel(name='User', fields=[])"
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_createmodel(call, context={})

    assert result is not None
    assert result.type == "add_table"
    assert result.table == "user"


def test_converter_addfield_to_add_column():
    """Convert AddField to add_column."""
    code = """
migrations.AddField(
    model_name='user',
    name='email',
    field=models.CharField(max_length=255, null=False)
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_addfield(call, context={})

    assert result is not None
    assert result.type == "add_column"
    assert result.table == "user"
    assert result.column == "email"
    assert result.nullable is False


def test_converter_addfield_nullable():
    """Convert AddField with nullable=True."""
    code = """
migrations.AddField(
    model_name='user',
    name='bio',
    field=models.TextField(null=True)
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_addfield(call, context={})

    assert result is not None
    assert result.type == "add_column"
    assert result.nullable is True


def test_converter_alterfield_to_alter_column():
    """Convert AlterField to alter_column."""
    code = """
migrations.AlterField(
    model_name='user',
    name='email',
    field=models.EmailField(max_length=255, null=False)
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_alterfield(call, context={})

    assert result is not None
    assert result.type == "alter_column"
    assert result.table == "user"
    assert result.column == "email"
    assert result.nullable is False


def test_converter_deletefield_to_drop_column():
    """Convert DeleteField to drop_column."""
    code = """
migrations.DeleteField(
    model_name='user',
    name='old_field'
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_deletefield(call, context={})

    assert result is not None
    assert result.type == "drop_column"
    assert result.table == "user"
    assert result.column == "old_field"


def test_converter_createindex_to_create_index():
    """Convert CreateIndex to create_index."""
    code = """
migrations.CreateIndex(
    model_name='user',
    index=models.Index(fields=['email'], name='user_email_idx')
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_createindex(call, context={})

    assert result is not None
    assert result.type == "create_index"
    assert result.table == "user"
    assert result.index == "user_email_idx"


def test_converter_runsql_handling():
    """Handle RunSQL operations."""
    code = """
migrations.RunSQL(
    sql="CREATE INDEX CONCURRENTLY idx_email ON users(email)"
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_runsql(call, context={})

    assert result is not None
    assert result.type == "execute"
    assert "CREATE INDEX" in result.raw_sql


def test_converter_runpython_handling():
    """Handle RunPython operations."""
    code = """
migrations.RunPython(
    code=forward_func,
    reverse_code=reverse_func
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_runpython(call, context={})

    assert result is not None
    assert result.type == "execute"
    assert result.raw_sql == "<runpython>"


def test_converter_handles_unknown_operation():
    """Handle unknown operations."""
    code = "migrations.UnknownOperation()"
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert(call, context={})

    # Unknown operations return execute operation with warning
    assert result is not None
    assert result.type == "execute"
    assert "unknown_django_operation" in result.raw_sql


def test_converter_convert_method():
    """Check main convert method."""
    code = "migrations.AddField(model_name='user', name='email', field=models.CharField())"
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert(call, context={})

    assert result is not None
    assert result.type == "add_column"
    assert result.table == "user"
    assert result.column == "email"


def test_converter_deletemodel_to_drop_table():
    """Convert DeleteModel to drop_table."""
    code = "migrations.DeleteModel(name='User')"
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_deletemodel(call, context={})

    assert result is not None
    assert result.type == "drop_table"
    assert result.table == "user"


def test_converter_renamemodel_to_alter_column():
    """Convert RenameModel to alter_column (approximation)."""
    code = """
migrations.RenameModel(
    old_name='OldUser',
    new_name='NewUser'
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_renamemodel(call, context={})

    assert result is not None
    assert result.type == "alter_column"  # Temporary solution
    assert result.table == "olduser"


def test_converter_renamefield_to_alter_column():
    """Convert RenameField to alter_column (approximation)."""
    code = """
migrations.RenameField(
    model_name='user',
    old_name='old_email',
    new_name='email'
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_renamefield(call, context={})

    assert result is not None
    assert result.type == "alter_column"  # Temporary solution
    assert result.table == "user"
    assert result.column == "old_email"


def test_converter_altermodeltable_to_alter_column():
    """Convert AlterModelTable to alter_column (approximation)."""
    code = """
migrations.AlterModelTable(
    name='User',
    table='custom_users_table'
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_altermodeltable(call, context={})

    assert result is not None
    assert result.type == "alter_column"  # Temporary solution
    assert result.table == "user"


def test_converter_createindex_with_fields():
    """Convert CreateIndex with index fields extraction."""
    code = """
migrations.CreateIndex(
    model_name='user',
    index=models.Index(fields=['email', 'created_at'], name='user_email_created_idx')
)
"""
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_createindex(call, context={})

    assert result is not None
    assert result.type == "create_index"
    assert result.table == "user"
    assert result.index == "user_email_created_idx"
    assert result.index_fields == "email, created_at"


def test_converter_with_variable_context():
    """Test conversion with variables in context."""
    # Simulate migration with variables
    code = """
model_name = 'User'
field_name = 'email'
migrations.AddField(
    model_name=model_name,
    name=field_name,
    field=models.CharField(max_length=255)
)
"""
    tree = ast.parse(code)
    # Extract variable context
    context = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                    context[target.id] = node.value.value

    # Extract AddField call
    call = None
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            break

    converter = DjangoOperationConverter()
    result = converter.convert_addfield(call, context=context)

    assert result is not None
    assert result.type == "add_column"
    assert result.table == "user"  # lowercase
    assert result.column == "email"


def test_converter_handles_missing_required_args():
    """Test handling missing required arguments."""
    # AddField without model_name
    code = "migrations.AddField(name='email', field=models.CharField())"
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_addfield(call, context={})

    # Should return None if required arguments are missing
    assert result is None


def test_converter_handles_complex_expressions():
    """Test handling complex expressions (AST analysis limitation)."""
    # F-string in model name (not supported)
    code = """
prefix = 'My'
migrations.CreateModel(name=f'{prefix}User', fields=[])
"""
    tree = ast.parse(code)
    call = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "CreateModel":
            call = node
            break

    if call:
        converter = DjangoOperationConverter()
        result = converter.convert_createmodel(call, context={})

        # Complex expressions are not supported, result may be None
        # or with incomplete data
        # This is an expected limitation of AST analysis
        assert result is None or result.table is None
    else:
        # If call not found, that's also fine for this test
        assert True


def test_converter_handles_positional_args():
    """Test handling positional arguments."""
    # CreateModel with positional arguments
    code = "migrations.CreateModel('User', [])"
    tree = ast.parse(code)
    call = tree.body[0].value

    converter = DjangoOperationConverter()
    result = converter.convert_createmodel(call, context={})

    assert result is not None
    assert result.type == "add_table"
    assert result.table == "user"
