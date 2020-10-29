import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_partner'),
        ('course_metadata', '0008_program_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='partner',
            field=models.ForeignKey(null=True, to='core.Partner', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='partner',
            field=models.ForeignKey(related_name='+', null=True, on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='core.Partner'),
        ),
        migrations.AddField(
            model_name='historicalorganization',
            name='partner',
            field=models.ForeignKey(related_name='+', null=True, on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='core.Partner'),
        ),
        migrations.AddField(
            model_name='organization',
            name='partner',
            field=models.ForeignKey(null=True, to='core.Partner', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='program',
            name='partner',
            field=models.ForeignKey(null=True, to='core.Partner', on_delete=django.db.models.deletion.CASCADE),
        ),
    ]
