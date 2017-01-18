# -*- coding: utf-8 -*-
# Generated by Django 1.9.11 on 2017-01-18 18:26
from __future__ import unicode_literals

from django.db import migrations

from course_discovery.apps.edx_haystack_extensions.models import ElasticsearchBoostConfig

def forward_func(apps, schema_editor):
    """Create or update the ElasticsearchBoostConfig instance."""

    # The imported ElasticsearchBoostConfig class shouldn't be used directly to modify the config, as it might be
    # the wrong version. Instead, we should get the model from the versioned app registry, as described in 
    # https://docs.djangoproject.com/en/1.8/ref/migration-operations/#runpython
    model = apps.get_model("edx_haystack_extensions", "ElasticsearchBoostConfig")

    # Create or update the config using what's currently in production, as of January 20, 2017.
    record = model(pk=ElasticsearchBoostConfig.SINGLETON_INSTANCE_PRIMARY_KEY)
    record.function_score = {
        "boost_mode": "sum",
        "boost": 1.0,
        "score_mode": "sum",
        "functions": [
            {"filter": {"term": {"pacing_type_exact": "self_paced"}}, "weight": 1.0},
            {"filter": {"term": {"type_exact": "micromasters"}}, "weight": 1.0},
            {"linear": {"start": {"origin": "now", "decay": 0.95, "scale": "1d"}}, "weight": 5.0}
        ]
    }
    record.save()

class Migration(migrations.Migration):

    dependencies = [
        ('edx_haystack_extensions', '0001_squashed_0002_auto_20160826_1750'),
    ]

    operations = [
        migrations.RunPython(forward_func, migrations.RunPython.noop)
    ]

