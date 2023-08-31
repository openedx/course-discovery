from adminsortable2.admin import SortableAdminMixin
from dal import autocomplete
from django.contrib import admin, messages
from django.contrib.admin.utils import model_ngettext
from django.db.utils import IntegrityError
from django.forms import CheckboxSelectMultiple, ModelForm
from django.http import HttpResponseRedirect
from django.urls import re_path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django_object_actions import DjangoObjectActions
from parler.admin import TranslatableAdmin
from simple_history.admin import SimpleHistoryAdmin
from waffle import get_waffle_flag_model  # lint-amnesty, pylint: disable=invalid-django-waffle-import

from course_discovery.apps.course_metadata.algolia_forms import SearchDefaultResultsConfigurationForm
from course_discovery.apps.course_metadata.algolia_models import SearchDefaultResultsConfiguration
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.constants import (
    COURSE_SKILLS_URL_NAME, REFRESH_COURSE_SKILLS_URL_NAME, REFRESH_PROGRAM_SKILLS_URL_NAME
)
from course_discovery.apps.course_metadata.exceptions import (
    MarketingSiteAPIClientException, MarketingSitePublisherException
)
from course_discovery.apps.course_metadata.forms import (
    CourseAdminForm, CourseRunAdminForm, PathwayAdminForm, ProgramAdminForm
)
from course_discovery.apps.course_metadata.models import *  # pylint: disable=wildcard-import
from course_discovery.apps.course_metadata.views import (
    CourseSkillsView, RefreshCourseSkillsView, RefreshProgramSkillsView
)
from course_discovery.apps.learner_pathway.api.urls import app_name as learner_pathway_app_name

PUBLICATION_FAILURE_MSG_TPL = _(
    'An error occurred while publishing the {model} to the marketing site. '
    'Please try again. If the error persists, please contact the Engineering Team.'
)


class CurriculumCourseMembershipForm(ModelForm):
    """
    A custom CurriculumCourseMembershipForm to override the widget used by the course ModelChoiceField.
    This allows us to leverage the view at the URL admin_metadata:course-autocomplete, which filters out draft
    courses.
    """
    class Meta:
        model = CurriculumCourseMembership
        fields = ['curriculum', 'course', 'course_run_exclusions', 'is_active']
        widgets = {
            'course': autocomplete.ModelSelect2(url='admin_metadata:course-autocomplete')
        }


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
    readonly_fields = ('_upgrade_deadline', )
    raw_id_fields = ('draft_version', 'currency')


class PositionInline(admin.TabularInline):
    model = Position
    extra = 0


class SourceInline(admin.TabularInline):
    model = Source
    extra = 0


class PersonSocialNetworkInline(admin.TabularInline):
    model = PersonSocialNetwork
    extra = 0


class PersonAreaOfExpertiseInline(admin.TabularInline):
    model = PersonAreaOfExpertise
    extra = 0


class AdditionalMetadataInline(admin.TabularInline):
    model = AdditionalMetadata
    extra = 0


@admin.register(GeoLocation)
class GeoLocationAdmin(admin.ModelAdmin):
    """Admin for GeoLocation model."""


@admin.register(ProductValue)
class ProductValueAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'per_click_usa', 'per_click_international', 'per_lead_usa', 'per_lead_international'
    ]


@admin.register(Course)
class CourseAdmin(DjangoObjectActions, SimpleHistoryAdmin):
    form = CourseAdminForm
    list_display = ('uuid', 'key', 'key_for_reruns', 'title', 'draft',)
    list_filter = ('partner', 'product_source')
    ordering = ('key', 'title',)
    readonly_fields = ['enrollment_count', 'recent_enrollment_count', 'active_url_slug', 'key', 'number']
    search_fields = ('uuid', 'key', 'key_for_reruns', 'title',)
    raw_id_fields = ('canonical_course_run', 'draft_version', 'location_restriction')
    autocomplete_fields = ['canonical_course_run']
    change_actions = ('course_skills', 'refresh_course_skills')

    def get_search_results(self, request, queryset, search_term):
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        if request.GET.get('app_label') == learner_pathway_app_name:
            queryset = queryset.filter(draft=False)
        return queryset, may_have_duplicates

    def get_readonly_fields(self, request, obj=None):
        """
        * Make UUID field editable for draft if flag is enabled.
        * Make product_source field readonly if the course obj is already created. In case a course
        without product_source is present, a superuser should be able to edit the product_source.

        By default, product_source & uuid are readonly. Remove them from list if either criteria is met
        """
        readonly_fields = self.readonly_fields.copy() + ['uuid', 'product_source']
        if obj and obj.draft:
            flag_name = f'{obj._meta.app_label}.{obj.__class__.__name__}.make_uuid_editable'
            flag = get_waffle_flag_model().get(flag_name)
            if flag.is_active(request):
                readonly_fields.remove('uuid')
        if (not obj) or (not obj.product_source and request.user.is_superuser):
            readonly_fields.remove('product_source')
        return readonly_fields

    def get_change_actions(self, request, object_id, form_url):
        """
        Get a list of change actions.

        Hide `Course Skills` action button for draft courses.
        """
        actions = super().get_change_actions(request, object_id, form_url)
        actions = list(actions)

        if not Course.objects.filter(id=object_id).exists():
            actions.remove('course_skills')

        return actions

    def course_skills(self, request, obj):
        """
        Object tool handler method - redirects to "Course Skills" view
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        course_skills_url = reverse(f"admin:{COURSE_SKILLS_URL_NAME}", args=(obj.pk,))
        return HttpResponseRedirect(course_skills_url)

    def refresh_course_skills(self, request, obj):
        """
        Object tool handler method - redirects to "Refresh Course Skills" view
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        refresh_course_skills_url = reverse(f"admin:{REFRESH_COURSE_SKILLS_URL_NAME}", args=(obj.pk,))
        return HttpResponseRedirect(refresh_course_skills_url)

    def get_urls(self):
        """
        Returns the additional urls used by the custom object tools.
        """
        additional_urls = [
            re_path(
                r"^([^/]+)/course_skills$",
                self.admin_site.admin_view(CourseSkillsView.as_view()),
                name=COURSE_SKILLS_URL_NAME
            ),
            re_path(
                r"^([^/]+)/refresh_course_skills$",
                self.admin_site.admin_view(RefreshCourseSkillsView.as_view()),
                name=REFRESH_COURSE_SKILLS_URL_NAME
            ),
        ]
        return additional_urls + super().get_urls()

    course_skills.label = "view course skills"
    course_skills.short_description = "view course skills"


@admin.register(CourseEditor)
class CourseEditorAdmin(admin.ModelAdmin):
    list_display = ('user', 'course',)
    search_fields = ('user__username', 'course__title', 'course__key',)
    raw_id_fields = ('user', 'course',)


@admin.register(CourseEntitlement)
class CourseEntitlementAdmin(SimpleHistoryAdmin):
    list_display = ['course', 'get_course_key', 'mode', 'draft']

    def get_course_key(self, obj):
        return obj.course.key

    get_course_key.short_description = 'Course key'

    raw_id_fields = ('course', 'draft_version',)
    search_fields = ['course__title', 'course__key']


@admin.register(Mode)
class ModeAdmin(admin.ModelAdmin):
    list_display = ['slug', 'name']


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ['mode', 'seat_type']


@admin.register(CourseRunType)
class CourseRunTypeAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'name']
    search_fields = ['uuid', 'name']


class CourseTypeAdminForm(ModelForm):
    class Meta:
        model = CourseType
        fields = '__all__'
        widgets = {
            'white_listed_orgs': CheckboxSelectMultiple
        }


@admin.register(CourseType)
class CourseTypeAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'name']
    search_fields = ['uuid', 'name']
    form = CourseTypeAdminForm


@admin.register(CourseRun)
class CourseRunAdmin(SimpleHistoryAdmin):
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
    readonly_fields = (
        'enrollment_count', 'recent_enrollment_count', 'hidden', 'key', 'enterprise_subscription_inclusion'
    )
    search_fields = ('uuid', 'key', 'title_override', 'course__title', 'slug', 'external_key')
    save_error = False
    form = CourseRunAdminForm

    def get_readonly_fields(self, request, obj=None):
        """
        Make UUID field editable for draft if flag is enabled.
        """
        if obj and obj.draft:
            flag_name = f'{obj._meta.app_label}.{obj.__class__.__name__}.make_uuid_editable'
            flag = get_waffle_flag_model().get(flag_name)
            if flag.is_active(request):
                return self.readonly_fields

        return self.readonly_fields + ('uuid',)

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

            msg = PUBLICATION_FAILURE_MSG_TPL.format(model='course run')
            messages.add_message(request, messages.ERROR, msg)


class CourseInline(admin.TabularInline):
    model = Course
    fields = ('key', 'title', 'draft')
    show_change_link = True

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CourseLocationRestriction)
class CourseLocationRestrictionAdmin(admin.ModelAdmin):
    list_display = ('id', 'restriction_type')
    fields = ('restriction_type', 'countries', 'states', 'created', 'modified')
    readonly_fields = ('created', 'modified')
    inlines = (CourseInline,)


@admin.register(TaxiForm)
class TaxiFormAdmin(admin.ModelAdmin):
    list_display = ('id', 'grouping', 'title')
    fields = ('form_id', 'grouping', 'title', 'subtitle', 'post_submit_url')
    readonly_fields = ('created', 'modified')


@admin.register(ProgramLocationRestriction)
class ProgramLocationRestrictionAdmin(admin.ModelAdmin):
    list_display = ('program', 'restriction_type',)
    fields = ('program', 'restriction_type', 'countries', 'states', 'created', 'modified')
    readonly_fields = ('created', 'modified')
    raw_id_fields = ('program',)
    search_fields = ('program__name', 'program__marketing_slug')


@admin.register(Program)
class ProgramAdmin(DjangoObjectActions, SimpleHistoryAdmin):
    form = ProgramAdminForm
    list_display = ('id', 'uuid', 'title', 'type', 'partner', 'status', 'hidden')
    list_filter = ('partner', 'type', 'product_source', 'status', ProgramEligibilityFilter, 'hidden')
    ordering = ('uuid', 'title', 'status')
    readonly_fields = (
        'uuid', 'custom_course_runs_display', 'excluded_course_runs', 'enrollment_count', 'recent_enrollment_count',
        'enterprise_subscription_inclusion', 'ofac_comment', 'data_modified_timestamp'
    )
    raw_id_fields = ('video',)
    search_fields = ('uuid', 'title', 'marketing_slug')
    exclude = ('card_image_url',)

    # ordering the field display on admin page.
    fields = (
        'uuid', 'title', 'subtitle', 'marketing_hook', 'product_source', 'type', 'status', 'partner', 'banner_image',
        'banner_image_url', 'card_image', 'marketing_slug', 'overview', 'credit_redemption_overview', 'video',
        'total_hours_of_effort', 'weeks_to_complete', 'min_hours_effort_per_week', 'max_hours_effort_per_week',
        'courses', 'order_courses_by_start_date', 'custom_course_runs_display', 'excluded_course_runs',
        'authoring_organizations', 'credit_backing_organizations', 'one_click_purchase_enabled', 'hidden',
        'corporate_endorsements', 'faq', 'individual_endorsements', 'job_outlook_items', 'expected_learning_items',
        'instructor_ordering', 'enrollment_count', 'recent_enrollment_count', 'credit_value',
        'organization_short_code_override', 'organization_logo_override', 'primary_subject_override',
        'level_type_override', 'language_override', 'enterprise_subscription_inclusion', 'in_year_value', 'labels',
        'geolocation', 'program_duration_override', 'has_ofac_restrictions', 'ofac_comment', 'data_modified_timestamp',
        'excluded_from_search', 'excluded_from_seo'
    )
    change_actions = ('refresh_program_skills', )

    save_error = False

    def get_readonly_fields(self, request, obj=None):
        """
        Make product_source field readonly if program obj is already created. In case a product without product_source
        is present, a superuser should be able to edit the product_source.
        """
        if (not obj) or (not obj.product_source and request.user.is_superuser):
            return self.readonly_fields
        return self.readonly_fields + ('product_source',)

    def get_urls(self):
        """
        Returns the additional urls used by the custom object tools.
        """
        additional_urls = [
            re_path(
                r"^([^/]+)/refresh_program_skills$",
                self.admin_site.admin_view(RefreshProgramSkillsView.as_view()),
                name=REFRESH_PROGRAM_SKILLS_URL_NAME
            ),
        ]
        return additional_urls + super().get_urls()

    def get_change_actions(self, request, object_id, form_url):
        actions = super().get_change_actions(request, object_id, form_url)
        actions = list(actions)

        obj = self.model.objects.get(pk=object_id)
        if obj.status != ProgramStatus.Active:
            actions.remove('refresh_program_skills')

        return actions

    def custom_course_runs_display(self, obj):
        return format_html('<br>'.join([str(run) for run in obj.course_runs]))

    custom_course_runs_display.short_description = _('Included course runs')

    def _redirect_course_run_update_page(self, obj):
        """ Returns a response redirect to a page where the user can update the
        course runs for the program being edited.

        Returns:
            HttpResponseRedirect
        """
        return HttpResponseRedirect(reverse('admin_metadata:update_course_runs', kwargs={'pk': obj.pk}))

    def refresh_program_skills(self, request, obj):
        """
        Object tool handler method - redirects to "Refresh Course Skills" view
        """
        refresh_program_skills_url = reverse(f"admin:{REFRESH_PROGRAM_SKILLS_URL_NAME}", args=(obj.pk,))
        return HttpResponseRedirect(refresh_program_skills_url)

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
            if obj.product_source and obj.product_source.ofac_restricted_program_types.filter(id=obj.type.id).exists():
                obj.mark_ofac_restricted()
            super().save_model(request, obj, form, change)
        except (MarketingSitePublisherException, MarketingSiteAPIClientException):
            self.save_error = True

            logger.exception('An error occurred while publishing program [%s] to the marketing site.', obj.uuid)

            msg = PUBLICATION_FAILURE_MSG_TPL.format(model='program')
            messages.add_message(request, messages.ERROR, msg)

    class Media:
        js = (
            'bower_components/jquery-ui/ui/minified/jquery-ui.min.js',
            'bower_components/jquery/dist/jquery.min.js',
            'js/sortable_select.js'
        )


@admin.register(Pathway)
class PathwayAdmin(admin.ModelAdmin):
    form = PathwayAdminForm
    readonly_fields = ('uuid',)
    list_display = ('name', 'uuid', 'org_name', 'partner', 'email', 'destination_url', 'pathway_type', 'get_programs',)
    search_fields = ('uuid', 'name', 'email', 'destination_url', 'pathway_type', 'programs__title')

    @admin.display(description='Programs')
    def get_programs(self, obj):
        return [*obj.programs.all()]


@admin.register(ProgramType)
class ProgramTypeAdmin(TranslatableAdmin):
    fields = ('name_t', 'applicable_seat_types', 'logo_image', 'slug', 'coaching_supported',)
    list_display = ('name_t', 'slug')


@admin.register(Seat)
class SeatAdmin(SimpleHistoryAdmin):
    list_display = ('course_run', 'type', 'draft', 'upgrade_deadline_override',)
    raw_id_fields = ('draft_version',)
    readonly_fields = ('_upgrade_deadline',)


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


@admin.register(Fact)
class FactAdmin(admin.ModelAdmin):
    list_display = ('heading', 'blurb', 'courses')
    search_fields = ('heading', 'blurb',)

    def courses(self, obj):

        def _get_course_keys(additional_metadata_object):
            return ', '.join([course.key for course in additional_metadata_object.related_courses.all()])

        return ', '.join([
            _get_course_keys(metadata) for metadata in obj.related_course_additional_metadata.all()
        ])


@admin.register(CertificateInfo)
class CertificateInfoAdmin(admin.ModelAdmin):
    list_display = ('heading', 'blurb', 'courses')
    search_fields = ('heading', 'blurb',)

    def courses(self, obj):

        def _get_course_keys(additional_metadata_object):
            return ', '.join([course.key for course in additional_metadata_object.related_courses.all()])

        return ', '.join([
            _get_course_keys(metadata) for metadata in obj.related_course_additional_metadata.all()
        ])


@admin.register(AdditionalMetadata)
class AdditionalMetadataAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'external_identifier', 'external_url', 'courses', 'facts_list', 'external_course_marketing_type',
    )
    search_fields = ('external_identifier', 'external_url')
    list_filter = ('product_status', )

    def courses(self, obj):
        return ', '.join([
            course.key for course in obj.related_courses.all()
        ])

    def facts_list(self, obj):
        return ', '.join([
            fact.heading for fact in obj.facts.all()
        ])


@admin.register(ProductMeta)
class ProductMetaAdmin(admin.ModelAdmin):
    list_display = ['title', 'description']
    search_fields = ['title']

    inlines = (
        AdditionalMetadataInline,
    )


class OrganizationUserRoleInline(admin.TabularInline):
    # course-meta-data models are importing in publisher app. So just for safe side
    # to avoid any circular issue importing the publisher model here.
    # pylint: disable=import-outside-toplevel
    from course_discovery.apps.publisher.models import OrganizationUserRole
    model = OrganizationUserRole
    extra = 3
    raw_id_fields = ('user',)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'key', 'name',)
    inlines = [OrganizationUserRoleInline, ]
    list_filter = ('partner',)
    search_fields = ('uuid', 'name', 'key',)

    def get_readonly_fields(self, request, obj=None):
        """
        Ensure that 'key' cannot be edited after creation.
        """
        if obj:
            flag_name = f'{obj._meta.app_label}.{obj.__class__.__name__}.make_uuid_editable'
            flag = get_waffle_flag_model().get(flag_name)
            if flag.is_active(request):
                return ['key', ]
            return ['uuid', 'key', ]
        else:
            return ['uuid', ]


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
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('src', 'description',)
    search_fields = ('src', 'description',)
    exclude = ('image',)


@admin.register(Prerequisite)
class PrerequisiteAdmin(admin.ModelAdmin):
    list_display = ('name',)
    ordering = ('name',)
    search_fields = ('name',)


@admin.register(LevelType)
class LevelTypeAdmin(SortableAdminMixin, TranslatableAdmin):
    list_display = ('name_t', 'sort_value')
    search_fields = ('name_t',)
    fields = ('name_t',)


class CurriculumProgramMembershipInline(admin.TabularInline):
    model = CurriculumProgramMembership
    fields = ('program', 'is_active')
    autocomplete_fields = ['program']
    extra = 0


class CurriculumCourseMembershipInline(admin.StackedInline):
    form = CurriculumCourseMembershipForm
    model = CurriculumCourseMembership
    readonly_fields = ("custom_course_runs_display", "course_run_exclusions", "get_edit_link",)

    def custom_course_runs_display(self, obj):
        return format_html('<br>'.join([str(run) for run in obj.course_runs]))

    custom_course_runs_display.short_description = _('Included course runs')

    def get_edit_link(self, obj=None):
        if obj and obj.pk:
            edit_url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk])
            return format_html(
                """<a href="{url}">{text}</a>""",
                url=edit_url,
                text=_("Edit course run exclusions"),
            )
        return _("(save and continue editing to create a link)")

    get_edit_link.short_description = _("Edit link")

    extra = 0


class CurriculumCourseRunExclusionInline(admin.TabularInline):
    model = CurriculumCourseRunExclusion
    autocomplete_fields = ['course_run']
    extra = 0


@admin.register(CurriculumProgramMembership)
class CurriculumProgramMembershipAdmin(admin.ModelAdmin):
    list_display = ('curriculum', 'program')


@admin.register(CurriculumCourseMembership)
class CurriculumCourseMembershipAdmin(admin.ModelAdmin):
    form = CurriculumCourseMembershipForm
    list_display = ('curriculum', 'course')
    inlines = (CurriculumCourseRunExclusionInline,)


@admin.register(CurriculumCourseRunExclusion)
class CurriculumCourseRunExclusionAdmin(admin.ModelAdmin):
    list_display = ("course_membership", "course_run")


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'program', 'name', 'is_active')
    inlines = (CurriculumProgramMembershipInline, CurriculumCourseMembershipInline)

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except IntegrityError:
            logger.exception('A database integrity error occurred while saving curriculum [%s].', obj.uuid)


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


class DegreeAdditionalMetadataInlineAdmin(admin.StackedInline):
    model = DegreeAdditionalMetadata


@admin.register(DegreeAdditionalMetadata)
class DegreeAdditionalMetadataAdmin(admin.ModelAdmin):
    list_display = ('degree', 'external_url', 'external_identifier', 'organic_url')


@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ('value', )


@admin.register(Degree)
class DegreeAdmin(admin.ModelAdmin):
    """
    This is an inheritance model from Program

    """
    list_display = ('uuid', 'title', 'marketing_slug', 'status', 'hidden', 'display_on_org_page')
    ordering = ('title', 'status')
    readonly_fields = ('uuid', )
    list_filter = ('partner', 'status',)
    search_fields = ('uuid', 'title', 'marketing_slug',)
    inlines = (
        CurriculumAdminInline,
        DegreeDeadlineInlineAdmin,
        DegreeCostInlineAdmin,
        IconTextPairingInline,
        DegreeAdditionalMetadataInlineAdmin,
    )
    # ordering the field display on admin page.
    fields = (
        'product_source', 'type', 'uuid', 'status', 'hidden', 'partner', 'authoring_organizations', 'marketing_slug',
        'card_image_url', 'search_card_ranking', 'search_card_cost', 'search_card_courses', 'overall_ranking',
        'campus_image', 'title', 'subtitle', 'title_background_image', 'banner_border_color', 'apply_url', 'overview',
        'rankings', 'application_requirements', 'prerequisite_coursework', 'lead_capture_image',
        'lead_capture_list_name', 'hubspot_lead_capture_form_id', 'taxi_form', 'micromasters_long_title',
        'micromasters_long_description', 'micromasters_url', 'micromasters_background_image',
        'micromasters_org_name_override', 'faq', 'costs_fine_print', 'deadlines_fine_print', 'specializations',
        'program_duration_override', 'display_on_org_page',
    )
    actions = ['publish_degrees', 'unpublish_degrees', 'display_degrees_on_org_page', 'hide_degrees_on_org_page']

    def change_degree_status(self, request, queryset, status):
        """
        Changes the status of a degree.
        """
        count = queryset.count()
        if count:
            for obj in queryset:
                obj.status = status
                obj.save()

            self.message_user(request, _("Successfully %(status)s %(count)d %(items)s.") % {
                "status": "published" if status == ProgramStatus.Active else "unpublished",
                "count": count,
                "items": model_ngettext(self.opts, count),
            }, messages.SUCCESS)

    @admin.action(permissions=['change'], description='Publish selected Degrees')
    def publish_degrees(self, request, queryset):
        """
        Django admin action to bulk publish degrees.
        """
        self.change_degree_status(request, queryset, ProgramStatus.Active)

    @admin.action(permissions=['change'], description='Unpublish selected Degrees')
    def unpublish_degrees(self, request, queryset):
        """
        Django admin action to bulk unpublish degrees.
        """
        self.change_degree_status(request, queryset, ProgramStatus.Unpublished)

    @admin.action(permissions=['change'], description="Display selected degrees on org page")
    def display_degrees_on_org_page(self, request, queryset):
        updated = queryset.update(display_on_org_page=True)
        self.message_user(
            request,
            f"{updated} {'degrees were' if updated>1 else 'degree was'} successfully set to display on org page.",
            messages.SUCCESS,
        )

    @admin.action(permissions=['change'], description="Hide selected degrees on org page")
    def hide_degrees_on_org_page(self, request, queryset):
        updated = queryset.update(display_on_org_page=False)
        self.message_user(
            request,
            f"{updated} {'degrees were' if updated>1 else 'degree was'} successfully set to be hidden on org page.",
            messages.SUCCESS,
        )


@admin.register(SearchDefaultResultsConfiguration)
class SearchDefaultResultsConfigurationAdmin(admin.ModelAdmin):
    form = SearchDefaultResultsConfigurationForm
    list_display = ('index_name',)

    class Media:
        js = (
            'bower_components/jquery-ui/ui/minified/jquery-ui.min.js',
            'bower_components/jquery/dist/jquery.min.js',
            'js/sortable_select.js'
        )


@admin.register(ExpectedLearningItem)
class ExpectedLearningItemAdmin(admin.ModelAdmin):
    search_fields = ('value',)


@admin.register(JobOutlookItem)
class JobOutlookItemAdmin(admin.ModelAdmin):
    search_fields = ('value',)


# Register remaining models using basic ModelAdmin classes
for model in (Image, SyllabusItem, PersonSocialNetwork, DataLoaderConfig,
              DeletePersonDupsConfig, DrupalPublishUuidConfig, MigrateCommentsToSalesforce,
              MigratePublisherToCourseMetadataConfig, ProfileImageDownloadConfig, PersonAreaOfExpertise,
              TagCourseUuidsConfig, BackpopulateCourseTypeConfig, RemoveRedirectsConfig, BulkModifyProgramHookConfig,
              BackfillCourseRunSlugsConfig, BulkUpdateImagesConfig, DeduplicateHistoryConfig):
    admin.site.register(model)


@admin.register(Collaborator)
class CollaboratorAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'name', 'image')
    readonly_fields = ('uuid', )
    search_fields = ('uuid', 'name')


@admin.register(CourseUrlSlug)
class CourseUrlSlugAdmin(admin.ModelAdmin):
    list_display = ('course', 'url_slug', 'is_active')
    search_fields = ('url_slug', 'course__title', 'course__key',)


@admin.register(CSVDataLoaderConfiguration)
class CSVDataLoaderConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for CSVDataLoaderConfiguration model.
    """
    list_display = ('id', 'enabled', 'changed_by', 'change_date')


@admin.register(DegreeDataLoaderConfiguration)
class DegreeDataLoaderConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for DegreeDataLoaderConfiguration model.
    """
    list_display = ('id', 'enabled', 'changed_by', 'change_date')


@admin.register(MigrateCourseSlugConfiguration)
class MigrateCourseSlugConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for MigrateCourseSlugConfiguration model.
    """
    list_display = ('id', 'enabled', 'changed_by', 'change_date')


@admin.register(ProgramSubscriptionConfiguration)
class ProgramSubscriptionConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for ProgramDataLoaderConfiguration model.
    """
    list_display = ('id', 'enabled', 'changed_by', 'change_date')


@admin.register(GeotargetingDataLoaderConfiguration)
class GeotargetingDataLoaderConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for GeotargetingDataLoaderConfiguration model.
    """
    list_display = ('id', 'enabled', 'changed_by', 'change_date')


@admin.register(GeolocationDataLoaderConfiguration)
class GeolocationDataLoaderConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for GeolocationDataLoaderConfiguration model.
    """
    list_display = ('id', 'enabled', 'changed_by', 'change_date')


@admin.register(ProductValueDataLoaderConfiguration)
class ProductValueDataLoaderConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for ProductValueDataLoaderConfiguration model.
    """
    list_display = ('id', 'enabled', 'changed_by', 'change_date')


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    """
    Admin for Source model.
    """
    list_display = ('id', 'name', 'slug', 'description')
    readonly_fields = ('slug',)


@admin.register(BulkUploadTagsConfig)
class BulkUploadTagsConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for BulkUploadTagsConfig model.
    """
    list_display = ('id', 'enabled', 'changed_by', 'change_date')


@admin.register(OrganizationMapping)
class OrganizationMappingAdmin(admin.ModelAdmin):
    """
    Admin settings to handle OrganizationMapping.
    """
    list_display = ('organization', 'source', 'organization_external_key')
    search_fields = ('organization__key', 'source__name', 'organization_external_key')


@admin.register(ProgramSubscription)
class ProgramSubscriptionAdmin(admin.ModelAdmin):
    """
    Admin settings for ProgramSubscription
    """
    readonly_fields = ('uuid', )
    search_fields = ("program__uuid", "program__title", "subscription_eligible")


@admin.register(ProgramSubscriptionPrice)
class ProgramSubscriptionPriceAdmin(admin.ModelAdmin):
    """
    Admin settings for ProgramSubscriptionPrice
    """
    readonly_fields = ('uuid', )
    search_fields = ("program_subscription__program__title", "program_subscription__program__uuid",
                     "price", "currency__name")
