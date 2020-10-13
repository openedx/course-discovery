from django.db import migrations


# NOTE (CCB): This migration is intentionally blank to avoid ghost migrations in production.
# The category field has been removed from the Program model. When we do squash migrations, this migration
# should be removed.


class Migration(migrations.Migration):
    dependencies = [
        ('edx_catalog_extensions', '0001_create_program_types'),
    ]

    operations = [
    ]
