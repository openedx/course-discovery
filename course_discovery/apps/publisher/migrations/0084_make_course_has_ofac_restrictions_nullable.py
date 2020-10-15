from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0083_publisher_course_unique_url_slug'),
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
