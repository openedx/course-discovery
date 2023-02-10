# Import the consumer Command from event-bus-kafka in order to expose it here.
#
# FIXME: This currently hardcodes our use of the Kafka implementation.
#   https://github.com/openedx/openedx-events/issues/147 discusses ways
#   we might make this configurable.

# pylint: disable=unused-import
from edx_event_bus_kafka.management.commands.consume_events import Command
