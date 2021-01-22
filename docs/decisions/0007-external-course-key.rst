External Course Run Keys
==============================================

Status
------

Accepted (circa June 2019)


Terminology
-----------

Course number - Course team defined number of their Course. Becomes part of the
Course key. Looks like ``CS101``.

Course Run key - Combination of Course key and term (based on start date).
Looks like ``course-v1:edX+CS101+2T2019``. Immutable after creation.

External course key - External university identifier for a course run.

Registrar - django backend integration layer between edX and master's partners that allows partners to manage program enrollment for master's students

Old Publisher - Course Discovery frontend integrated with the Discovery IDA. On track to be deprecated in the future.

New Publisher - frontend-app-publisher repository, microfrontend written in React using Discovery APIs


Context
-------

Within the Registrar service, there are several endoints that require an edX
course run key in order to identify a specific course run. When the Registrar API
documentation was first released to partners, they expressed a desire to identify course
runs in a different way. They have systems that identify their courses by some internal
naming scheme, and they requested the ability to use those identifiers in the context of
Registrar so that they wouldn't have to convert between their own course run ids and
edX course run keys.

Example:

    There is an edX course, Introduction To Calculus.
    It has a course run with the key ``course-v1:exampleX+IntoToCalc+Fall2020``.

    In the partner's systems, their Introduction to Calculus Fall 2020 course is
    called ``MATH205-Fall20``", and they would like to use this identifier when interfacing with edX.

Decision
--------

We decided to add a field ``external_course_key`` to the CourseRun model that could
be set through Publisher, and allow partners using the Registrar API to identify
course runs with either an edx course run key or their own ``external_course_key``. This field should currently only be used on course runs that are a part of a master's program.

We came to the decision to enforce external course key uniquness at a program level, and
at any level below that. That means that no course can have two course runs with the same external course key, and  that no Curriculum can contain two courses with course runs that share an external course key, and that no program can contain two curricula that have courses that have course runs that share a course key. From here on, a program that would violate this will be refered to as being in a 'bad state'.

We enforce this by way of three new pre_save signal handlers, on CourseRun, CurriculumCourseMembership, and Curriculum.

Considerations
---------------

The decision was made to do the check as a pre_save hook on course_metadata models because we want to prevent any 'bad state' from being saved in the database, and we wanted to surface the fact that there was a 'bad state' to a user as quickly as possible. This adds some complexity to saving any of these models, specifically CourseRun, but we wrote the signal in such a way as to return immediately if the CourseRun has no ``external_course_key``. Because we expect only CourseRuns that are a part of a masters program to have this field, this addistional complexity will be immediately avoided for almost all CourseRuns.

To avoid adding a pre_save signal handler, we also considered raising an error only once a user made a Registrar API request for a program that was in a 'bad state'. We thought that it would be best to prevent the user from having to go back and forth between two different services (publisher and Registrar), and also that the user setting up programs in publisher may not even be the same user as the Registrar user.

We also considered doing the validation as a form validation on publisher, but decided against that because we wanted to also prevent changes from the django admin page from accidentally getting us into a 'bad state'.

At one point we considered storing the field entirely within Registrar. Registrar is currently the only place such a mapping is required, and it's also where we define and translate external program keys (another piece of master's-specific data). Unfortunately, due to the structure of Old Publisher, that was found to be unworkable without explicitly coupling old publisher to registar. The thought was that when a course was published, a call could be made to Registrar to check the uniqueness of the key and to update the mapping.

Potential Future Improvements
-----------------------------

Some good news is that the above approach is viable in new publisher. Once we have moved to exclusively using new publisher, it would be possible to move ``external_course_key`` and the related logic out of course discovery altogether and move it entirely into Registrar.