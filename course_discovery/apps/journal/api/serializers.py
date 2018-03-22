"""Journal API Serializers"""
from rest_framework import serializers

from course_discovery.apps.api.serializers import MinimalCourseSerializer
from course_discovery.apps.journal.models import Journal, JournalBundle


class JournalSerializer(serializers.HyperlinkedModelSerializer):
    """Serializer for the ``Journal`` model."""
    price = serializers.DecimalField(
        decimal_places=Journal.PRICE_FIELD_CONFIG['decimal_places'],
        max_digits=Journal.PRICE_FIELD_CONFIG['max_digits']
    )
    currency = serializers.SlugRelatedField(read_only=True, slug_field='code')
    sku = serializers.CharField()
    expires = serializers.DateTimeField()

    # @classmethod
    #def prefetch_queryset(cls):
    #   return Journal.objects.all().select_related('currency')

    class Meta(object):
        model = Journal
        # TODO - add partner
        fields = ('uuid', 'title', 'price', 'currency', 'sku', 'expires')


class JournalBundleSerializer(serializers.ModelSerializer):
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
