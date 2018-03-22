"""Journal API Serializers"""
from rest_framework import serializers
from course_discovery.apps.journal.models import Journal


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
