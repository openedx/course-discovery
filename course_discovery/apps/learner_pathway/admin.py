"""
Admin definitions for learner_pathway app.
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from course_discovery.apps.learner_pathway import constants
from course_discovery.apps.learner_pathway.models import (
    LearnerPathway, LearnerPathwayCourse, LearnerPathwayProgram, LearnerPathwayStep
)


class LearnerPathwayProgramInline(admin.TabularInline):
    model = LearnerPathwayProgram
    extra = 0
    autocomplete_fields = ('program', )
    readonly_fields = ('estimated_completion_time',)

    def estimated_completion_time(self, pathway_program):
        return pathway_program.get_estimated_time_of_completion() or '-'


class LearnerPathwayCourseInline(admin.TabularInline):
    model = LearnerPathwayCourse
    extra = 0
    autocomplete_fields = ('course', )
    readonly_fields = ('estimated_completion_time',)

    def estimated_completion_time(self, pathway_course):
        return pathway_course.get_estimated_time_of_completion() or '-'


@admin.register(LearnerPathwayStep)
class StepAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'estimated_completion_time', 'courses', 'programs')

    class Media:
        css = {
            "all": ("css/learner_pathway.css",)
        }

    inlines = [
        LearnerPathwayCourseInline,
        LearnerPathwayProgramInline,
    ]

    def estimated_completion_time(self, pathway_step):
        return pathway_step.get_estimated_time_of_completion() or '-'

    def courses(self, pathway_step):
        return pathway_step.get_node_type_count()[constants.NODE_TYPE_COURSE]

    def programs(self, pathway_step):
        return pathway_step.get_node_type_count()[constants.NODE_TYPE_PROGRAM]


class LearnerPathwayStepInline(admin.TabularInline):
    model = LearnerPathwayStep
    extra = 0
    min_num = 1
    readonly_fields = ('UUID', 'estimated_completion_time',)
    exclude = ('min_requirement',)

    def UUID(self, pathway_step):
        step_change_url = reverse('admin:learner_pathway_learnerpathwaystep_change', args=(pathway_step.id,))
        return format_html('<a href="{}">{}</a>', step_change_url, pathway_step.uuid)

    def estimated_completion_time(self, pathway_step):
        return pathway_step.get_estimated_time_of_completion() or '-'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LearnerPathway)
class LearnerPathwayAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'name', 'steps', 'estimated_completion_time')

    inlines = [
        LearnerPathwayStepInline,
    ]

    def steps(self, pathway):
        return pathway.steps.count()

    def estimated_completion_time(self, pathway):
        return pathway.time_of_completion or '-'


@admin.register(LearnerPathwayCourse)
class LearnerPathwayCourseAdmin(admin.ModelAdmin):
    list_display = ('learner_pathway_course_uuid', 'course_key', 'course_title')
    autocomplete_fields = ('course',)
    search_fields = ('uuid', 'course__key', 'course__title')

    class Media:
        css = {
            "all": ("css/learner_pathway.css",)
        }

    def course_key(self, pathway_course):
        return pathway_course.course.key

    def course_title(self, pathway_course):
        return pathway_course.course.title

    def learner_pathway_course_uuid(self, pathway_course):
        return pathway_course.uuid


@admin.register(LearnerPathwayProgram)
class LearnerPathwayProgramAdmin(admin.ModelAdmin):
    list_display = ('learner_pathway_program_uuid', 'program_title', 'program_uuid',)
    autocomplete_fields = ('program',)
    search_fields = ('uuid', 'program__uuid', 'program__title')

    class Media:
        css = {
            "all": ("css/learner_pathway.css",)
        }

    def program_title(self, pathway_program):
        return pathway_program.program.title

    def program_uuid(self, pathway_program):
        return pathway_program.program.uuid

    def learner_pathway_program_uuid(self, pathway_program):
        return pathway_program.uuid
