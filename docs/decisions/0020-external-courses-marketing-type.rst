20. Defining Marketing category for External Courses
------------------------------------------------------------------

Status
------

Accepted (January 2023)

Context
-------

Discovery has been traditionally used to author the marketing information of the courses offered on the platform. The course authors or editors would setup course and course runs
using Publisher MFE and use discovery APIs to get required information. Apart from providing on-site courses' marketing, there are capabilities in Discovery
that allow it to act like a Marketplace where courses external to platform can be marketed. The external courses utilize the course
and course run types present in Discovery.

With external courses, there is one exception. How can they be marketed differently from existing course types? It is certainly possible to create new course
and course run types to fulfill the marketing needs. The process of curating new course and course run types is complex. Creating a new course or course run type requires changes across Discovery, E-commerce, and Platform.

Decision
--------

In AdditionalMetadata model, present in course_metadata app, a new field called **external_course_marketing_type** will be added. The field will contain the possible choices an external courses can have. The course will remain linked with the desired course type and use the newly added field to drive behavior on frontend experience.

Consequences
------------

* The addition of the field assumes that the information is only intended for marketing or reporting purposes and there are no expectations of having an enrollment data against this. The enrollments, if done, will be linked against Course and Course run types.
* The field is not linked with course and course run types. At this moment, there are no checks to validate if a marketing type is allowed under a certain course type. These checks might be added in form of Django setting variable if required.
