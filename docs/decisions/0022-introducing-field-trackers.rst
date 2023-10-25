22. Tracking data changes using Field Trackers in Discovery
=============================================================

Status
=======

Accepted

Context
========

Discovery provides data to various services in Open edX ecosystem, including but not limited to Studio, E-commerce, and frontend marketing site. The current APIs in Discovery provide all the products with some limited filtering capabilities.
With a large data set in Discovery, the time to fetch the data is large and can cause bottleneck in many different areas of Open edX infrastructure.
There is no way to identify which products have been changed over a period of time. Therefore, the services have to fetch all the information from Discovery to utilize data or keep data in sync.

Decision
=========

There are two capabilities being added in Discovery to overcome the above challenges:

* Add timestamp filter capabilities in courses and programs APIs.
* Introduce a new field, **data_modified_timestamp**, in Course and Program models that contains the timestamp a product was changed.

timestamp filter
-----------------

The timestamp filter will be available as query parameter **timestamp**. The timestamp will take date or datetime in isoformat **YYYY-MM-DDTHH:MM:SS**. The timestamp filter will list the products that have been modified since the provided timestamp.

With the introduction of timestamp-based query, the services will have capability to fetch data changed in a specified duration. Resultantly, there will be lesser data to fetch, return and consume for every discovery API call, reducing the processing and time cost considerably.

Field trackers
----------------

A challenge with data_modified_timestamp field is identifying how to track changes in model and its related objects. During the investigation, a utility class `FieldTracker` built inside `django-model-utils` was discovered. When added to a model, it will track all modification to it's values until `save()` is called. It has capabilities of tracking all modifications, such as old and new values, and if a value has been changed or not.

FieldTracker will be added to select models inside various course-discovery apps. The `save()` method of Course and Program models will be overridden, checking if any change has been observed as well as editable `ForeignKeys`. If there is a change, the `data_modified_timestamp` will be updated to the current timestamp.

Let's consider the following example. In `course_discovery.apps.course_metadata.models`, the changes mentioned above will look similar as following for `Course` Model:


.. code-block::

    from datetime import datetime
    from model_utils import FieldTracker


    class Course(TimeStampedModel):

        field_tracker = FieldTracker()
        data_modified_timestamp = models.DateTimeField()

        @property
        def has_changed(self, external_fields):
            change = field_tracker.has_changed() and len(field_tracker.changed())
            for field in external_fields:  # Foreign keys to check
                change = change and field.has_changed()
            return change

        def save(self, *args, **kwargs):
            if self.has_changed([self.partner, self.course_run]):
                self.data_modified_timestamp = datetime.now()
            super().save(*args, **kwargs)


Implications
=============

* Diamond Problem - Consider a Program that has two courses. If a Program's data is altered by a course query, should the modifications be reflected in other courses from the same program?
* Child-Parent Relationship - Consider a Program having courses. If a Program's data is altered, should it reflect it in course? Or vice versa?

Future Improvements
=====================

1. The field tracker solution does not work well with Django ORM update() method because the method does not trigger save(). Discovery course API use update method on various linked objects. That would mean updating API to use save() instead of update to trigger last modified update flow
2. Directly changing the related objects of Course or Program (via admin or ORM) does not update last modified timestamp. There will be a need to add pre_save signals for desired models to allow changing last modified timestamp for Courses and Programs when their related objects are changed directly.

Alternates Considered
======================

* All of this functionality can be added inside a `pre_save` signal. However, overriding the `save()` method seems like a straightforward way.
* Most models in the discovery service inherit a `TimeStampedModel`, which include a modified field. However, this field is updated everytime the `save()` function is called, even if there is no change.
* django-simple-history provides a capability to query Django object history. However, the history is only for main object and does not apply to changes in related objects. To use django-simple-history for tracking changes, there would be a need to add history objects for all of the related models for Course and Program. Also, the history query makes an additional DB call to get object which can have its performance aspects in the long run.

Updates (August 2023)
======================
This section has been added to highlight some integral changes that had to be done to support tracking data changes for **Course** model.

Only updating draft objects timestamps
---------------------------------------
An additional condition has been added alongside FieldTracker to detect if an object has changed. If the object being changed is the draft version of the entity, only then perform the timestamp updates.
This has been done to fix an issue where saving a Course via API with no changes was resulting in timestamp update for non-draft version.

`set_official_state`_, a util responsible for converting draft to non-draft, was the root-cause for this behavior. The primary key of non-draft (associated with draft object) is assigned to draft object to make it non-draft.The original draft obj is assigned to non-draft to ensure the data sync. This resulted in the field tracker treating non-draft course/course run as changed, which then updated the data_modified_timestamp field for non-draft version.
Although the behavior was only happening for Course & CourseRun models, the draft checks have been added to all the models that inherit DraftModelMixin. This has been done to keep consistent behavior of timestamp updates across models.

.. _set_official_state: https://github.com/openedx/course-discovery/blob/11c50c6e61eb5e26b1462e41d077e5b22e01f7fa/course_discovery/apps/course_metadata/utils.py#L68

Addition of pre_save and m2m_changed signal handlers
-----------------------------------------------------
This change is the 2nd item mentioned in Future Improvements. The field tracker only tracks the changes on the model field values and the IDs of foreign keys. Let's consider the Course - CourseRun relationship (1-Many). The field tracker on CourseRun will monitor CourseRun fields. If something changes in Course, the field tracker of CourseRun will not know about it.
In Discovery, the Course model has relationship to many models. If the field/data of the related model objects change, the data_modified_timestamp on Course should be updated to showcase that the Course, as an entity, has modified.

To achieve that, pre_save and m2m_changed signal handlers have been added on select models. The select models are those that can be changed using Publisher MFE, via Course API. The rationale is that the required information for a course is present on Publisher MFE. Hence, the underlying related models should have signal handlers to update the timestamp for Course.

- pre_save on related Foreign/OneToOne relationship
   - AdditionalMetadata
   - CertificateInfo
   - Facts
   - ProductMeta
   - GeoLocation
   - CourseLocationRestriction
   - ProductValue
   - CourseEntitlement
   - Seat
- m2m_changed on Many-Many relationship change
   - Collaborators
   - Topics/Tags
   - Subjects
   - Staff

M2M relationships
-------------------

Following two categories of M2M relationships on Course model are of importance here:

* SortedM2M Field

* Taggable Manager

Sorted M2M
-----------
Internally, SortedM2M first clears the M2M relation and then adds the value back again. The clear is always done to maintain the ordering of the objects in M2M relationship. Due to clearing, it was not possible to compare m2m values on Course / CourseRun objects when adding a handler against m2m_changed (pre_add, pre_delete). The respective M2M would always be empty when received in signal handlers.

The workaround for this involves draft & non-draft objects. In Discovery APIs, all the edits are made to draft object first. Then, the same edits are carried over to non-draft. This workflow is used in m2m_changed signal handler to identify if a sorted M2M has changes in values.  This is done by getting M2M relationship pks from non-draft versions of Course/CourseRun and then comparing those pks with values being added in m2m_relationship, via pk_set kwarg, on draft version. If the primary keys of m2m relation fields on non-draft are same as pk_set available in m2m changed signal handler, that means no change has been made in the relationship. This approach does not check the ordering of added values, only the values themselves.

Taggable Manager
----------------
Taggable manager in django-taggit uses TaggedItem to store information about the tags assigned to Django model objects (via content type). TaggedItem is the default through value when setting up TaggableManager for a model. In Discovery course_metadata app, the value for through is not defined whenever TaggableManager is used (be it Org, Course, ProductMeta, Program, etc).

To receive m2m_changed signal, a sender needs to be specified. The sender is intermediate or through model (which is TaggedItem in this case). When m2m_changed is attempted to be set only for a specific field, let's say Course.topics, since through=TaggedItem, it resulted in executing all signal handlers of Taggable Manager, even those whose sender was different.

To be able to identify which model initiated the tag change, explicit model label checks have been added in respective signal handlers. By checking the model labels, the correct handler code gets executed which then updates the timestamp field for course.

References
============

* https://django-model-utils.readthedocs.io/en/latest/utilities.html#field-tracker
* https://ilovedjango.com/django/models-and-databases/tips/field-tracker/
* https://stackoverflow.com/questions/36600293/django-tracking-if-a-field-in-the-model-is-changed
* https://django-simple-history.readthedocs.io/en/latest/querying_history.html
