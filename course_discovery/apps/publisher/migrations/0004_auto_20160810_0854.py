import django.db.models.deletion
import django_extensions.db.fields
import django_fsm
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('publisher', '0003_auto_20160801_1757'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalState',
            fields=[
                ('id', models.IntegerField(blank=True, auto_created=True, verbose_name='ID', db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', django_fsm.FSMField(choices=[('draft', 'Draft'), ('needs_review', 'Needs Review'), ('needs_final_approval', 'Needs Final Approval'), ('finalized', 'Finalized'), ('published', 'Published')], default='draft', max_length=50)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical state',
            },
        ),
        migrations.CreateModel(
            name='State',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', django_fsm.FSMField(choices=[('draft', 'Draft'), ('needs_review', 'Needs Review'), ('needs_final_approval', 'Needs Final Approval'), ('finalized', 'Finalized'), ('published', 'Published')], default='draft', max_length=50)),
            ],
            options={
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='courserun',
            name='state',
            field=models.ForeignKey(blank=True, to='publisher.State', null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='state',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='publisher.State', related_name='+', null=True),
        ),
    ]
