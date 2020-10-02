# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-12-11 17:24


from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0136_drupalpublishuuidconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonAreaOfExpertise',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('value', models.CharField(max_length=255)),
                ('person', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='areas_of_expertise', to='course_metadata.Person')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
