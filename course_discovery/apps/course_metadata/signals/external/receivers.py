import logging

from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete, post_save, m2m_changed
from django.dispatch import receiver
import pulsar
from pulsar.schema.schema import JsonSchema

from ...models import Course, CourseRun, Organization, Program
from .schema import CourseSchema, CourseRunSchema, OrganizationSchema, ProgramSchema
from .transformers import transform_course, transform_courserun, transform_organization, transform_program

logger = logging.getLogger(__name__)

# Create persistent client
client = pulsar.Client("pulsar://edx.devstack.pulsar:6650")

# Create and throw away producers to set initial state and schema
client.create_producer("discovery_course_change", schema=JsonSchema(CourseSchema))
client.create_producer("discovery_course_delete", schema=JsonSchema(CourseSchema))
client.create_producer("discovery_courserun_change", schema=JsonSchema(CourseRunSchema))
client.create_producer("discovery_courserun_delete", schema=JsonSchema(CourseRunSchema))
client.create_producer("discovery_organization_change", schema=JsonSchema(OrganizationSchema))
client.create_producer("discovery_organization_delete", schema=JsonSchema(OrganizationSchema))
client.create_producer("discovery_program_change", schema=JsonSchema(ProgramSchema))
client.create_producer("discovery_program_delete", schema=JsonSchema(ProgramSchema))

# Not needed unless create/update are on same topic as delete
# class ChangeTypeProperties:
#     CREATED = {"change_type": "created"}
#     UPDATED = {"change_type": "updated"}
#     DELETED = {"change_type": "deleted"}


#####
@receiver(m2m_changed, sender=Course.authoring_organizations.through)
@receiver([post_save, m2m_changed], sender=Course)
def announce_course_change(sender, instance, **kwargs):
    producer = client.create_producer("discovery_course_change", schema=JsonSchema(CourseSchema))
    data = transform_course(instance)
    producer.send(data)

@receiver(post_delete, sender=Course)
def announce_course_deletion(sender, instance, **kwargs):
    producer = client.create_producer("discovery_course_delete", schema=JsonSchema(CourseSchema))
    data = transform_course(instance)
    producer.send(data)

#####
@receiver([post_save, m2m_changed], sender=CourseRun)
def announce_courserun_change(sender, instance, **kwargs):
    producer = client.create_producer("discovery_courserun_change", schema=JsonSchema(CourseRunSchema))
    data = transform_courserun(instance)
    producer.send(data)

@receiver(post_delete, sender=CourseRun)
def announce_courserun_deletion(sender, instance, **kwargs):
    producer = client.create_producer("discovery_courserun_delete", schema=JsonSchema(CourseRunSchema))
    data = transform_courserun(instance)
    producer.send(data)

#####
@receiver([post_save, m2m_changed], sender=Organization)
def announce_organization_change(sender, instance, **kwargs):
    producer = client.create_producer("discovery_organization_change", schema=JsonSchema(OrganizationSchema))
    data = transform_organization(instance)
    producer.send(data)

@receiver(post_delete, sender=Organization)
def announce_organization_deletion(sender, instance, **kwargs):
    producer = client.create_producer("discovery_organization_delete", schema=JsonSchema(OrganizationSchema))
    data = transform_organization(instance)
    producer.send(data)

#####
# @receiver(m2m_changed, sender=Course.course_runs.through)
@receiver(m2m_changed, sender=Program.authoring_organizations.through)
@receiver(m2m_changed, sender=Program.excluded_course_runs.through)
@receiver(post_save, sender=Program)
def announce_program_change(sender, instance, **kwargs):
    producer = client.create_producer("discovery_program_change", schema=JsonSchema(ProgramSchema))
    logger.info(instance.excluded_course_runs.all())
    data = transform_program(instance)
    producer.send(data)

@receiver(post_delete, sender=Program)
def announce_program_deletion(sender, instance, **kwargs):
    producer = client.create_producer("discovery_program_delete", schema=JsonSchema(ProgramSchema))
    data = transform_program(instance)
    producer.send(data)
