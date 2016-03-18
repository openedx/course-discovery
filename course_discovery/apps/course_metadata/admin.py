from django.contrib import admin

from course_discovery.apps.course_metadata.models import (
    Seat, Image, Video, LevelType, PacingType, Subject, Prerequisite, ExpectedLearningItem, Course, CourseRun,
    Organization, Person, CourseOrganization, SyllabusItem)


class CourseOrganizationInline(admin.TabularInline):
    model = CourseOrganization
    extra = 1


class SeatInline(admin.TabularInline):
    model = Seat
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    inlines = (CourseOrganizationInline,)


@admin.register(CourseRun)
class CourseRunAdmin(admin.ModelAdmin):
    inlines = (SeatInline,)


# Register all models using basic ModelAdmin classes
models = (
    Image, Video, LevelType, PacingType, Subject, Prerequisite, ExpectedLearningItem, Organization, Person, SyllabusItem
)

for model in models:
    admin.site.register(model)
