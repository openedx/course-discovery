27. Restricted Course Runs
============================

Status
---------
Accepted (April 2024)


Context
---------
Course Discovery was created as a central data aggregator, aggregating information from Studio, LMS, and Ecommerce. Centralizing the catalog, Discovery offers various ways
for the information to be consumed by different consumers. While the consumers consume APIs to get the information, how the APIs work internally to provide the requested information differ greatly. The majority of the APIs work by hitting the database directly. Then, there are specific catalog and search APIs that first query ElasticSearch to search object IDs and then query the database to get the complete information against provided object IDs. The ElasticSearch
APIs are primarily used by B2B/Enterprise while non-ES APIs are used by frontend B2C and other Open edX services.

Because course discovery is an entry point and a source of truth for consumers, the different ways of fetching the information make it challenging to restrict the fetch selectively. It is not possible to define a product available for some consumers but hidden for others. To focus on CourseRun model, as course run is the entity that contains the course content consumed by the learners, there is a **hidden** boolean field that hides the course run from most APIs if set to True. However, that flag is never set in Discovery/Publisher. Instead, it is set from Studio (catalog_visibility) and then synced to Discovery.

Why is there a need to have course runs be available selectively? Some of the use-cases can be:

- Market special course runs at increased/decreased price in specific regions
- Create custom presentations and Small Private Online Course (SPOC) for Business-to-Business (B2B) customers without disrupting the Business-to-consumer (B2C) workflow (or vice versa)


Decision
----------
A new model, RestrictedCourseRun, will be added. The new model will:

- Have a one-to-one relation with CourseRun model
- Use DraftManager to have both draft and non-draft entries, linked with respective CourseRun entry
- Specify if the run should be restricted as a custom-b2b or custom-b2c course run.

This model will not override **hidden** field in any capacity. If a course run has been marked as hidden, the RestrictedCourseRun model will have no impact on the visibility of runs across APIs and objects.


Consequences
--------------

- In all the places where the course runs are fetched, whether getting course runs or aggregating based on course run information, this new model will need to be catered to i.e. ensure the restricted runs are not returned by default.
- Publisher would need to be updated to allow a course run to be marked as restricted.
- Unlike **hidden**, this new model will not be synced with Studio. The level of control will only apply to Discovery.
- The restricted runs will be pushed to e-commerce, as these runs are products. However, e-commerce will not have any information about the course run being restricted. This behavior will be consistent with how **hidden** course runs pushed to ecommerce do not specify whether they are hidden.
- The restricted course runs will not be exposed in APIs by default. However, a query param `include_restricted` will be added to APIs to provide a way to optionally fetch the restricted runs.


Alternatives Considered
-------------------------

- Keep using hidden field for selective filtering. However, using a Boolean to identify if the run should be visible on ES vs non-ES APIs could not have been achieved.
- Add a new field, **es_restricted**, to restrict runs to ES APIs. However, the new field could cause confusion with existing hidden field and could make code flow confusing.
