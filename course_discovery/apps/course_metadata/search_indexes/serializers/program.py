import json

from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework import serializers
from taxonomy.choices import ProductTypes
from taxonomy.utils import get_whitelisted_serialized_skills

from course_discovery.apps.api.serializers import ContentTypeSerializer, ProgramSerializer
from course_discovery.apps.course_metadata.utils import get_product_skill_names
from course_discovery.apps.edx_elasticsearch_dsl_extensions.serializers import BaseDjangoESDSLFacetSerializer

from ..constants import BASE_PROGRAM_FIELDS, BASE_SEARCH_INDEX_FIELDS, COMMON_IGNORED_FIELDS
from ..documents import ProgramDocument
from .common import DocumentDSLSerializerMixin

__all__ = ('ProgramSearchDocumentSerializer',)


class ProgramSearchDocumentSerializer(DocumentSerializer):
    """
    Serializer for program elasticsearch document.
    """

    authoring_organizations = serializers.SerializerMethodField()
    skill_names = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()

    def get_authoring_organizations(self, program):
        organizations = program.authoring_organization_bodies
        return [json.loads(organization) for organization in organizations] if organizations else []

    def get_skill_names(self, program):
        return get_product_skill_names(program.uuid, ProductTypes.Program)

    def get_skills(self, program):
        return get_whitelisted_serialized_skills(program.uuid, product_type=ProductTypes.Program)

    class Meta:
        """
        Meta options.
        """

        document = ProgramDocument
        ignore_fields = COMMON_IGNORED_FIELDS
        fields = (
            BASE_SEARCH_INDEX_FIELDS +
            BASE_PROGRAM_FIELDS +
            (
                'authoring_organization_uuids',
                'authoring_organizations',
                'hidden',
                'is_program_eligible_for_one_click_purchase',
                'max_hours_effort_per_week',
                'min_hours_effort_per_week',
                'staff_uuids',
                'subject_uuids',
                'skill_names',
                'skills',
                'weeks_to_complete_max',
                'weeks_to_complete_min',
                'search_card_display',
                'is_2u_degree_program',
                'excluded_from_search',
                'excluded_from_seo',
            )
        )


# pylint: disable=abstract-method
class ProgramFacetSerializer(BaseDjangoESDSLFacetSerializer):
    """
    Serializer for program facets elasticsearch document.
    """

    class Meta:
        """
        Meta options.
        """

        ignore_fields = COMMON_IGNORED_FIELDS
        fields = BASE_PROGRAM_FIELDS + ('organizations',)


class ProgramSearchModelSerializer(DocumentDSLSerializerMixin, ContentTypeSerializer, ProgramSerializer):
    """
    Serializer for program model elasticsearch document.
    """

    class Meta(ProgramSerializer.Meta):
        """
        Meta options.
        """

        document = ProgramDocument
        fields = ContentTypeSerializer.Meta.fields + ProgramSerializer.Meta.fields
