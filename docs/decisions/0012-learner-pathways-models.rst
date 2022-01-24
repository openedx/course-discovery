Create new models in course-discovery for Learner Pathways
==========================================================

Status
======

Accepted (October 2021)

Context
=======

The structure of a Learner Pathway allows for programs, courses, and course
blocks to be arranged in a semi-sequential collection of steps to be completed
by a learner in pursuit of a specific goal for which the pathway has been
designed. e.g. Maximizing growth in a specific skill.

Unlike programs or curricula, Learner Pathways are not primarily concerned
with price bundling or credentials. Instead, Learner Pathways are meant to be
more flexible, not coupling too closely with their own content. In fact, it is
expected that Learner Pathways be periodically updated as newer, more relevant
content becomes available.

Learner Pathways are structured both vertically and horizontally. Their vertical
structure consists of 1 or more steps to be completed. It is implied that the
steps should be completed in order, but this is not strictly enforced. However,
we may decide later to enforce requirements (potentially leveraging the edX
milestone service). A Learner Pathway's horizontal structure consists of 1 or
more content options (electives) presented for a given step. For steps like,
Learners much complete a minimum number of electives. e.g. Complete 2 of the
following 3 courses. By structuring Learner Pathways in this way, we accomplish
the creation of a hierarchy of content knowledge that the Learner Pathway
builds, while at the same time, affording learners some freedom of choice.

Decision
========

To accurately model data as described above, a new application ``learner_pathway``
will be created with its own API and models as described here:

The LearnerPathway model
------------------------

The LearnerPathway model contains all the necessary data and sub-models required
to fully describe a Learner Pathway. In addition to the Learner Pathway's metadata
(title, id, etc.), this model also contains an ordered set of LearnerPathwayStep
objects. These objects describe the vertical structure of the Learner Pathway that
learners must traverse towards completion.

This model also implements methods to be used to return data aggregated from the
pathway's composite steps and nodes. e.g. The pathway can return an estimated time
of completion by iterating through each step and calling each node's
``get_estimated_time()`` method and aggregating the data.

The LearnerPathwayStep model
----------------------------

The LearnerPathwayStep model represents a step in the vertical structure of a
pathway. Each step contains 1 or more nodes to be completed before moving on to
the next step. If multiple nodes exist within a step, the step will use its
``minimum_to_complete`` data field to indicate how many nodes must be completed.

Each step has a 1-1 relationship with a pathway. A step in one pathway may be
identical in form to a step in another pathway, but each pathway maintains its own
separate set of steps and nodes.

Each step implements a method to calculate the minimum and maximum estimated time
to completion of itself by iterating through each node in the step and calling its
``get_estimated_time()`` method, and aggregating the minimum and maximum values.

The LearnerPathwayNode model
----------------------------

The LearnerPathwayNode model is an abstract model that represents a piece of content.
This content will typically be a course, but may also be a program. In some cases,
nodes may be a block of course content, such as a video.

Using an abstract model in this way allows LearnerPathwayStep objects to be agnostic
of the specific types of content they contain.

Node objects declare abstract methods to return their content's estimated time to
completion, and the effort level involved. This data can be aggregated for each step,
and in turn, for the pathway in its entirety.

The LearnerPathwayCourse model
------------------------------

The LearnerPathwayCourse model represents a single course. Each LearnerPathwayCourse
node relates to a specific Course. Through this relationship, the node can access
information about the course, providing it to the pathway to which the node belongs.
This information includes, but is not limited to: title, description, subjects, and
prerequisites. Also, through the Course's related CourseRun list, we have access
to the estimated time to completion, estimated effort, etc.

The LearnerPathwayProgram model
-------------------------------

The LearnerPathwayProgram model represents a single program. This model is very
similar to the LearnerPathwayCourse model, except that it relates to a Program
object, rather than to a Course object. Through this relationship, the node can access
information about the program, providing it to the pathway to which the node belongs.
This information includes, but is not limited to: title, subtitle, marketing hook,
overview, total hours of effort, weeks to complete, etc.

In addition to metadata about the program itself, we can use the Program object's
related Course list to retrieve metadata about any of the courses belonging to the
program.

The LearnerPathwayBlock model
-----------------------------

The LearnerPathwayBlock model represents a single block of content from a course.
Each model object relates to a specific Course, and to a specific block within that
course (identified by the block ID). This allows pathway curators the flexibility
to prescribe certain content without requiring the entire course.

The Learner Pathway API
-------------------

The Learner Pathway API is made available from ``course-discovery`` and can be used
by an MFE to retrieve and store Learner Pathways.

Learner Pathways are loosely coupled to learners and their progress
------------------------------------------------------------------

Learner Pathways do not relate directly to learners, as doing so would needlessly
complicate their structure and maintenance. Instead, we plan to add a new model
to the LMS to provide the status of a learner's progress through a pathway. This
progress model can be related to the learner, and retrieved by an MFE through an
API method. By combining the progress model with a pathway, we can easily
determine what pathway content the learner has completed vs. what remains.

Learner Pathways are loosely coupled to enterprises
---------------------------------------------------

Though this feature is developed by an Enterprise team, it is not necessarily
an Enterprise exclusive feature. The design is intended to allow pathways to be
used by both B2B and B2C.

Learner Pathways are capable of being scoped. Most will be available to all learners,
but some may be scoped to one or more enterprises. Potentially, pathways could also
be scoped to a specific set of learners.

Why not reuse Programs?
-----------------------

Initially, our Program model was chosen as a potential framework on which we could
build Learner Pathways. After several discussions with the Programs team, we
decided against that because:
1. Programs was built primarily for price bundling, and as such is closely tied to
CourseEntitlements.
2. Programs can only contain courses, and we wanted more flexibility. e.g. multiple
programs in a pathway, course blocks.
3. We didn't want to break Programs, or at least to not further complicate it.
4. It's better to have two things doing their own thing, rather than one thing
trying to do everything.

Decision that we will make later
--------------------------------

We don't currently enforce a rigid set of requirements or prerequisites. Pathways
will initially be built manually, with the expectation that the curators will
choose the sequence of content based on their knowledge of the course content.

We may later implement algorithms to automatically generate pathways. To do so
may require that we use or create tools to help enforce requirements. The edX
``milestones`` service may be useful for this purpose.

