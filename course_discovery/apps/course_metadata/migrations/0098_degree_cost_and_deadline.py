import django.db.models.deletion
import django_extensions.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0097_degree_lead_capture_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='DegreeCost',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('description', models.CharField(help_text='Describes what the cost is for (e.g. Tuition)', max_length=255)),
                ('amount', models.CharField(help_text='String-based field stating how much the cost is (e.g. $1000).', max_length=255)),
            ],
            options={
                'ordering': ['created'],
            },
        ),
        migrations.CreateModel(
            name='DegreeDeadline',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('semester', models.CharField(help_text='Deadline applies for this semester (e.g. Spring 2019', max_length=255)),
                ('name', models.CharField(help_text='Describes the deadline (e.g. Early Admission Deadline)', max_length=255)),
                ('date', models.CharField(help_text='The date after which the deadline expires (e.g. January 1, 2019)', max_length=255)),
                ('time', models.CharField(help_text='The time after which the deadline expires (e.g. 11:59 PM EST).', max_length=255)),
            ],
            options={
                'ordering': ['created'],
            },
        ),
        migrations.RemoveField(
            model_name='degree',
            name='application_deadline',
        ),
        migrations.AddField(
            model_name='degree',
            name='application_requirements',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='degree',
            name='prerequisite_coursework',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='degreedeadline',
            name='degree',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='deadlines', to='course_metadata.Degree'),
        ),
        migrations.AddField(
            model_name='degreecost',
            name='degree',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='costs', to='course_metadata.Degree'),
        ),
    ]
