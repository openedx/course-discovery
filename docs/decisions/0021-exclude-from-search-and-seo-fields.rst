21. Exclude From Search And SEO Fields
------------------------------------------------------------------

Status
------

In-Progress (February 2023)

Context
-------

It is important to easily toggle items from appearing in internal search results. Currently, there have been a lot of conditions that would need to be met for a particular course or program to be indexed in Algolia, but a simple interface for this functionality was needed. 
Additionally, for some of the About Pages, it was important to easily hide them from SEO (add noindex meta tag).

Decision
--------

Two fields have been added on Course and Program models:

- excluded_from_search
- excluded_from_seo

Both can be set to TRUE/FALSE in Django Admin for each course and program.

Moreover, since we have been adding additional fields through Contentful for some of the bootcamps and degrees, these fields can now be added in Contentful directly on the Boot Camp Page and Degree Detail Page content types. 

If an item (i.e. a bootcamp) has an entry in both Course-Discovery and Contentful:

- if the exclude_from_search value is set to True in Contentful, we will not index this Boot Camp in Algolia (overriding whatever value is in course-discovery)
- if the exclude_from_search value is set to False, we will still look at all other conditions that we normally look at in course-discovery to determine whether this item should be indexed

Consequences
------------
When this work has been merged and deployed:

- We can now easily toggle which objects should be indexed in Algolia
- We can now easily toggle which About Pages should be hidden from external search results (SEO)
