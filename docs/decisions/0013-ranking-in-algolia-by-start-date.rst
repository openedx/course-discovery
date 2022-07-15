Ranking in Algolia by Start Date
================================

Status
------

Accepted (07/13/2022)

Context
-------

While most Executive Education courses on edX are currently running, some have future start dates. Not all future
courses are created equal, however. Some are relatively far off - we're defining this as more than 45 days in the
future - while others will start soon.

When a course is starting more than 45 days in the future, we need a way to de-emphasize it in search.

Decision
--------

Algolia provides a custom ranking feature. We will index a boolean field (e.g. ``far_off_start_date``) that returns
``True`` if the course starts over 45 days in the future. This field will be set as a descending custom ranking
attribute in Algolia, so that these courses can be de-prioritized.

We can create a replica index in order to test these changes without affecting the search results on production.

Consequences
------------

* This data will only be available in Algolia. However, there are no plans to use it elsewhere.
* Executive Education courses have a different source of truth for start date than OCM courses
  (``additional_metadata.start_date`` vs. ``advertised_course_run.start``, respectively). We will have to consider this
  when implementing.

References
----------

* `Custom Ranking in Algolia <https://www.algolia.com/doc/guides/managing-results/must-do/custom-ranking/#custom-ranking>`_
* `Understanding Replicas <https://www.algolia.com/doc/guides/managing-results/refine-results/sorting/in-depth/replicas/>`_
