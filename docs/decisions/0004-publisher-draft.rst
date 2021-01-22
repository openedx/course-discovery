Publisher Draft Model Decisions
===============================

Status
------

Accepted

Context
-------

As we develop a new frontend for Publisher, we need to support handling a Draft
mode of Courses and Course Runs (prior to OFAC approval) that will show
potential changes before a go-live action.

- We need to be able to stage, save, and present changes without modifying the
  live course.

- We want this content to be served from our REST endpoints alongside the
  Courses or Course Runs.

- We want to allow for any fields on the form pages to be draft-able even if
  they are not part of the course_run or course tables.

- We want to easily be able to tell which Courses or Course Runs have active
  drafts.

Terminology
-----------

Draft: Content that is being edited by a course team and has yet to be served live
Official: Non-draft content that is ready to be served live

Decision
--------

Add an additional row for each currently existing row within the tables that
need draft states. Creates will create a new "draft" row that will be the
version that is modified.

Add an additional column representing the differing state for the forms we need
history for. This will prevent us from increasing our table size, as well as
prevent us from having to modify our APIs outside of a specific query param
for unpublished data. The default manager will need to query against the
official states. Our schema will also be up to date via default migrations,
and any consumer of the API will be able to act directly on reading from either
official or draft rows.

Add a foreign key column that points between the draft version and the
official version. For performance reasons when needing to flip between them.

Add a query parameter to list endpoints that will return draft versions of
rows if available, and if not available, will return the official versions.
We can just re-use the editable=1 flag for that.

All form and API updates will be applied to the draft row. And only after a
successful review, the data of the draft row will be written to the official
row. (Although that "review" might be a no-op depending on business logic -
it may be skipped if the course run is already live for example.)

Benefits
--------

- Automatically keeps schema updates for draft versions in sync with official
  versions.

- Single point of access for differing between Draft and Official state at the
  ORM object manager level.

- Minimal to no API changes necessary to support the proposed design.

- Consumers of API can easily work against Draft or Official versions without
  breaking data contracts.

Consequences
------------

By choosing this solution over alternatives we miss out on a few things, as well
as open ourselves up to certain risks.

- Duplicating data across the tables we have will be a non trivial task,
  as well as doubling those tables' sizes.

- Indexes will need to be updated accordingly to accommodate the new access
  pattern we will be querying on.

- Base object manager classes will need to be overridden.

- Primary/Composite Primary keys will need to consider the draft/official state.

- Historical changes will not exist by default, it will be difficult to rollback
  and difficult to restore revisions.

- Relations for many to many, or one to many may not be the easiest to propagate
  to the live "official" versions (update vs drop/create).

Other Considered Approaches
===========================

JSON Column
-----------

Add an additional column to each table that needs a draft version. This column
would store the changes applied to the form, as well as pointers to the related
columns. This column would be applied and zero'd out on a successful "publish",
with the existence of a non-null value detecting that it is in a draft state.
Additional efforts would need to be made to apply schema changes to the stored
draft states.

Historical Table
----------------

We currently have a set of Historical Tables that keep a running history of
changes made and applied to a Course/Course Run. This table could be updated to
provide the draft state with the addition of a boolean to show which versions
are published, and the more recent entries since then being the draft states.
The schemas would be kept in sync, but the APIs would need to serve content from
the historical tables instead of the base tables.
