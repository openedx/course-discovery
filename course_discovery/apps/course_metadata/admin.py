from adminsortable2.admin import SortableAdminMixin
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin

from course_discovery.apps.course_metadata.exceptions import (
    MarketingSiteAPIClientException, MarketingSitePublisherException
)
from course_discovery.apps.course_metadata.forms import (
    CourseAdminForm, CurriculumCourseMembershipInlineAdminForm, CurriculumCourseRunExclusionInlineAdminForm,
    CurriculumProgramMembershipInlineAdminForm, PathwayAdminForm, ProgramAdminForm
)
from course_discovery.apps.course_metadata.models import *  # pylint: disable=wildcard-import

PUBLICATION_FAILURE_MSG_TPL = _(
    'An error occurred while publishing the {model} to the marketing site. '
    'Please try again. If the error persists, please contact the Engineering Team.'
)


class ProgramEligibilityFilter(admin.SimpleListFilter):
    title = _('eligible for one-click purchase')
    parameter_name = 'eligible_for_one_click_purchase'

    def lookups(self, request, model_admin):  # pragma: no cover
        return (
            (1, _('Yes')),
            (0, _('No'))
        )

    def queryset(self, request, queryset):
        """
        The queryset can be filtered to contain programs that are eligible for
        one click purchase or to exclude them.
        """
        value = self.value()
        if value is None:
            return queryset

        program_ids = set()
        queryset = queryset.prefetch_related('courses__course_runs')
        for program in queryset:
            if program.is_program_eligible_for_one_click_purchase == bool(int(value)):
                program_ids.add(program.id)
        return queryset.filter(pk__in=program_ids)


class SeatInline(admin.TabularInline):
    model = Seat
    extra = 1


class PositionInline(admin.TabularInline):
    model = Position
    extra = 0


class PersonSocialNetworkInline(admin.TabularInline):
    model = PersonSocialNetwork
    extra = 0


class PersonAreaOfExpertiseInline(admin.TabularInline):
    model = PersonAreaOfExpertise
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    form = CourseAdminForm
    list_display = ('uuid', 'key', 'title', 'draft',)
    list_filter = ('partner',)
    ordering = ('key', 'title',)
    readonly_fields = ('uuid', 'enrollment_count', 'recent_enrollment_count',)
    search_fields = ('uuid', 'key', 'title',)
    raw_id_fields = ('draft_version',)


@admin.register(CourseEditor)
class CourseEditorAdmin(admin.ModelAdmin):
    list_display = ('user', 'course',)
    search_fields = ('user__username', 'course__title', 'course__key',)
    raw_id_fields = ('user', 'course',)


@admin.register(CourseEntitlement)
class CourseEntitlementAdmin(admin.ModelAdmin):
    list_display = ['course', 'get_course_number', 'mode', 'draft']

    def get_course_number(self, obj):
        return obj.course.number

    get_course_number.short_description = 'Course number'

    raw_id_fields = ('course', 'draft_version',)
    search_fields = ['course__title', 'course__number']


@admin.register(CourseRun)
class CourseRunAdmin(admin.ModelAdmin):
    inlines = (SeatInline,)
    list_display = ('uuid', 'key', 'external_key', 'title', 'status', 'draft',)
    list_filter = (
        'course__partner',
        'hidden',
        ('language', admin.RelatedOnlyFieldListFilter,),
        'status',
        'license',
    )
    ordering = ('key',)
    raw_id_fields = ('course', 'draft_version',)
    readonly_fields = ('uuid', 'enrollment_count', 'recent_enrollment_count',)
    search_fields = ('uuid', 'key', 'title_override', 'course__title', 'slug', 'external_key')
    save_error = False

    def response_change(self, request, obj):
        if self.save_error:
            return self.response_post_save_change(request, obj)

        return super().response_change(request, obj)

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except (MarketingSitePublisherException, MarketingSiteAPIClientException):
            self.save_error = True

            logger.exception('An error occurred while publishing course run [%s] to the marketing site.', obj.key)

            msg = PUBLICATION_FAILURE_MSG_TPL.format(model='course run')  # pylint: disable=no-member
            messages.add_message(request, messages.ERROR, msg)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    form = ProgramAdminForm
    list_display = ('id', 'uuid', 'title', 'type', 'partner', 'status', 'hidden')
    list_filter = ('partner', 'type', 'status', ProgramEligibilityFilter, 'hidden',)
    ordering = ('uuid', 'title', 'status')
    readonly_fields = ('uuid', 'custom_course_runs_display', 'excluded_course_runs', 'enrollment_count',
                       'recent_enrollment_count',)
    raw_id_fields = ('video',)
    search_fields = ('uuid', 'title', 'marketing_slug')

    # ordering the field display on admin page.
    fields = (
        'uuid', 'title', 'subtitle', 'status', 'type', 'partner', 'banner_image', 'banner_image_url', 'card_image_url',
        'marketing_slug', 'overview', 'credit_redemption_overview', 'video', 'total_hours_of_effort',
        'weeks_to_complete', 'min_hours_effort_per_week', 'max_hours_effort_per_week', 'courses',
        'order_courses_by_start_date', 'custom_course_runs_display', 'excluded_course_runs', 'authoring_organizations',
        'credit_backing_organizations', 'one_click_purchase_enabled', 'hidden', 'corporate_endorsements', 'faq',
        'individual_endorsements', 'job_outlook_items', 'expected_learning_items', 'instructor_ordering',
        'enrollment_count', 'recent_enrollment_count',
    )

    save_error = False

    def custom_course_runs_display(self, obj):
        return mark_safe('<br>'.join([str(run) for run in obj.course_runs]))

    custom_course_runs_display.short_description = _('Included course runs')

    def _redirect_course_run_update_page(self, obj):
        """ Returns a response redirect to a page where the user can update the
        course runs for the program being edited.

        Returns:
            HttpResponseRedirect
        """
        return HttpResponseRedirect(reverse('admin_metadata:update_course_runs', kwargs={'pk': obj.pk}))

    def response_add(self, request, obj, post_url_continue=None):
        if self.save_error:
            return self.response_post_save_add(request, obj)
        else:
            return self._redirect_course_run_update_page(obj)

    def response_change(self, request, obj):
        if self.save_error:
            return self.response_post_save_change(request, obj)
        else:
            if any(status in request.POST for status in ['_continue', '_save']):
                return self._redirect_course_run_update_page(obj)
            else:
                return HttpResponseRedirect(reverse('admin:course_metadata_program_add'))

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except (MarketingSitePublisherException, MarketingSiteAPIClientException):
            self.save_error = True

            logger.exception('An error occurred while publishing program [%s] to the marketing site.', obj.uuid)

            msg = PUBLICATION_FAILURE_MSG_TPL.format(model='program')  # pylint: disable=no-member
            messages.add_message(request, messages.ERROR, msg)

    class Media:
        js = ('bower_components/jquery-ui/ui/minified/jquery-ui.min.js',
              'js/sortable_select.js')


@admin.register(Pathway)
class PathwayAdmin(admin.ModelAdmin):
    form = PathwayAdminForm
    readonly_fields = ('uuid',)
    list_display = ('name', 'uuid', 'org_name', 'partner', 'email', 'destination_url', 'pathway_type',)
    search_fields = ('uuid', 'name', 'email', 'destination_url', 'pathway_type',)


@admin.register(ProgramType)
class ProgramTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug',)


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('course_run', 'type', 'draft')
    raw_id_fields = ('draft_version',)


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


@admin.register(Ranking)
class RankingAdmin(admin.ModelAdmin):
    list_display = ('rank', 'description', 'source')


@admin.register(AdditionalPromoArea)
class AdditionalPromoAreaAdmin(admin.ModelAdmin):
    list_display = ('title', 'description', 'courses')
    search_fields = ('description',)

    def courses(self, obj):
        return ', '.join([
            course.key for course in obj.extra_description.all()
        ])


class OrganizationUserRoleInline(admin.TabularInline):
    # course-meta-data models are importing in publisher app. So just for safe side
    # to avoid any circular issue importing the publisher model here.
    from course_discovery.apps.publisher.models import OrganizationUserRole
    model = OrganizationUserRole
    extra = 3
    raw_id_fields = ('user',)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'key', 'name',)
    inlines = [OrganizationUserRoleInline, ]
    list_filter = ('partner',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'name', 'key',)


@admin.register(Subject)
class SubjectAdmin(TranslatableAdmin):
    list_display = ('uuid', 'name', 'slug',)
    list_filter = ('partner',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'name', 'slug',)


@admin.register(Topic)
class TopicAdmin(TranslatableAdmin):
    list_display = ('uuid', 'name', 'slug',)
    list_filter = ('partner',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'name', 'slug',)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    inlines = (PositionInline, PersonSocialNetworkInline, PersonAreaOfExpertiseInline)
    list_display = ('uuid', 'salutation', 'family_name', 'given_name', 'bio_language', 'slug',)
    list_filter = ('partner', 'bio_language')
    ordering = ('salutation', 'family_name', 'given_name', 'uuid',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'salutation', 'family_name', 'given_name', 'slug',)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('person', 'organization', 'organization_override',)
    search_fields = ('person__given_name',)

    def has_delete_permission(self, request, obj=None):
        """Don't allow deletes"""
        return False

    def get_actions(self, request):
        actions = super(PositionAdmin, self).get_actions(request)
        actions.pop('delete_selected', None)
        return actions


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('src', 'description',)
    search_fields = ('src', 'description',)


@admin.register(Prerequisite)
class PrerequisiteAdmin(admin.ModelAdmin):
    list_display = ('name',)
    ordering = ('name',)
    search_fields = ('name',)


@admin.register(LevelType)
class LevelTypeAdmin(SortableAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'order')
    search_fields = ('name',)


class CurriculumProgramMembershipInline(admin.TabularInline):
    model = CurriculumProgramMembership
    form = CurriculumProgramMembershipInlineAdminForm
    fields = ('program', 'is_active')
    extra = 0


class CurriculumCourseMembershipInline(admin.StackedInline):
    model = CurriculumCourseMembership
    form = CurriculumCourseMembershipInlineAdminForm
    readonly_fields = ("custom_course_runs_display", "course_run_exclusions", "get_edit_link",)

    def custom_course_runs_display(self, obj):
        return mark_safe('<br>'.join([str(run) for run in obj.course_runs]))

    custom_course_runs_display.short_description = _('Included course runs')

    def get_edit_link(self, obj=None):
        if obj and obj.pk:
            url = reverse('admin:{}_{}_change'.format(obj._meta.app_label, obj._meta.model_name), args=[obj.pk])
            return """<a href="{url}">{text}</a>""".format(
                url=url,
                text=_("Edit course run exclusions"),
            )
        return _("(save and continue editing to create a link)")
    get_edit_link.short_description = _("Edit link")
    get_edit_link.allow_tags = True

    extra = 0


class CurriculumCourseRunExclusionInline(admin.TabularInline):
    model = CurriculumCourseRunExclusion
    form = CurriculumCourseRunExclusionInlineAdminForm
    extra = 0


@admin.register(CurriculumProgramMembership)
class CurriculumProgramMembershipAdmin(admin.ModelAdmin):
    list_display = ('curriculum', 'program')


@admin.register(CurriculumCourseMembership)
class CurriculumCourseMembershipAdmin(admin.ModelAdmin):
    list_display = ('curriculum', 'course')
    inlines = (CurriculumCourseRunExclusionInline,)


@admin.register(CurriculumCourseRunExclusion)
class CurriculumCourseRunExclusionAdmin(admin.ModelAdmin):
    list_display = ("course_membership", "course_run")


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'program', 'name', 'is_active')
    inlines = (CurriculumProgramMembershipInline, CurriculumCourseMembershipInline)


class CurriculumAdminInline(admin.StackedInline):
    model = Curriculum
    extra = 1


class IconTextPairingInline(admin.StackedInline):
    model = IconTextPairing
    extra = 3
    verbose_name = "Quick Fact"
    verbose_name_plural = "Quick Facts"


@admin.register(DegreeDeadline)
class DegreeDeadlineAdmin(admin.ModelAdmin):
    list_display = ('degree', 'semester', 'name', 'date', 'time')


@admin.register(DegreeCost)
class DegreeCostAdmin(admin.ModelAdmin):
    list_display = ('degree', 'description', 'amount')


class DegreeDeadlineInlineAdmin(admin.StackedInline):
    model = DegreeDeadline
    extra = 1


class DegreeCostInlineAdmin(admin.StackedInline):
    model = DegreeCost
    extra = 1


@admin.register(Degree)
class DegreeAdmin(admin.ModelAdmin):
    """
    This is an inheritance model from Program

    """
    list_display = ('title', 'partner', 'status', 'hidden')
    ordering = ('title', 'status')
    readonly_fields = ('uuid', )
    search_fields = ('title', 'partner', 'marketing_slug')
    inlines = (CurriculumAdminInline, DegreeDeadlineInlineAdmin, DegreeCostInlineAdmin, IconTextPairingInline)
    # ordering the field display on admin page.
    fields = (
        'type', 'uuid', 'status', 'hidden', 'partner', 'authoring_organizations', 'marketing_slug', 'card_image_url',
        'search_card_ranking', 'search_card_cost', 'search_card_courses', 'overall_ranking', 'campus_image', 'title',
        'subtitle', 'title_background_image', 'banner_border_color', 'apply_url', 'overview', 'rankings',
        'application_requirements', 'prerequisite_coursework', 'lead_capture_image', 'lead_capture_list_name',
        'hubspot_lead_capture_form_id', 'micromasters_long_title', 'micromasters_long_description', 'micromasters_url',
        'micromasters_background_image', 'micromasters_org_name_override', 'faq', 'costs_fine_print',
        'deadlines_fine_print',
    )


# Register remaining models using basic ModelAdmin classes
for model in (Image, ExpectedLearningItem, SyllabusItem, PersonSocialNetwork, JobOutlookItem, DataLoaderConfig,
              DeletePersonDupsConfig, DrupalPublishUuidConfig, MigratePublisherToCourseMetadataConfig,
              ProfileImageDownloadConfig, PersonAreaOfExpertise, TagCourseUuidsConfig):
    admin.site.register(model)
