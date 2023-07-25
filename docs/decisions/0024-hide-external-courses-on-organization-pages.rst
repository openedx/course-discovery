24. Hide External Courses on Organization Pages
------------------------------------------------------------------

Status
------

Accepted (*Temporary)

\* The current solution is specific to edX needs and it is expected for this solution to be moved out of discovery in the future.

Context
-------

Course Discovery is the source of truth for the products marketing information within Open edX. The course authors or editors would setup course and course runs
using Publisher MFE utilizing discovery APIs. Apart from providing on-site courses' marketing, there are capabilities in Discovery
that allow it to act like a Marketplace where courses external to platform can be marketed. The external courses utilize the existing course
and course run types structure in Discovery and are authored under existing organizations.

However, there is no capability to hide these external courses on an organization's about or marketing page. This becomes important in the cases where the participating organization does not want its brands getting mixed up. The organization requires control in deciding what external products should be displayed on the organization marketing page.


Decision
--------

In AdditionalMetadata model of course_metadata app, a new boolean field called **display_on_org_page** will be added. By default, this will be set to **True**. The field will signify if an external product's card will be displayed on the organization's about page. The newly added field will be source of truth to drive the card experience on organization pages.

Consequences
------------

* This field is primarily intended for use-case of edX marketing of external courses. There are no expectations of having a wider usage for this. This is the primary reason that this change is temporary and will be removed in near future.