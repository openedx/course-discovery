23. External Source based course filtering for Publisher
=============================================================

Status
=======

In-Progress

Context
========

Frontend App Publisher (MFE) uses different APIs in Discovery to view, create and edit courses.
This has been an internal tool that only allows Course Editors to perform these actions.
With the inclusion of other product lines in the Catalog, there has been a need to allow external users to be able to perform actions like viewing and updating their courses through Publisher.
These external users should have Course Editor access to be able to visit Publisher and should only be able to view and edit their own courses only.
Currently, these products are created and added in Discovery using `csv_loader`_ and `degrees_loader`_
The external users should not be able to create these products through Publisher.

 .. _csv_loader: https://github.com/openedx/course-discovery/blob/master/course_discovery/apps/course_metadata/data_loaders/csv_loader.py
 .. _degrees_loader: https://github.com/openedx/course-discovery/blob/master/course_discovery/apps/course_metadata/data_loaders/degrees_loader.py

Decision
=========

The access checks will be implemented using role based authorization using `edx-rbac`_

* A feature-based role will be created for each product line in Discovery. Each role will have product_source(s) and course_type(s) which will be used in permissions and filtering.
* The role will be assigned to external users within Discovery. The role will be accessible through an exposed endpoint and that user would only be able to see its assigned role. The role assignment will contain other information, such as the assignment date, the reason for giving access, access history, etc.
* Publisher will make an additional API call to get the users' assigned role. Based upon the assignment, the behavior of publisher will change.

 .. _edx-rbac: https://github.com/openedx/edx-rbac

Consequences
------------

This approach will keep the internal flow of Publisher as it is but will give users from other product lines access to a subset of courses and related objects.

Alternates Considered
-----------------------

* Using Django User group, assign the users the new group, and make decisions based on the group. Additional information like product_source and course_type specific to each user group was to be added in the django groups. This approach, however, falls short in adding metadata of the role assignment.
* Using a Config Model to save mapping for each user group. The decision was to rather use rbac instead of user groups hence this approach isn't usable anymore. We will keep the mapping of each role in edx-internal.