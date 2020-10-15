import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('publisher', '0006_auto_20160902_0726'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='changed_by',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='courserun',
            name='changed_by',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='changed_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, db_constraint=False, null=True, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='changed_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, db_constraint=False, null=True, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalseat',
            name='changed_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, db_constraint=False, null=True, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='historicalstate',
            name='changed_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, db_constraint=False, null=True, blank=True, related_name='+'),
        ),
        migrations.AddField(
            model_name='seat',
            name='changed_by',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='state',
            name='changed_by',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.CASCADE),
        ),
    ]
