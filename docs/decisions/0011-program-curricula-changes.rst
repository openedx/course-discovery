Refactor the Curriculum model to relate to the Program model
============================================================

Status
======

Accepted (January 2019)

Context
=======

The structure of a Master's Degree program (as well as other programs,
e.g. MicroMasters) requires loosely that we support programs which may
consist of 0 or more Masters-level courses or 0 or more MicroMasters
programs as part of the program's curriculum.  The structure (or "curriculum")
of a program may change over time, and we should be able to track different
versions of curricula as they change.  Our discovery service should
be able to accurately model the relationship between courses, programs,
and Master's degrees and the curricula thereof.  Consider the following example.

Faber College offers a M.S. in Analytics.  Enrollees in this program may
specialize in three different tracks:

- Analytical Tools
- Business Analytics
- Computation Data Analytics

Each of these specializations may require enrollees to complete partially
overlapping, or completely distinct courses and MicroMasters programs to
fulfill the requirement of the specialized degree.

So, from this example, we see that a single degree may offer 1 or more
distinct specializations, and each specialization may require the completion
of different courses or MicroMasters (i.e. other, smaller programs).

Decision
========

To accurately model data as described above, the following changes to models
in the ``course_metadata`` application are proposed:

A Program may have multiple Curricula
-------------------------------------

We can use the Curriculum model to represent the fact that a Master's
Degree may contain one or more specializations through which an enrollee
may satisfy the requirements of a degree.  Furthermore, several of these
Curricula may be currently active, and several may be inactive.  For example,
consider extending the example above as follows:

- The "Analytical Tools" speciailization is retired.
- A new specialization, "Analytics in the Quantum Age" is introduced.

Our Curriculum models should be able to accurately represent this modification
to the MS Analytics Degree.  A Curriculum model for "Analytical Tools" should
capture the fact that the specialization is no longer active, and the date
on which it became inactive (after which, presumably, no new enrollee may
participate in that specialization).  A Curriculum model for the
"Analytics in the Quantum Age" should be created, with a field to indicate
that the curriculum/specialization is now active and the date on which it
became active.

A Degree may have changing deadlines and costs
----------------------------------------------

The amount of tuition charged, the dates of deadlines, etc. will naturally
change over the lifetime of a Master's Degree.  To support this, we will
update the models that capture this data to capture history (using
``django-simple-history``.  We will also track historical changes of ``Curricula``.

For now, there will be two ways to capture a Program's included courses
-----------------------------------------------------------------------

There should be one, and preferably only one way to model the relationship
between courses and programs.  After taking actions to implement the decisions
outlined above, there will be two ways: via program curricula, and via
the ``courses`` and ``excluded_course_runs`` fields of the ``Program`` model.
In the future, these fields should be eschewed, and their data migrated into the ``Curriculum``
and associated models.  The requirements to support this are beyond the scope of this document.

Decision that we will make later
--------------------------------

We don't currently need to track ideas like prerequisites, required, or
elective courses.


Actions
=======

Relating Curricula to Programs
------------------------------

The current course_metadata design relates Curricula to Degrees via a 1-1 field.
We will change Curricula to relate to Programs via a Foreign Key field, so
that a program may consist of zero or many curricula.  Note that specializations
are just one example of a use-case supported by relating Curricula to
Programs in this fashion.

Action 1
^^^^^^^^

Add ``program`` as a FK field in the ``Curriculum`` model, and point
that FK at the ``Program`` model.

Action 2
^^^^^^^^

There are existing ``Curriculum`` objects that are tied to existing
``Degree`` objects (roughly 10).  We will migrate existing curricula to
reference the program objects associated with the current degrees referenced by the curricula.

Action 3
^^^^^^^^

Remove the existing ``degree`` 1-1 field from the ``Curriculum`` model.

Action 4
^^^^^^^^

``DegreeProgramCurriculum`` and ``DegreeCourseCurriculum`` are the bridge
models that link ``Curriculum`` objects to ``Program`` and ``Course`` models,
respectively.  These names should be changed as follows:

- Rename ``DegreeProgramCurriculum`` to ``CurriculumProgramMembership``.
- Rename ``DegreeCourseCurriculum`` to ``CurriculumCourseMembership``.
