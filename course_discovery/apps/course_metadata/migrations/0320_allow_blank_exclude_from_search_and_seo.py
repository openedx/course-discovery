# Generated by Django 3.2.17 on 2023-03-20 21:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0319_auto_20230317_1424'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='excluded_from_search',
            field=models.BooleanField(blank=True, default=False, help_text='If checked, this item will not be indexed in Algolia and will not show up in search results.', null=True, verbose_name='Excluded From Search (Algolia Indexing)'),
        ),
        migrations.AlterField(
            model_name='course',
            name='excluded_from_seo',
            field=models.BooleanField(blank=True, default=False, help_text='If checked, the About Page will have a meta tag with noindex value', null=True, verbose_name='Excluded From SEO (noindex tag)'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='excluded_from_search',
            field=models.BooleanField(blank=True, default=False, help_text='If checked, this item will not be indexed in Algolia and will not show up in search results.', null=True, verbose_name='Excluded From Search (Algolia Indexing)'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='excluded_from_seo',
            field=models.BooleanField(blank=True, default=False, help_text='If checked, the About Page will have a meta tag with noindex value', null=True, verbose_name='Excluded From SEO (noindex tag)'),
        ),
        migrations.AlterField(
            model_name='historicalprogram',
            name='excluded_from_search',
            field=models.BooleanField(blank=True, default=False, help_text='If checked, this item will not be indexed in Algolia and will not show up in search results.', null=True, verbose_name='Excluded From Search (Algolia Indexing)'),
        ),
        migrations.AlterField(
            model_name='historicalprogram',
            name='excluded_from_seo',
            field=models.BooleanField(blank=True, default=False, help_text='If checked, the About Page will have a meta tag with noindex value', null=True, verbose_name='Excluded From SEO (noindex tag)'),
        ),
        migrations.AlterField(
            model_name='program',
            name='excluded_from_search',
            field=models.BooleanField(blank=True, default=False, help_text='If checked, this item will not be indexed in Algolia and will not show up in search results.', null=True, verbose_name='Excluded From Search (Algolia Indexing)'),
        ),
        migrations.AlterField(
            model_name='program',
            name='excluded_from_seo',
            field=models.BooleanField(blank=True, default=False, help_text='If checked, the About Page will have a meta tag with noindex value', null=True, verbose_name='Excluded From SEO (noindex tag)'),
        ),
    ]
