"""Hash legacy seller passwords while preserving existing password hashes."""

from typing import ClassVar

from django.apps.registry import Apps
from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.operations.base import Operation


def hash_existing_passwords(
    apps: Apps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Convert plaintext passwords using the migration's database connection."""
    shop_owner_model = apps.get_model("accounts", "ShopOwner")
    database_alias = schema_editor.connection.alias
    owners = shop_owner_model.objects.using(database_alias)
    for owner in owners.all().iterator():
        try:
            identify_hasher(owner.password)
        except ValueError:
            owners.filter(pk=owner.pk).update(password=make_password(owner.password))


class Migration(migrations.Migration):
    """Upgrade stored credentials; hashes cannot be converted back to plaintext."""

    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("accounts", "0003_customer_failed_attempts_customer_locked_until_and_more"),
    ]

    operations: ClassVar[list[Operation]] = [
        migrations.RunPython(hash_existing_passwords, migrations.RunPython.noop),
    ]
