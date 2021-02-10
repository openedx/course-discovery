from pulsar.schema import (
    Array,
    Float,
    Integer,
    Record,
    String,
)

class CourseSchema(Record):
    uuid = String()
    key = String()
    title = String()
    authoring_organizations = Array(String())  # List of UUIDs of Organizations

class CourseRunSchema(Record):
    course = String()
    uuid = String()
    title_override = String()
    key = String()
    start_date = Float()  # Stored as seconds since epoch
    end_date = Float()  # Stored as seconds since epoch

class OrganizationSchema(Record):
    uuid = String()
    key = String()
    name = String()
    certificate_logo_url = String()

class ProgramSchema(Record):
    uuid = String()
    title = String()
    course_runs = Array(String())  # List of UUIDs of CourseRuns
    authoring_organizations = Array(String())  # List of UUIDs of Organizations
    type_localized = String()
    type_slug = String()
    hours_of_effort = Integer()
    status = String()
