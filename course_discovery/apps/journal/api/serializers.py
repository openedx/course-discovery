"""Journal API Serializers"""
from rest_framework import serializers

from course_discovery.apps.api.serializers import MinimalCourseSerializer
from course_discovery.apps.journal.models import Journal, JournalBundle
from course_discovery.apps.core.models import Currency, Partner


class JournalSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``Journal`` model.
    """
    price = serializers.DecimalField(
        decimal_places=Journal.PRICE_FIELD_CONFIG['decimal_places'],
        max_digits=Journal.PRICE_FIELD_CONFIG['max_digits']
    )
    partner = serializers.SlugRelatedField(slug_field='name', queryset=Partner.objects.all())
    currency = serializers.SlugRelatedField(slug_field='code', queryset=Currency.objects.all())

    class Meta(object):
        model = Journal
        fields = ('id', 'uuid', 'partner', 'title', 'price', 'currency', 'sku', 'expires')


class JournalBundleSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``JournalBundle`` model.
    """
    courses = MinimalCourseSerializer(many=True, read_only=True)
    journals = JournalSerializer(many=True, read_only=True)
    partner = serializers.SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = JournalBundle
        fields = (
            'uuid',
            'title',
            'partner',
            'journals',
            'courses'
        )
