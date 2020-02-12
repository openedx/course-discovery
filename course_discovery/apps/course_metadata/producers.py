
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
    # Need to add serializer tests to make sure our contract or some
    # set of base fields does not change. In the case where we want
    # to remove some of these old fields, we should create a new serializer
    # and publish messages on save (or whatever) with multiple serialzers.
    # the consumers can then decide which message they want to listen to.
    #
    # The test should be comparing a message to a json that explicitly includes
    # the fields below (as done at hackathon)
    class Meta:
        model = Program
        fields = (
            'id', 'created', 'modified', 'uuid', 'title', 'subtitle',
            'marketing_hook', 'status', 'marketing_slug',
            'order_courses_by_start_date', 'overview', 'total_hours_of_effort',
            'weeks_to_complete', 'min_hours_effort_per_week',
            'max_hours_effort_per_week', 'banner_image', 'banner_image_url',
            'card_image_url', 'credit_redemption_overview', 'one_click_purchase_enabled',
            'hidden', 'enrollment_count', 'recent_enrollment_count', 'credit_value',
            'type', 'partner', 'video', 'courses', 'excluded_course_runs',
            'authoring_organizations', 'expected_learning_items', 'faq',
            'instructor_ordering', 'credit_backing_organizations',
            'corporate_endorsements', 'job_outlook_items', 'individual_endorsements',
        )

# TODO - make this read from a setting
connection = Connection('redis://:password@redis:6379/10')
producer = connection.Producer()

