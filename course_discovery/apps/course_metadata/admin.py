from django.contrib import admin
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect

from simple_history.admin import SimpleHistoryAdmin
from course_discovery.apps.course_metadata.forms import ProgramAdminForm
from course_discovery.apps.course_metadata.models import *  # pylint: disable=wildcard-import


class SeatInline(admin.TabularInline):
    model = Seat
    extra = 1


class PositionInline(admin.TabularInline):
    model = Position
    extra = 0


class FaqsInline(admin.TabularInline):
    model = Program.faq.through
    exclude = ('sort_value',)
    extra = 1
    verbose_name_plural = 'Faqs'


class IndividualEndorsementInline(admin.TabularInline):
    model = Program.individual_endorsements.through
    exclude = ('sort_value',)
    extra = 1
    verbose_name_plural = 'Individual Endorsement'


class CorporateEndorsementsInline(admin.TabularInline):
    model = Program.corporate_endorsements.through
    exclude = ('sort_value',)
    extra = 1
    verbose_name_plural = 'Corporate Endorsement'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'key', 'title',)
    list_filter = ('partner',)
    ordering = ('key', 'title',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'key', 'title',)


@admin.register(CourseRun)
class CourseRunAdmin(admin.ModelAdmin):
    inlines = (SeatInline,)
    list_display = ('uuid', 'key', 'title',)
    list_filter = (
        'course__partner',
        ('language', admin.RelatedOnlyFieldListFilter,),
        'status',
    )
    ordering = ('key',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'key', 'title_override', 'course__title', 'slug',)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    form = ProgramAdminForm
    inlines = [FaqsInline, IndividualEndorsementInline, CorporateEndorsementsInline]
    list_display = ('id', 'uuid', 'title', 'category', 'type', 'partner', 'status',)
    list_filter = ('partner', 'type', 'status',)
    ordering = ('uuid', 'title', 'status')
    readonly_fields = ('uuid', 'custom_course_runs_display', 'excluded_course_runs',)
    search_fields = ('uuid', 'title', 'marketing_slug')

    filter_horizontal = ('job_outlook_items', 'expected_learning_items',)

    # ordering the field display on admin page.
    fields = (
        'title', 'subtitle', 'status', 'type', 'partner', 'banner_image', 'banner_image_url', 'card_image_url',
        'marketing_slug', 'overview', 'video', 'weeks_to_complete', 'min_hours_effort_per_week',
        'max_hours_effort_per_week',
    )
    fields += (
        'courses', 'custom_course_runs_display', 'excluded_course_runs', 'authoring_organizations',
        'credit_backing_organizations'
    )
    fields += filter_horizontal

    def custom_course_runs_display(self, obj):
        return ", ".join([str(run) for run in obj.course_runs])

    custom_course_runs_display.short_description = "Included course runs"

    def response_add(self, request, obj, post_url_continue=None):
        return HttpResponseRedirect(reverse('admin_metadata:update_course_runs', kwargs={'pk': obj.pk}))

    def response_change(self, request, obj):
        if '_continue'in request.POST or '_save' in request.POST:
            return HttpResponseRedirect(reverse('admin_metadata:update_course_runs', kwargs={'pk': obj.pk}))
        else:
            return HttpResponseRedirect(reverse('admin:course_metadata_program_add'))


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


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    inlines = (PositionInline,)
    list_display = ('uuid', 'family_name', 'given_name', 'slug',)
    list_filter = ('partner',)
    ordering = ('family_name', 'given_name', 'uuid',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'family_name', 'given_name', 'slug',)


class NamedModelAdmin(admin.ModelAdmin):
    list_display = ('name',)
    ordering = ('name',)
    search_fields = ('name',)


# Register children of AbstractNamedModel
for model in (LevelType, Prerequisite,):
    admin.site.register(model, NamedModelAdmin)

# Register remaining models using basic ModelAdmin classes
for model in (Image, Video, ExpectedLearningItem, SyllabusItem, PersonSocialNetwork, CourseRunSocialNetwork,
              JobOutlookItem,):
    admin.site.register(model)
