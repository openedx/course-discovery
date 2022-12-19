import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from edx_event_bus_kafka import KafkaEventConsumer
from edx_toggles.toggles import SettingToggle
from openedx_events.tooling import OpenEdxPublicSignal

logger = logging.getLogger(__name__)


# FIXME: This is currently a direct copy of the Kafka implementation. In the future,
# we would like to make this configurable to different implementations of the event bus.
class Command(BaseCommand):
    """
    Consumes events off the event bus implementation and fires signals in response.
    """

    help = """
    This starts a Kafka event consumer that listens to the specified topic and logs all messages it receives. Topic
    is required.
    example:
        python3 manage.py cms consume_events -t user-event-debug -g user-event-consumers
    # TODO (EventBus): Add pointer to relevant future docs around topics and consumer groups, and potentially
    update example topic and group names to follow any future naming conventions.
    """

    def add_arguments(self, parser):

        parser.add_argument(
            '-t', '--topic',
            nargs=1,
            required=True,
            help='Topic to consume'
        )

        parser.add_argument(
            '-g', '--group_id',
            nargs=1,
            required=True,
            help='Consumer group id'
        )
        parser.add_argument(
            '-s', '--signal',
            nargs=1,
            required=True,
            help='Type of signal to emit from consumed messages.'
        )
        parser.add_argument(
            '-o', '--offset_time',
            nargs=1,
            required=False,
            default=None,
            help='The timestamp (in ISO format) that we would like to set the consumers to read from on startup.'
                  'Overrides existing offsets.'
        )

    # We are not testing the current version of this code because it is copied from tested code
    # in event-bus-kafka, and this code will have to change once we have a better idea for the
    # consumer API. (https://github.com/openedx/event-bus-kafka/issues/19)
    def handle(self, *args, **options):  # pragma: no cover
        try:
            import confluent_kafka  # pylint: disable=import-outside-toplevel,unused-import
        except ImportError:
            logger.info("Cannot consume events because confluent-kafka is are not available.")
            return

        # .. toggle_name: EVENT_BUS_KAFKA_CONSUMERS_ENABLED
        # .. toggle_implementation: SettingToggle
        # .. toggle_default: False
        # .. toggle_description: Enables the ability to listen and process events from the Kafka event bus
        # .. toggle_use_cases: opt_in
        # .. toggle_creation_date: 2022-01-31
        # .. toggle_tickets: https://openedx.atlassian.net/browse/ARCHBOM-1992
        KAFKA_CONSUMERS_ENABLED = SettingToggle('EVENT_BUS_KAFKA_CONSUMERS_ENABLED', default=False)

        if not KAFKA_CONSUMERS_ENABLED.is_enabled():
            logger.info("Kafka consumers not enabled")
            return
        try:
            signal = OpenEdxPublicSignal.get_signal_by_type(options['signal'][0])
            if options['offset_time'] and options['offset_time'][0] is not None:
                try:
                    offset_timestamp = datetime.fromisoformat(options['offset_time'][0])
                except ValueError:
                    logger.exception('Could not parse the offset timestamp.')
                    raise
            else:
                offset_timestamp = None

            event_consumer = KafkaEventConsumer(
                topic=options['topic'][0],
                group_id=options['group_id'][0],
                signal=signal,
            )
            event_consumer.consume_indefinitely(offset_timestamp=offset_timestamp)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error consuming Kafka events")
