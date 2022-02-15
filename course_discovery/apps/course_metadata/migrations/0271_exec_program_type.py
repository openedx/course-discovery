# Generated by Django 3.2.11 on 2022-02-15 10:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0270_alter_courseurlslug_url_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalmode',
            name='certificate_type',
            field=models.CharField(blank=True, choices=[('honor', 'Honor'), ('credit', 'Credit'), ('verified', 'Verified'), ('professional', 'Professional'), ('executive-education', 'Executive Education'), ('executive-program', 'Executive Program')], help_text='Certificate type granted if this mode is eligible for a certificate, or blank if not.', max_length=64),
        ),
        migrations.AlterField(
            model_name='mode',
            name='certificate_type',
            field=models.CharField(blank=True, choices=[('honor', 'Honor'), ('credit', 'Credit'), ('verified', 'Verified'), ('professional', 'Professional'), ('executive-education', 'Executive Education'), ('executive-program', 'Executive Program')], help_text='Certificate type granted if this mode is eligible for a certificate, or blank if not.', max_length=64),
        ),
    ]
