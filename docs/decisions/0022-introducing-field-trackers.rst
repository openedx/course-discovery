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

Lets consider the following example. In our `couse_discovery.apps.course_metadata.models` we have a `Course` Model. The changes mentioned above will look similar to following:


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

* The field tracker solution does not work well with Django ORM update() method because the method does not trigger save(). Discovery course API use update method on various linked objects. That would mean updating API to use save() instead of update to trigger last modified update flow
* Directly changing the related objects of Course or Program (via admin or ORM) does not update last modified timestamp. There will be a need to add pre_save signals for desired models to allow changing last modified timestamp for Courses and Programs when their related objects are changed directly.

Alternates Considered
======================

* All of this functionality can be added inside a `pre_save` signal. However, overriding the `save()` method seems like a straightforward way.
* Most models in the discovery service inherit a `TimeStampedModel`, which include a modified field. However, this field is updated everytime the `save()` function is called, even if there is no change.
* django-simple-history provides a capability to query Django object history. However, the history is only for main object and does not apply to changes in related objects. To use django-simple-history for tracking changes, there would be a need to add history objects for all of the related models for Course and Program. Also, the history query makes an additional DB call to get object which can have its performance aspects in the long run.


References
============

* https://django-model-utils.readthedocs.io/en/latest/utilities.html#field-tracker
* https://ilovedjango.com/django/models-and-databases/tips/field-tracker/
* https://stackoverflow.com/questions/36600293/django-tracking-if-a-field-in-the-model-is-changed
* https://django-simple-history.readthedocs.io/en/latest/querying_history.html
