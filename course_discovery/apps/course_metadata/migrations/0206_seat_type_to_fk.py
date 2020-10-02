# -*- coding: utf-8 -*-
# Generated by Django 1.11.24 on 2019-10-17 19:50


from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


def create_missing_seat_types(apps, schema_editor):
    Seat = apps.get_model('course_metadata', 'Seat')
    SeatType = apps.get_model('course_metadata', 'SeatType')
    for type_slug in set(Seat.everything.values_list('type', flat=True)):
        SeatType.objects.get_or_create(slug=type_slug, defaults={'name': type_slug.capitalize()})


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0205_create_initial_coursetypes'),
    ]

    operations = [
        migrations.RunPython(create_missing_seat_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='coursetype',
            name='entitlement_types',
            field=models.ManyToManyField(blank=True, to='course_metadata.SeatType'),
        ),
        migrations.AlterField(
            model_name='seattype',
            name='name',
            field=models.CharField(max_length=64),
        ),
        migrations.AlterField(
            model_name='seattype',
            name='slug',
            field=django_extensions.db.fields.AutoSlugField(blank=True, editable=False, populate_from='name', unique=True),
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='type',
            field=models.ForeignKey(blank=True, db_column='type', db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='course_metadata.SeatType', to_field='slug'),
        ),
        migrations.AlterField(
            model_name='seat',
            name='type',
            field=models.ForeignKey(db_column='type', on_delete=django.db.models.deletion.CASCADE, to='course_metadata.SeatType', to_field='slug'),
        ),
    ]
