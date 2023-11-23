26. CSV Loader Update to Support Multiple Course Runs
=====================================================

Status
------
Accepted (November 2023).

Context
-------
Historically, the CSV loader was limited in its ability to handle multiple course runs for a single course.
The existing functionality only allowed for the creation of a course along with its corresponding course run or the
update of course and course run metadata for an already existing course. As a result, decisions regarding the placement
of external LOBs courses' course run/variant information were recorded in the ``AdditionalMetadata`` fields, and these courses were
designated for marketing purposes only and couldn't be purchased through the platform.

Objectives
----------
This enhancement aims to address two primary objectives:

1. Backpopulate dates and variants from additional metadata to CourseRun by either creating new runs or updating existing ones. This is a one-time process and applies only to external courses.
2. Allow active and future products to follow a consistent, multiple run format.

Decision
--------

To achieve the goals outlined above, the following criteria will determine when to create a new run:

- For courses with a provided "variant Id" (External LOBs courses such as ExecEd, Bootcamps, etc.), the ``CSVLoader`` will check if the incoming
    ``variant_id`` matches the ``variant_id`` of the active course run. If they are different, the system will then compare the schedule dates of the
    incoming run with those of the active run in Discovery. If the schedule dates differ, a new run will be created. In all cases,
    the dates and variants data will be either backpopulated to the existing run or used to create a new run.

- For cases where the variant ID is not provided, the ``CSVLoader`` will compare the schedule dates of the incoming run with the active run in Discovery.
    If there is a difference in schedule dates, a new run will be created. Otherwise, the existing run will be updated with the incoming dates and variants data from the CSV.

As we have decided to support multiple runs, the ingestion summary email will be updated to include details on whether
a new product or a new variant of an existing product is created during the ingestion process. This provides clearer insights into the changes
made during each run of the CSV loader.

Consequences
------------
Implementing this enhancement in the CSV loader will result in the following consequences:

1. Backpopulating dates and variants from additional metadata ensures accurate representation in ``CourseRun``.
2. The introduction of a multiple run format ensures uniformity for active and future products.
3. Variant ↔ CourseRun mapping will become unique, aligning with the distinct key for each new run.
