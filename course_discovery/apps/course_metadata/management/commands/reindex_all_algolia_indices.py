import logging

from algoliasearch_django import get_registered_model, reindex_all
from django.core.management import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = 'Wrapper command for Algolia\'s algolia_reindex'

    def handle(self, *args, **options):
        for model in get_registered_model():
            try:
                counts = reindex_all(model, batch_size=1000)
                logger.info('\t* {} --> {}'.format(model.__name__, counts))
            except Exception as e:  # pylint: disable=broad-except
                content = e.content.decode('utf8') if hasattr(e, 'content') else str(e)
                msg = 'Failed to reindex: {}'.format(content)
                logger.exception(msg)
