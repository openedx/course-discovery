from django.db import migrations, models
from sortedm2m import fields, operations


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0028_courserun_hidden'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='order_courses_by_start_date',
            field=models.BooleanField(default=True, help_text='If this box is not checked, courses will be ordered as in the courses select box above.', verbose_name='Order Courses By Start Date'),
        ),
        operations.AlterSortedManyToManyField(
            model_name='program',
            name='courses',
            field=fields.SortedManyToManyField(help_text=None, related_name='programs', to='course_metadata.Course'),
        ),
    ]
