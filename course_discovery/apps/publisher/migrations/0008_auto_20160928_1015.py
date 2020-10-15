from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0007_auto_20160905_1020'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='verification_deadline',
            field=models.DateTimeField(null=True, verbose_name='Verification deadline', help_text='Last date/time on which verification for this product can be submitted.', blank=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='verification_deadline',
            field=models.DateTimeField(null=True, verbose_name='Verification deadline', help_text='Last date/time on which verification for this product can be submitted.', blank=True),
        ),
    ]
