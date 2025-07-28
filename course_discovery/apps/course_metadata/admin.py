from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin

from course_discovery.apps.course_metadata.exceptions import (
    MarketingSiteAPIClientException, MarketingSitePublisherException
)
from course_discovery.apps.course_metadata.forms import CourseAdminForm, ProgramAdminForm
from course_discovery.apps.course_metadata.models import *  # pylint: disable=wildcard-import

PUBLICATION_FAILURE_MSG_TPL = _(
    'An error occurred while publishing the {model} to the marketing site. '
    'Please try again. If the error persists, please contact the Engineering Team.'
)

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
    list_filter = ('org',)
    ordering = ('key', 'title',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'key', 'title',)


@admin.register(CourseRun)
class CourseRunAdmin(admin.ModelAdmin):
    inlines = (SeatInline,)
    list_display = ('uuid', 'key', 'title',)
    list_filter = (
        'course__org',
        'status',
    )
    ordering = ('key',)
    raw_id_fields = ('course',)
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'key', 'title_override', 'course__title')
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
    list_display = ('id', 'uuid', 'title', 'org', 'status')
    list_filter = ('org', 'status',)
    ordering = ('uuid', 'title', 'status')
    readonly_fields = ('uuid',)
    search_fields = ('uuid', 'title')

    # ordering the field display on admin page.
    fields = (
        'uuid', 'title', 'status', 'org', 'card_image_url', 'courses'
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


@admin.register(ProgramType)
class ProgramTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug',)


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('course_run', 'type')


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
    inlines = (PositionInline, PersonWorkInline, PersonSocialNetworkInline)
    list_display = ('uuid', 'salutation', 'family_name', 'given_name', 'slug',)
    list_filter = ('partner',)
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
