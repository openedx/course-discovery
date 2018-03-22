from django.contrib import admin
from .models import JournalBundle, Journal


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'partner',
        'uuid',
    )
    raw_id_fields = (
        'partner',
    )


@admin.register(JournalBundle)
class JournalBundleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'uuid',
        'title'
    )
    raw_id_fields = (
        'partner',
        'journals',
        'courses'
    )
