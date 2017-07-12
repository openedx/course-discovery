from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.course_metadata.exceptions import (
    MarketingSiteAPIClientException, MarketingSitePublisherException
)
from course_discovery.apps.course_metadata.forms import CourseAdminForm, ProgramAdminForm
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


class PersonWorkInline(admin.TabularInline):
    model = PersonWork
    extra = 0


class PersonSocialNetworkInline(admin.TabularInline):
    model = PersonSocialNetwork
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    form = CourseAdminForm
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
        'hidden',
        ('language', admin.RelatedOnlyFieldListFilter,),
        'status',
    )
    ordering = ('key',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'key', 'title_override', 'course__title', 'slug',)
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
    readonly_fields = ('uuid', 'custom_course_runs_display', 'excluded_course_runs',)
    raw_id_fields = ('video',)
    search_fields = ('uuid', 'title', 'marketing_slug')

    filter_horizontal = ('job_outlook_items', 'expected_learning_items',)

    # ordering the field display on admin page.
    fields = (
        'uuid', 'title', 'subtitle', 'status', 'type', 'partner', 'banner_image', 'banner_image_url', 'card_image_url',
        'marketing_slug', 'overview', 'credit_redemption_overview', 'video', 'weeks_to_complete',
        'min_hours_effort_per_week', 'max_hours_effort_per_week', 'courses', 'order_courses_by_start_date',
        'custom_course_runs_display', 'excluded_course_runs', 'authoring_organizations',
        'credit_backing_organizations', 'one_click_purchase_enabled', 'hidden', 'corporate_endorsements', 'faq',
        'individual_endorsements',
    )
    fields += filter_horizontal
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


@admin.register(ProgramType)
class ProgramTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug',)


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
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'name', 'slug',)
    list_filter = ('partner',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'name', 'slug',)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    inlines = (PositionInline, PersonWorkInline, PersonSocialNetworkInline)
    list_display = ('uuid', 'family_name', 'given_name', 'slug',)
    list_filter = ('partner',)
    ordering = ('family_name', 'given_name', 'uuid',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'family_name', 'given_name', 'slug',)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('src', 'description',)
    search_fields = ('src', 'description',)


class NamedModelAdmin(admin.ModelAdmin):
    list_display = ('name',)
    ordering = ('name',)
    search_fields = ('name',)


# Register children of AbstractNamedModel
for model in (LevelType, Prerequisite,):
    admin.site.register(model, NamedModelAdmin)

# Register remaining models using basic ModelAdmin classes
for model in (Image, ExpectedLearningItem, SyllabusItem, PersonSocialNetwork, CourseRunSocialNetwork, JobOutlookItem,
              DataLoaderConfig):
    admin.site.register(model)
