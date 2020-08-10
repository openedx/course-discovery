from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0207_auto_20191025_1939'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='has_ofac_restrictions',
            field=models.NullBooleanField(verbose_name='Course Has OFAC Restrictions'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='has_ofac_restrictions',
            field=models.NullBooleanField(verbose_name='Course Has OFAC Restrictions'),
        ),
    ]
