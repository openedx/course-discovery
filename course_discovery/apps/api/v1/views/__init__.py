from django.conf import settings
from django.contrib.auth import get_user_model

from course_discovery.apps.api import serializers
from course_discovery.apps.api.exceptions import InvalidPartnerError
from course_discovery.apps.core.models import Partner

User = get_user_model()


def prefetch_related_objects_for_courses(queryset):
    """
    Pre-fetches the related objects that will be serialized with a `Course`.

    Pre-fetching allows us to consolidate our database queries rather than run
    thousands of queries as we serialize the data. For details, see the links below:

        - https://docs.djangoproject.com/en/1.10/ref/models/querysets/#select-related
        - https://docs.djangoproject.com/en/1.10/ref/models/querysets/#prefetch-related

    Args:
        queryset (QuerySet): original query

    Returns:
        QuerySet
    """
    _prefetch_fields = serializers.PREFETCH_FIELDS
    _select_related_fields = serializers.SELECT_RELATED_FIELDS

    # Prefetch the data for the related course runs
    course_run_prefetch_fields = _prefetch_fields['course_run'] + _select_related_fields['course_run']
    course_run_prefetch_fields = ['course_runs__' + field for field in course_run_prefetch_fields]
    queryset = queryset.prefetch_related(*course_run_prefetch_fields)

    queryset = queryset.select_related(*_select_related_fields['course'])
    queryset = queryset.prefetch_related(*_prefetch_fields['course'])
    return queryset


class PartnerMixin:
    def get_partner(self):
        """ Return the partner for the short_code passed in or the default partner """
        partner_code = self.request.query_params.get('partner')
        if partner_code:
            try:
                partner = Partner.objects.get(short_code=partner_code)
            except Partner.DoesNotExist:
                raise InvalidPartnerError('Unknown Partner: {}'.format(partner_code))
        else:
            partner = Partner.objects.get(id=settings.DEFAULT_PARTNER_ID)

        return partner
