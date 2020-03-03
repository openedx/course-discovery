import logging

from algoliasearch_django import get_registered_model, reindex_all
from django.core.management import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = 'Wrapper command for Algolia\'s algolia_reindex'

    def handle(self, *args, **options):
        for model in get_registered_model():
            counts = reindex_all(model, batch_size=1000)
            logger.info('\t* {} --> {}'.format(model.__name__, counts))
