from .schema import CourseSchema, CourseRunSchema, OrganizationSchema, ProgramSchema

def transform_course(instance):
    return CourseSchema(
        uuid = str(instance.uuid),
        key = str(instance.key),
        title = str(instance.title),
        authoring_organizations = [str(org.uuid) for org in instance.authoring_organizations.all()],
    )

def transform_courserun(instance):
    return CourseRunSchema(
        course = str(instance.course.uuid),
        uuid = str(instance.uuid),
        title_override = str(instance.title_override),
        key = str(instance.key),
        start_date = float(instance.start.timestamp()),
        end_date = float(instance.end.timestamp()),
    )

def transform_organization(instance):
    cert_logo_url = getattr(instance, "certificate_logo_image", None)
    return OrganizationSchema(
        uuid = str(instance.uuid),
        key = str(instance.key),
        name = str(instance.name),
        certificate_logo_url = str(cert_logo_url.url if cert_logo_url else ""),
    )

def transform_program(instance):
    program_course_run_uuids = set()
    program_courses = instance.courses.all()
    for program_course in program_courses:
        for program_course_run in program_course.course_runs.all():
            program_course_run_uuids.add(str(program_course_run.uuid))
    for excluded_run in instance.excluded_course_runs.all():
        program_course_run_uuids.remove(str(excluded_run.uuid))

    schema = ProgramSchema(
        uuid = str(instance.uuid),
        title = str(instance.title),
        course_runs = list(program_course_run_uuids),
        authoring_organizations = [str(org.uuid) for org in instance.authoring_organizations.all()],
        type_localized = str(instance.type),
        type_slug = str(instance.type.slug),
        status = str(instance.status),
    )
    if instance.total_hours_of_effort:
        schema.hours_of_effort = int(instance.total_hours_of_effort)
    return schema
