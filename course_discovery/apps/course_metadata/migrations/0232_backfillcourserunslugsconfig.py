# -*- coding: utf-8 -*-
# Generated by Django 1.11.27 on 2020-01-13 19:54


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0231_remove_url_fields_from_org'),
    ]

    operations = [
        migrations.CreateModel(
            name='BackfillCourseRunSlugsConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('all', models.BooleanField(default=False, verbose_name='Add redirects from all published course url slugs')),
                ('uuids', models.TextField(blank=True, default='', verbose_name='Course uuids')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
