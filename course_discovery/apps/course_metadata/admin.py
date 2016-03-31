from django.contrib import admin

from course_discovery.apps.course_metadata.models import (
    Seat, Image, Video, LevelType, Subject, Prerequisite, ExpectedLearningItem, Course, CourseRun, Organization, Person,
    CourseOrganization, SyllabusItem
)


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
    ordering = ('key', 'title',)


@admin.register(CourseRun)
class CourseRunAdmin(admin.ModelAdmin):
    inlines = (SeatInline,)
    list_display = ('key', 'title',)
    ordering = ('key',)


class KeyNameAdmin(admin.ModelAdmin):
    list_display = ('key', 'name',)
    ordering = ('key', 'name',)
    search_fields = ('key', 'name',)


class NamedModelAdmin(admin.ModelAdmin):
    list_display = ('name',)
    ordering = ('name',)
    search_fields = ('name',)


# Register key-name models
for model in (Organization, Person,):
    admin.site.register(model, KeyNameAdmin)

# Register children of AbstractNamedModel
for model in (LevelType, Subject, Prerequisite,):
    admin.site.register(model, NamedModelAdmin)

# Register remaining models using basic ModelAdmin classes
for model in (Image, Video, ExpectedLearningItem, SyllabusItem):
    admin.site.register(model)
