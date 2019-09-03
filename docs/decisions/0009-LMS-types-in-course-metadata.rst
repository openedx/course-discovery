LMS Course Types in Course Metadata
===================================

Status
------

Accepted


Terminology
-----------

Product - A Seat or Entitlement that is offered in the E-Commerce service.

Mode - The LMS Course Run mode available. In the edX ecosystem, these would
be Audit, Verified, Professional, No ID Professional, Credit, Masters, and
Honor.


Context
-------

Course Metadata keeps its own record of two types of E-Commerce Products:
Seats for Course Runs and Entitlements for Courses.

In the past, Course Discovery did not have reliable knowledge about the
connection between E-Commerce and the LMS in terms of E-Commerce Products and
LMS Course Run Modes. In order to determine anything about the LMS Modes,
Course Discovery would have to look at the Seats that exist for a particular
Course Run in Course Metadata and infer from there. This was possible when
Seats and Entitlements had a one-to-one mapping to the current LMS Modes that
existed.

However, with the inclusion of Masters, we saw a divergence between Seats in
Course Metadata and the products in E-Commerce. Masters is a LMS Course Run
Mode, but has no E-Commerce products associated with it, breaking our earlier
assumption of Seats being used to inform on LMS and E-Commerce. Additionally,
the E-Commerce Data Loader (part of the refresh_course_metadata management job
in Course Discovery) syncs Course Metadata with E-Commerce, so when the
data loader sees Seats in Course Metadata that have no E-Commerce counterpart,
it deletes the Seats out of Course Metadata. This situation has now led to
Course Runs in Course Metadata that have no Seats so there is no good way of
determining the LMS Mode.

The problem we are trying to solve is this then: how to cleanly define the
combinations of LMS Modes and E-Commerce Products that exist for our various
Course / Course Run use cases. The goal is for this model to also be easily
expanded as new Products or Modes are added. Additionally, we want Course
Discovery to remain a source of truth for this information so we want to also
be able to keep track of metadata associated with Products or Modes.


Decision
--------

In order to accommodate both E-Commerce Products and LMS Modes in Course
Discovery, we have decided to add in four new models.

The first is the Mode model, the LMS Mode equivalent to the SeatType
model. The idea behind this is to allow SeatType to be the connection of the
types in the E-Commerce service and Mode to be the connection to the LMS
Modes. This model will also be able to keep track of a number of metadata
fields about the different Modes (such as if the Mode requires ID
verification or who the payee is for the track).

The second model is the Track model. This model will contain fields for the
Mode selection as well as the Product (Seat) associated with that selection.
Two examples of Tracks are::

    mode: Verified, seat_type: Verified (indicates Verified Seat in E-Commerce)
    mode: Masters, seat_type: None (indicates there is no E-Commerce Product)

The third model is CourseRunType, the connector between a Course Run and its
Tracks. CourseRunType will also be able to contain run-specific information,
such as if this run has a marketing site or not.
An example of CourseRunType::

    One row in the CourseRunType could have the label "Verified and Audit" and
    the Audit and Verified Tracks. This would mean any Course Runs pointing at
    this row would have Verified and Audit Tracks in the LMS and Verified and
    Audit Seats in E-Commerce.

    A similar, but different situation, would be the CourseRunType row for
    "Masters, Verified, and Audit". Any Course Runs that are connected to this
    row will have Masters, Verified, and Audit Tracks. In this case, the course
    runs will have all three Modes, but will continue to only have Verified and
    Audit Seats in E-Commerce since Masters does not have any E-Commerce
    Products associated with it.

The last model is the CourseType model, the connector between the Course, its
Products (Entitlements), and the allowed CourseRunTypes for its Course Runs.
The CourseType will contain information that will reduce the possible
selections for its Course Runs and this will also determine if an Entitlement
is needed. Example::

    CourseType could have the row "Masters, Verified, and Audit". This would
    indicate that any of the Course Runs inside this Course could have any
    allowed permutation in CourseRunType that makes sense with this Course
    selection. Examples of possible CourseRunTypes are:
        * "Masters, Verified, and Audit"
        * "Verified and Audit"
        * "Audit only"
        * "Masters only"
    This selection would also mean a Verified Entitlement should be made in
    E-Commerce since it is possible for some of its Course Runs to be Verified.

It is believed this new format will be more resilient and explicit moving
forward in Course Discovery. It will allow for clear specification at both the
Course and Course Run levels for what type it is and what Products are
associated with that selection.

Entity Relationship Diagram:

.. image:: ../_static/course_discovery_types.png


Alternative Approaches Considered
---------------------------------

**No major data model changes (continue to infer LMS Tracks based on Products
in Course Metadata)** - One option would be to just not change the current
infrastructure to accommodate for LMS Tracks inside of Course Discovery. This
option would still require making changes to work for the Masters case, but
could be done with a smaller overhaul. This option was rejected as it was
decided there would be current and future benefit in having a clear connection
from Course Discovery to both E-Commerce and LMS. One such benefit is being
able to make the SeatType model the source of truth for what types of Products
we offer, whereas currently Masters exists as a SeatType despite never
existing inside of E-Commerce.

**Allowing selection of all Tracks** - In the examples above, the option for
CourseType and CourseRunType always followed the form of a label ("Verified
and Audit"). Another option we considered was allowing the user to simply
select all of the types they wanted in their Course or Course Run. For
example, with the "Verified and Audit" case, the user would select a
"Verified" option and an "Audit" option. This path was decided against due to
the complex nature of our Course and Course Run types. For example, we do not
allow a single Course to have the Professional type and
any other type (Professional must exist on its own). Another example is how we
will have a type that looks the same, but differs in a few ways. This
situation happens when we have a standard Audit Course Run and a Small Private
Online Course (SPOC). In both cases, the LMS Track is Audit, but the SPOC has
no E-Commerce Products and no marketing page whereas the the standard Audit
Course has both. For these reasons, it was decided that providing only labels
to the user will allow us to encapsulate the underlying logic and abstract
away the implementation details of concepts such as "Audit".
