from django.contrib import admin
from solo.admin import SingletonModelAdmin
from course_discovery.apps.edx_haystack_extensions.models import ElasticsearchBoostConfig


admin.site.register(ElasticsearchBoostConfig, SingletonModelAdmin)
