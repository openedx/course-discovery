# Generated by Django 3.2.13 on 2022-06-07 21:39

from django.db import migrations, models
import django_extensions.db.fields
import sortedm2m.fields
import uuid


class Migration(migrations.Migration):

    replaces = [('course_metadata', '0282_producttopic'), ('course_metadata', '0283_alter_producttopic_parent_topics'), ('course_metadata', '0284_auto_20220607_2106')]

    dependencies = [
        ('course_metadata', '0281_program_override_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductTopic',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='UUID')),
                ('name', models.CharField(max_length=255)),
                ('parent_topics', sortedm2m.fields.SortedManyToManyField(blank=True, help_text=None, to='course_metadata.ProductTopic')),
                ('subjects', sortedm2m.fields.SortedManyToManyField(help_text=None, to='course_metadata.Subject')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='course',
            name='product_topics',
            field=sortedm2m.fields.SortedManyToManyField(blank=True, help_text=None, to='course_metadata.ProductTopic'),
        ),
    ]