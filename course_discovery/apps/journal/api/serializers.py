"""Journal API Serializers"""
from rest_framework import serializers

from course_discovery.apps.api.serializers import MinimalCourseSerializer
from course_discovery.apps.core.models import Currency, Partner
from course_discovery.apps.course_metadata.models import Organization
from course_discovery.apps.journal.models import Journal, JournalBundle


class OrganizationSerializer(serializers.BaseSerializer):
    """
    Serializer for the ``Organization`` model.
    """
    def to_representation(self, instance):
        return instance.key

    def to_internal_value(self, data):
        return data

    def create(self, validated_data):  # pragma: no cover
        pass

    def update(self, instance, validated_data):  # pragma: no cover
        pass


class JournalSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``Journal`` model.
    """
    price = serializers.DecimalField(
        decimal_places=Journal.PRICE_FIELD_CONFIG['decimal_places'],
        max_digits=Journal.PRICE_FIELD_CONFIG['max_digits']
    )
    partner = serializers.SlugRelatedField(slug_field='short_code', queryset=Partner.objects.all())
    organization = OrganizationSerializer(many=False)
    currency = serializers.SlugRelatedField(slug_field='code', queryset=Currency.objects.all())

    def create(self, validated_data):
        org = Organization.objects.filter(
            key=validated_data.pop('organization'),
            partner=validated_data.get('partner')).first()
        validated_data['organization'] = org
        journal = Journal.objects.create(**validated_data)
        return journal

    class Meta(object):
        model = Journal
        fields = (
            'uuid',
            'partner',
            'organization',
            'title',
            'price',
            'currency',
            'sku',
            'card_image_url',
            'short_description',
            'full_description',
            'access_length',
            'status',
            'about_page_id',
        )

    @classmethod
    def prefetch_queryset(cls, queryset):
        return queryset.select_related(
            'partner',
            'organization',
            'currency',
        )


class JournalBundleSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``JournalBundle`` model.
    """
    courses = MinimalCourseSerializer(many=True, read_only=True)
    journals = JournalSerializer(many=True, read_only=True)
    partner = serializers.SlugRelatedField(slug_field='name', read_only=True)
    applicable_seat_types = serializers.SlugRelatedField(slug_field='slug', read_only=True, many=True)

    class Meta:
        model = JournalBundle
        fields = (
            'uuid',
            'title',
            'partner',
            'journals',
            'courses',
            'applicable_seat_types',
        )

    @classmethod
    def prefetch_queryset(cls, queryset):
        return queryset.select_related(
            'partner',
        ).prefetch_related(
            'journals',
            'courses',
            'applicable_seat_types',
        )
