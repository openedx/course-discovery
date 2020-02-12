
from kombu import Connection, Exchange, Queue
from rest_framework import serializers

from course_discovery.apps.course_metadata.models import Program

from django.conf import settings

program_exchange = Exchange(settings.EDX_CATALOG_EXCHANGE, type='direct')
program_create_task_queue = Queue(
    settings.EDX_PROGRAM_CREATE_QUEUE_NAME,
    program_exchange,
    routing_key=settings.EDX_PROGRAM_CREATE_ROUTING_KEY
)
program_update_task_queue = Queue(
    settings.EDX_PROGRAM_UPDATE_QUEUE_NAME,
    program_exchange,
    routing_key=settings.EDX_PROGRAM_UPDATE_ROUTING_KEY
)
program_delete_task_queue = Queue(
    settings.EDX_PROGRAM_DELETE_QUEUE_NAME,
    program_exchange,
    routing_key=settings.EDX_PROGRAM_DELETE_ROUTING_KEY
)



class ProgramMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = '__all__'

# TODO - make this read from a setting
connection = Connection('redis://:password@redis:6379/0')
producer = connection.Producer()

