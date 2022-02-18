# Generated by Django 3.2.8 on 2022-02-18 12:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('learner_pathway', '0006_learnerpathway_partner'),
    ]

    operations = [
        migrations.AddField(
            model_name='learnerpathway',
            name='visible_via_association',
            field=models.BooleanField(default=True, help_text='Course/Program associated pathways also appear in search results'),
        ),
    ]
