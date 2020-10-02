# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-06-03 16:12


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0179_historicalcourseentitlement_historicalseat'),
    ]

    operations = [
        migrations.AlterField(
            model_name='seat',
            name='currency',
            field=models.ForeignKey(default='USD', on_delete=django.db.models.deletion.CASCADE, to='core.Currency'),
        ),
    ]
