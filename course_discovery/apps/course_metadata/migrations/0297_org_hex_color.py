from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0296_geotargetingdataloaderconfiguration'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalorganization',
            name='organization_hex_color',
            field=models.CharField(help_text="""The 6 character-hex-value of the orgnization theme color,
            all related course under same organization will use this color as theme color.
            (e.g. "#ff0000" which equals red) No need to provide the `#`""",
                validators=[django.core.validators.RegexValidator(
                    regex=r'^(([0-9a-fA-F]{2}){3}|([0-9a-fA-F]){3})$',
                    message='Hex color must be 3 or 6 A-F or numeric form',
                    code='invalid_hex_color'
                )],
                blank=True, null=True, max_length=6),
            ),
        migrations.AddField(
            model_name='organization',
            name='organization_hex_color',
            field=models.CharField(help_text="""The 6 character-hex-value of the orgnization theme color,
            all related course under same organization will use this color as theme color.
            (e.g. "#ff0000" which equals red) No need to provide the `#`""", 
                validators=[django.core.validators.RegexValidator(
                    regex=r'^(([0-9a-fA-F]{2}){3}|([0-9a-fA-F]){3})$',
                    message='Hex color must be 3 or 6 A-F or numeric form',
                    code='invalid_hex_color'
                )],
                blank=True,null=True, max_length=6),
        )
    ]
