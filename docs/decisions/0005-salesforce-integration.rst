Publisher Salesforce Cases/Comments Integration
===============================================

Status
------

Accepted


Terminology
-----------

Comment: An exchange between an external user and an edX employee

Record: A representation of a model (Course/Course Run) within Salesforce

Old Publisher: Course Discovery frontend integrated with the Discovery IDA

New Publisher: frontend-app-publisher repository, microfrontend written in React using Discovery APIs

Context
-------

Old Publisher contained a section of comments that allowed our partners and course teams
to communicate with our internal users for data changes, and other general requests. This
feature is still required for New Publisher, and we can rely on Salesforce to handle
workflows and creation of actionable statuses/emails, instead of writing those ourselves.
However, this means that the data needs to be available inside of Salesforce for us to
interact with.

- We need to be able to create Accounts, Users, Courses, Course Runs, Cases inside of
  Salesforce

- We want our users to not need Salesforce accounts or access

- We want a hierarchy of Accounts linked to Courses linked to Course Runs linked to
  Cases linked to Users

- We want all of our historical comments from Publisher available in Salesforce

- We want to be able to access the Cases for a Course or Course Run via a REST API


Decision
--------

This feature will remain optional to accomodate Open edX users.

Create an optional configuration within Course Discovery admin to accept
Salesforce credentials, where if it is set, the feature is enabled.

Create a RESTful endpoint within Course Discovery to accept Course/Course Run
IDs to proxy GET requests out to Salesforce for Case data.

Create a RESTful endpoint within Course Discovery to proxy write requests
out to Salesforce for creation of Cases.

Add Django ORM save hooks to write out to Salesforce if and only if the
configuration exists in order to migrate data over to Salesforce in an
ad-hoc way so anything that isn't needed isn't bulk loaded.

Create a UI that surfaces Course level Cases with a string of comments internal
to that Case, and allows users to post additional comments, as well as read
comments belonging to that Course.

Bulk load all historical Publisher comments by creating the proper relationships
and so that our users don't see any messages dropped.

Benefits
--------

- Moves Workflow and e-mail requirements outside of Engineering, as well as enables
  additional customization down the road that will not require Course Discovery
  changes.

- Allows users to interact with our internal systems, without needing direct access.

- Ad-hoc creates ensures there are no dangling cases, and bulk will allow a seamless
  transition to begin using the system.

Consequences
------------

- Locks us into an external technology.

- Impacts Open Source community if they want this feature, by requiring external dependencies.
