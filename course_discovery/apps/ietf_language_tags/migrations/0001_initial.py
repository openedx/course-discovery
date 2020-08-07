from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='LanguageTag',
            fields=[
                ('code', models.CharField(primary_key=True, max_length=50, serialize=False)),
                ('name', models.CharField(max_length=255)),
            ],
        ),
    ]
