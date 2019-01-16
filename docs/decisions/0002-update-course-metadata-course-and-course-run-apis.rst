2. Update Course Metadata Course and Course Run APIs
----------------------------------------------------

Status
------

Accepted

Context
-------

With Publisher being pulled out from course-discovery in favor of the creation of a self-service Publisher embedded inside of Studio, the existing Course and Course Run APIs need to be modified to accommodate the new use cases of self-service Publisher. Permission levels for access to the different write endpoints will be a necessary change, but will not be discussed in this Decision Document.

Decision
--------

We have decided to augment the existing Course and Course Run APIs from alternative choices described below. The changes will require setting permission levels for the endpoints based on the different permission groups defined for self-service Publisher.

Design
======
The modified endpoint will include POST, PATCH, and DELETE functionality. All of the write endpoints will have permission levels set up such that users will only be able to write to courses they have edit access to. Additionally, the GET endpoints for Courses and Course Runs will be changed to have the functionality to return the list of courses a user has edit access to.

Why
===
Self-service Publisher is intended for our users (course teams) to be able to create and edit course content without needing to include edX in the process. In pursuit of this functionality, we need APIs that can support creation, editing, and deletion so it can truly function as self-service. It is also important to include the appropriate permissions on each of these write endpoints to ensure no user is able to create a course, edit, or delete a course for an organization the user does not belong to.


Other Choices Considered
------------------------

#. Version API: Versioning the API was skipped due to there not being a need to change any of the functionality of the existing API. Since we would not be introducing any breaking changes to the API, it was decided that a new version was not necessary.

#. Create new API: Creating a new API could have led to having a new API based on the client consuming the API (in this case, self-service Publisher). Although we believed this option had merit since the existing API was intended as a read only view and the new consumer will be for writing, creating a new API for each new client seemed like overkill. Additionally, the current API already supports filtering the catalog based on the needs of marketing (a different client) and so to introduce a new API for our client was unnecessary.


Requirements
------------

* All current functionality of the Course and Course Run APIs remains the same for consumers.
* GET must still be able to return the full catalog to authenticated users.
* GET must be able to return the list of courses a user can edit to that user.
* A user should be able to POST a new course within the correct permissions for that user.
* A user should be able to PATCH to a course if the user has edit access to that course.
* A user should be ablt to DELETE a course if the user has edit access to that course.
