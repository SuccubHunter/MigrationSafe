"""Django migration example for analysis."""

from django.db import migrations, models


# Example 1: Dangerous migration - adding NOT NULL column
class Migration(migrations.Migration):
    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.AddField(
            model_name="user",
            name="email",
            field=models.EmailField(null=False, default=""),
        ),
    ]


# Example 2: Safe migration - adding nullable column
class SafeMigration(migrations.Migration):
    dependencies = [("myapp", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email",
            field=models.EmailField(null=True),
        ),
    ]


# Example 3: Index creation without CONCURRENTLY
class IndexMigration(migrations.Migration):
    dependencies = [("myapp", "0002_add_email")]

    operations = [
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["email"], name="user_email_idx"),
        ),
    ]


# Example 4: Field removal (DROP COLUMN)
class RemoveFieldMigration(migrations.Migration):
    dependencies = [("myapp", "0003_add_index")]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="old_field",
        ),
    ]
