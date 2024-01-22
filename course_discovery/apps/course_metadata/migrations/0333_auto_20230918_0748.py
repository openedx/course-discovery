# Generated by Django 3.2.20 on 2023-09-18 07:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0332_alter_migratecourseslugconfiguration_course_type'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='additionalmetadata',
            options={},
        ),
        migrations.AlterModelOptions(
            name='productmeta',
            options={},
        ),
        migrations.AlterModelOptions(
            name='productvalue',
            options={},
        ),
        migrations.AlterModelOptions(
            name='taxiform',
            options={},
        ),
        migrations.AlterField(
            model_name='courserun',
            name='has_ofac_restrictions',
            field=models.BooleanField(blank=True, choices=[('', '--'), (True, 'Blocked'), (False, 'Unrestricted')], default=None, null=True, verbose_name='Add OFAC restriction text to the FAQ section of the Marketing site'),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='has_ofac_restrictions',
            field=models.BooleanField(blank=True, choices=[('', '--'), (True, 'Blocked'), (False, 'Unrestricted')], default=None, null=True, verbose_name='Add OFAC restriction text to the FAQ section of the Marketing site'),
        ),
        migrations.AlterField(
            model_name='historicalprogram',
            name='has_ofac_restrictions',
            field=models.BooleanField(blank=True, choices=[('', '--'), (True, 'Blocked'), (False, 'Unrestricted')], default=None, null=True, verbose_name='Add OFAC restriction text to the FAQ section of the Marketing site'),
        ),
        migrations.AlterField(
            model_name='program',
            name='has_ofac_restrictions',
            field=models.BooleanField(blank=True, choices=[('', '--'), (True, 'Blocked'), (False, 'Unrestricted')], default=None, null=True, verbose_name='Add OFAC restriction text to the FAQ section of the Marketing site'),
        ),
    ]
