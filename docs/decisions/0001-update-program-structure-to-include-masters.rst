1. Update Program Structure to Include Degrees
----------------------------------------------

Status
------

Accepted

Context
-------

The second phase of the Master's Theme requires us to support the persistence of metadata about different
Master's Degree programs in the course-discovery service.  The data is later surfaced on our marketing site in the
corresponding "product pages" for these degree programs.  We need this decision to make sure we can realize the
marketing requirements as fast as possible, and at the same time, make sure we can scale - both out to a variety of
Master's degree programs, but possibly to different types of degree's as well (e.g. Bachelor's).
See the OnlineMasters_ page for more information.

.. _OnlineMasters: https://openedx.atlassian.net/wiki/spaces/EDUCATOR/pages/762642493/Online+Masters

Decision
--------

For the Fall 2018 phase of the Master's project, we are utilizing a design of a Degree model extending
the existing Program model. All the parties talked to have given support for this solution.

The design
===========
The ``Degree`` model extends existing ``Program`` model. We'll add a new table with a foreign key to the existing
``Program`` table to store and define new Master's degrees.  We'll create a new ``ProgramType`` with the name "Masters"
to indicate that a degree is specifically a Master's degree.  The information required for the marketing product
page for a Master's degree will be stored in the union of the set of fields from ``Program`` and ``Degree``.  The
``Degree`` table will contain fields that are only relevant in the context of a degree (e.g. an application deadline
or application URL).

We will also create a ``Curriculum`` model which captures the relationship between a degree and the ``Courses``
and ``Programs`` that compose that degree's curriculum.

Why
===
#. With the extension model, we can leverage the existing software to index and serve Master's program data via
   the course-discovery API like any other program, since the program table will have a row for each Master's
   degree instance.  The ``Degree`` table will help us capture the unique requirements for Masters
   (mostly marketing product page requirements at this time).

#. We can utilize existing code that relies on the ``ProgramType`` model to make Master's degrees that are newly-created
   in the course discovery service to automatically populate a new Drupal page of the Master's content type.

#. Similarly, there is already code in place that uses ``ProgramType`` to control search facets.  We would
   like Master's to be a facet of course/program search.

#. The separation of marketing-centric data from curriculum-centric data will make management of degrees
   easier and less error-prone for users (e.g. the marketing team).

#. Having the relationship between degrees and Micromasters defined this way avoids the nested
   program to program relationship that can be super confusing.


All Choices we Considered
-------------------------

1. As part of Programs model: We can insert Master data into the existing program model. With this approach, we can satisfy the search and facets requirement, as well as affiliate api requirement pretty easily. However, existing program model fields do not map well to the content needs of Master program page design. The relationship between Masters and Micromasters programs would need new models. 

2. Extension model to existing Programs model: We create a new program extension model which has a foreign key pointing at a row within the Program model. The Master program page data, which cannot be captured by the existing Program model can be easily captured in the extension model. A Master program would have its data in both the Program model as well as the extension model. The relationship between Master and Micromasters are defined through extension model. This way, the have data integrity check for relationships on the DB level. However, we would need to adjust the django admin authoring process for Masters to include this additional model. It also requires in extra level of indirection to figure out how a Micromaster program is related to a Master

3. Create a new Degrees grouping: Create a brand new model called Degrees. This approach should lay the foundation for future like Bachelors. The new Degree model would help relationship between Masters and Courses on a level where we can generalize and scale. However, this approach require big work load to add net new functionality to all aspects of the discovery service, from search to affiliate API to new business logics

4. Create a content relationship data model which allows us to have a more generic way of grouping content together. This would involve creating a model which contains fields for storing two different content IDs and a field for describing the relationship between the content items, e.g. requires, contains, etc. A separate model could be created to store attributes associated with a particular piece of content (which could be used for storing metadata associated with the masters program in a generic way). The edx-milestones package does something along these lines and could possibly be used out of the box or to inspire the data model that would fit the particular content item relationship problem we are trying to solve here.

Requirements
------------

* Masters will have it's own landing page, just like Micromasters, 
  to show case various masters program, but with a new design
* Masters will have it's own design for Master about pages
* Search Facet will show Masters at the same level with Micromasters,
  XSeries and Professional Education, underneath the Programs group
* Each Master Program will have it's own search result card, as part of the Programs group
* Masters will be show cased in the same Programs drop down from edx.org top navigation
* Should be part of the affiliate API return
* Must be able to be consist of 1 to N Micromaster programs
* Must be able to be consist of 0 to N courses in addition to Micromaster programs
* Need to include electives (probably)
