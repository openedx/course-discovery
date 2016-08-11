from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from course_discovery.apps.course_metadata.models import *  # pylint: disable=wildcard-import


class CourseOrganizationInline(admin.TabularInline):
    model = CourseOrganization
    extra = 1


class SeatInline(admin.TabularInline):
    model = Seat
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    inlines = (CourseOrganizationInline,)
    list_display = ('key', 'title',)
    list_filter = ('partner',)
    ordering = ('key', 'title',)
    search_fields = ('key', 'title',)


@admin.register(CourseRun)
class CourseRunAdmin(admin.ModelAdmin):
    inlines = (SeatInline,)
    list_display = ('key', 'title',)
    ordering = ('key',)
    search_fields = ('key', 'title_override', 'course__title',)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'title', 'marketing_slug', 'type',)
    list_filter = ('partner', 'type',)
    ordering = ('uuid', 'title',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'title', 'marketing_slug')


@admin.register(ProgramType)
class ProgramTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(SeatType)
class SeatTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug',)
    readonly_fields = ('slug',)


@admin.register(Endorsement)
class EndorsementAdmin(admin.ModelAdmin):
    list_display = ('endorser',)


@admin.register(CorporateEndorsement)
class CorporateEndorsementAdmin(admin.ModelAdmin):
    list_display = ('corporation_name',)


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question',)


@admin.register(Organization)
class OrganizationAdmin(SimpleHistoryAdmin):
    list_display = ('uuid', 'key', 'name',)
    list_filter = ('partner',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'name', 'key',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'name', 'slug',)
    list_filter = ('partner',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'name', 'slug',)


class KeyNameAdmin(admin.ModelAdmin):
    list_display = ('key', 'name',)
    ordering = ('key', 'name',)
    search_fields = ('key', 'name',)


class NamedModelAdmin(admin.ModelAdmin):
    list_display = ('name',)
    ordering = ('name',)
    search_fields = ('name',)


# Register key-name models
for model in (Person,):
    admin.site.register(model, KeyNameAdmin)

# Register children of AbstractNamedModel
for model in (LevelType, Prerequisite, Expertise, MajorWork):
    admin.site.register(model, NamedModelAdmin)

# Register remaining models using basic ModelAdmin classes
for model in (Image, Video, ExpectedLearningItem, SyllabusItem, PersonSocialNetwork, CourseRunSocialNetwork,
              JobOutlookItem,):
    admin.site.register(model)
