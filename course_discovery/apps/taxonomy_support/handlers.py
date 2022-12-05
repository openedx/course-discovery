import logging

from django.dispatch import receiver
from openedx_events.content_authoring.data import DuplicatedXBlockData, XBlockData
from openedx_events.content_authoring.signals import XBLOCK_DELETED, XBLOCK_DUPLICATED, XBLOCK_PUBLISHED
from taxonomy.signals.signals import UPDATE_XBLOCK_SKILLS
from taxonomy.signals.signals import XBLOCK_DELETED as TAXONOMY_XBLOCK_DELETED
from taxonomy.signals.signals import XBLOCK_DUPLICATED as TAXONOMY_XBLOCK_DUPLICATED

logger = logging.getLogger(__name__)


@receiver(XBLOCK_DELETED)
def handle_xblock_deleted_event(**kwargs):
    """
    When we get a signal indicating that the xblock was deleted, make sure to
    trigger taxonomy xblock deleted signal.

    Args:
        kwargs: event data sent to signal
    """
    xblock_data = kwargs.get('xblock_info', None)
    if not xblock_data or not isinstance(xblock_data, XBlockData):
        logger.error('Received null or incorrect data from XBLOCK_DELETED.')
        return

    # Send signal to taxonomy-connector to delete related xblock skills.
    TAXONOMY_XBLOCK_DELETED.send(sender="OPENEDX_EVENTS", xblock_uuid=xblock_data.usage_key)


@receiver(XBLOCK_DUPLICATED)
def handle_xblock_duplicated_event(**kwargs):
    """
    When we get a signal indicating that the xblock was duplicated, make sure to
    trigger taxonomy xblock duplicated signal.

    Args:
        kwargs: event data sent to signal
    """
    xblock_data = kwargs.get('xblock_info', None)
    if not xblock_data or not isinstance(xblock_data, DuplicatedXBlockData):
        logger.error('Received null or incorrect data from XBLOCK_DUPLICATED.')
        return

    # Send signal to taxonomy-connector to copy XBlock skills for the duplicated block.
    TAXONOMY_XBLOCK_DUPLICATED.send(
        sender="OPENEDX_EVENTS",
        source_xblock_uuid=xblock_data.source_usage_key,
        xblock_uuid=xblock_data.usage_key,
    )


@receiver(XBLOCK_PUBLISHED)
def handle_xblock_published_event(**kwargs):
    """
    When we get a signal indicating that the xblock was publised, make sure to
    trigger taxonomy xblock publised signal.

    Args:
        kwargs: event data sent to signal
    """
    xblock_data = kwargs.get('xblock_info', None)
    if not xblock_data or not isinstance(xblock_data, XBlockData):
        logger.error('Received null or incorrect data from XBLOCK_PUBLISHED.')
        return

    # Send signal to taxonomy-connector to update the skills of the published XBlock.
    UPDATE_XBLOCK_SKILLS.send(sender="OPENEDX_EVENTS", xblock_uuid=xblock_data.usage_key)
