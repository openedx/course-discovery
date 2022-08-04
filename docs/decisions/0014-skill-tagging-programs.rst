Skill Tagging of Programs
=========================================================

Status
------

Accepted

Context
-------
Programs in course-discovery do not have a direct way to getting tagged with Taxonomy skills. Each program has a set
of associated courses. Most of the courses have a list of skills attached to them. The course skills information is present in `taxonomy-connector models`_. By aggregating the skills linked to the courses, the skills of a program can be formulated.
However, with the import of external programs (degrees) that
do not have associated courses in discovery, the course skills aggregation mechanism can not be utilized for listing program skills.
With no relevant skills available, the external programs can not be used effectively in Algolia search.

.. _taxonomy-connector models: https://github.com/openedx/taxonomy-connector/blob/09bc066ae66ed4bea73f70811dedc0853e2fe077/taxonomy/models.py#L102

Decision
--------
A new model called ProgramSkill will be added in `taxonomy-connector`_, using the same design as CourseSkill model.
This model will be responsible for containing the information of skills associated with a Program. The tagging process
for new programs will work as follows:

1. In discovery, when a program publishes for the first time or the contents of "overview" field change, emit a signal indicating the program skills must be updated.
2. In taxonomy-connector, add a `signal handler`_ that is listening to the event published by course-discovery.
3. Upon receiving the signal, get Program information from Discovery and send "overview" data field to EMSI using EMSI API.
4. With a successful EMSI API call, create or update the skill information for Program in taxonomy app.

The above mentioned process can work for any type of Program (with or without associated courses). To back-populate the Programs
that are already present in the Catalog, a management command that is performing the above steps in a similar capacity would be needed.

.. _taxonomy-connector: https://github.com/openedx/taxonomy-connector/blob/09bc066ae66ed4bea73f70811dedc0853e2fe077/taxonomy/models.py
.. _signal handler: https://github.com/openedx/taxonomy-connector/tree/09bc066ae66ed4bea73f70811dedc0853e2fe077/taxonomy/signals

Consequences
------------

* The program skill information would need to be indexed in Algolia.
* For the cases where the associated skill(s) for a program are not correct or do not meet the quality, there should be a mechanism to remove or blacklist the unwanted skills for a Program.
* If the program has associated courses, the course skills aggregation will be given preference for the determination of Program skills.
