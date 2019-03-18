from course_discovery.apps.course_metadata.models import Course, CourseEntitlement, CourseRun, Seat


def set_draft_state(obj, model, attrs=None):
    """
    Sets the draft state for an object by giving it a new primary key. Also sets any given
    attributes (primarily used for setting foreign keys that also point to draft rows). This will
    make any additional operations on the object to be done to the new draft state object.

    Parameters:
        obj (Model object): The object to create a draft state for. *Must have draft and draft_version as attributes.*
        model (Model class): the model class so it can be used to get the original object
        attrs ({str: value}): Dictionary of attributes to set on the draft model. The key should be the
            attribute name as a string and the value should be the value to set.

    Returns:
        (Model obj, Model obj): Tuple of Model objects where the first is the draft object
            and the second is the original
    """
    original_obj = model.objects.get(pk=obj.pk)
    obj.pk = None
    obj.draft = True
    if attrs:
        for key, value in attrs.items():
            setattr(obj, key, value)
    # Will throw an integrity error if the draft row already exists, but this
    # should be caught as part of a try catch in the API calling ensure_draft_world
    obj.save()
    original_obj.draft_version = obj
    original_obj.save()
    return obj, original_obj


def ensure_draft_world(obj):
    """
    Ensures the draft world exists for an object. The draft world is defined as all draft objects related to
    the incoming draft object. For now, this will create the draft Course, all draft Course Runs associated
    with that course, all draft Seats associated with all of the course runs, and all draft Entitlements
    associated with the course.

    Assumes that if the given object is already a draft, the draft world for that object already exists.

    Will throw an integrity error if the draft row already exists, but this
    should be caught as part of a try catch in the API calling ensure_draft_world

    Parameters:
        obj (Model object): The object to create a draft state for. *Must have draft as an attribute.*

    Returns:
        obj (Model object): The returned object will be the draft version on the input object.
    """
    if obj.draft:
        return obj

    if isinstance(obj, CourseRun):
        ensure_draft_world(obj.course)
        return CourseRun.everything.get(key=obj.key, draft=True)

    elif isinstance(obj, Course):
        # We need to null this out because it will fail with a OneToOne uniqueness error when saving the draft
        obj.canonical_course_run = None
        draft_course, original_course = set_draft_state(obj, Course)
        draft_course.slug = original_course.slug

        # Create draft course runs, the corresponding draft seats, and the draft entitlement
        for run in original_course.course_runs.all():
            draft_run, original_run = set_draft_state(run, CourseRun, {'course': draft_course})
            draft_run.slug = original_run.slug
            draft_run.save()

            for seat in original_run.seats.all():
                set_draft_state(seat, Seat, {'course_run': draft_run})
            if original_course.canonical_course_run and draft_run.uuid == original_course.canonical_course_run.uuid:
                draft_course.canonical_course_run = draft_run
        for entitlement in original_course.entitlements.all():
            set_draft_state(entitlement, CourseEntitlement, {'course': draft_course})

        draft_course.save()
        return draft_course
    else:
        raise Exception('Ensure draft world only accepts Courses and Course Runs.')
