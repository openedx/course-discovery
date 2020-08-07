import django.db.models.deletion
import django_extensions.db.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('sites', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Comments',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('object_pk', models.TextField(verbose_name='object ID')),
                ('user_name', models.CharField(verbose_name="user's name", blank=True, max_length=50)),
                ('user_email', models.EmailField(verbose_name="user's email address", blank=True, max_length=254)),
                ('user_url', models.URLField(verbose_name="user's URL", blank=True)),
                ('comment', models.TextField(verbose_name='comment', max_length=3000)),
                ('submit_date', models.DateTimeField(verbose_name='date/time submitted', default=None, db_index=True)),
                ('ip_address', models.GenericIPAddressField(verbose_name='IP address', blank=True, unpack_ipv4=True, null=True)),
                ('is_public', models.BooleanField(help_text='Uncheck this box to make the comment effectively disappear from the site.', verbose_name='is public', default=True)),
                ('is_removed', models.BooleanField(help_text='Check this box if the comment is inappropriate. A "This comment has been removed" message will be displayed instead.', verbose_name='is removed', default=False)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('content_type', models.ForeignKey(verbose_name='content type', to='contenttypes.ContentType', related_name='content_type_set_for_comments', on_delete=django.db.models.deletion.CASCADE)),
                ('site', models.ForeignKey(to='sites.Site', on_delete=django.db.models.deletion.CASCADE)),
                ('user', models.ForeignKey(verbose_name='user', blank=True, to=settings.AUTH_USER_MODEL, null=True, related_name='comments_comments', on_delete=django.db.models.deletion.SET_NULL)),
            ],
            options={
                'verbose_name': 'comment',
                'permissions': [('can_moderate', 'Can moderate comments')],
                'verbose_name_plural': 'comments',
                'ordering': ('submit_date',),
                'abstract': False,
            },
        ),
    ]
