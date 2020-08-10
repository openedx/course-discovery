import djchoices.choices
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0023_auto_20160826_1912'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserun',
            name='status',
            field=models.CharField(db_index=True, validators=[djchoices.choices.ChoicesValidator({'unpublished': 'Unpublished', 'published': 'Published'})], choices=[('published', 'Published'), ('unpublished', 'Unpublished')], max_length=255, default='unpublished'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='status',
            field=models.CharField(db_index=True, validators=[djchoices.choices.ChoicesValidator({'unpublished': 'Unpublished', 'published': 'Published'})], choices=[('published', 'Published'), ('unpublished', 'Unpublished')], max_length=255, default='unpublished'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='courserun',
            name='pacing_type',
            field=models.CharField(choices=[('instructor_paced', 'Instructor-paced'), ('self_paced', 'Self-paced')], null=True, db_index=True, validators=[djchoices.choices.ChoicesValidator({'instructor_paced': 'Instructor-paced', 'self_paced': 'Self-paced'})], blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='pacing_type',
            field=models.CharField(choices=[('instructor_paced', 'Instructor-paced'), ('self_paced', 'Self-paced')], null=True, db_index=True, validators=[djchoices.choices.ChoicesValidator({'instructor_paced': 'Instructor-paced', 'self_paced': 'Self-paced'})], blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='program',
            name='status',
            field=models.CharField(db_index=True, help_text='The lifecycle status of this Program.', choices=[('unpublished', 'Unpublished'), ('active', 'Active'), ('retired', 'Retired'), ('deleted', 'Deleted')], max_length=24, validators=[djchoices.choices.ChoicesValidator({'unpublished': 'Unpublished', 'active': 'Active', 'deleted': 'Deleted', 'retired': 'Retired'})]),
        ),
    ]
