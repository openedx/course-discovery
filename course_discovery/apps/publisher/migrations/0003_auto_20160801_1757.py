import django.db.models.deletion
import sortedm2m.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0002_auto_20160729_1027'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='organizations',
            field=models.ManyToManyField(blank=True, related_name='publisher_courses', to='course_metadata.Organization', verbose_name='Partner Name'),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='course',
            field=models.ForeignKey(related_name='publisher_course_runs', to='publisher.Course', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='staff',
            field=sortedm2m.fields.SortedManyToManyField(blank=True, related_name='publisher_course_runs_staffed', help_text=None, to='course_metadata.Person'),
        ),
    ]
