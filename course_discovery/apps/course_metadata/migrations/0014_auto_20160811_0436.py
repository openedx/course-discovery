import uuid

from django.db import migrations, models


def update_organizations(apps, schema_editor):
    Organization = apps.get_model('course_metadata', 'Organization')
    HistoricalOrganization = apps.get_model('course_metadata', 'HistoricalOrganization')

    # Clear history to avoid null constraint issues
    HistoricalOrganization.objects.all().delete()

    for organization in Organization.objects.all():
        organization.name = organization.name or organization.key
        organization.uuid = uuid.uuid4()
        organization.save()


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0013_auto_20160809_1259'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='organization',
            options={},
        ),
        migrations.RemoveField(
            model_name='historicalorganization',
            name='banner_image',
        ),
        migrations.RemoveField(
            model_name='historicalorganization',
            name='logo_image',
        ),
        migrations.AddField(
            model_name='historicalorganization',
            name='banner_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalorganization',
            name='logo_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalorganization',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='UUID'),
        ),
        migrations.AddField(
            model_name='organization',
            name='banner_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='logo_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='UUID'),
        ),
        migrations.AlterField(
            model_name='historicalorganization',
            name='key',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='organization',
            name='key',
            field=models.CharField(max_length=255),
        ),
        migrations.RemoveField(
            model_name='organization',
            name='banner_image',
        ),
        migrations.RemoveField(
            model_name='organization',
            name='logo_image',
        ),
        migrations.RunPython(update_organizations, reverse_code=migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='organization',
            unique_together={('partner', 'uuid'), ('partner', 'key')},
        ),
        migrations.AlterField(
            model_name='historicalorganization',
            name='name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='organization',
            name='name',
            field=models.CharField(max_length=255),
        ),
    ]
