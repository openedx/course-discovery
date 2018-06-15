1. Update Program Structure to Include Masters
----------------------------------

Status
------

Accepted

Context
-------

Masters project need this decision to make sure we can realize the marketing requirements
as fast as possible, and at the same time, make sure we can scale. 
We should also be aware that it's impact to existing program and course structure so,
whatever decision we make, it should be backward compatible and minimize risks to existing offerings.



.. _Online Masters: https://openedx.atlassian.net/wiki/spaces/EDUCATOR/pages/762642493/Online+Masters


Decision
--------

For the Fall 2018 phase of the Master project, we are going with the extension model design.
All the parties talked to have given support for this solution.

The design
===========
Extension model to existing Programs model. Basically, add a new table with a foreign key to the existing
Programs table to store and define the Masters. 

Why
===
1. With the extension model, we can leverage the existing software to index and serve Master program like 
any other programs since program table will have a row for each Master. It helps us capture the unique requirements for Masters. 

2. When the relationship between Master and Micromasters
are defined through the extension model, it avoided the nested program to program relationship that can
be super confusing.

3. Another benefit with this choice is, if we eventually want to have a whole new Degrees
grouping. We can easily turn the extension model into Degrees. The work there will not be prohibitively large.

4. We don't believe the generalized content relationship model is needed at the moment for we don't yet have all clear and complete requirements for how Masters would relate to other programs and courses.

Choices
-------

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
* Need to include electives?
