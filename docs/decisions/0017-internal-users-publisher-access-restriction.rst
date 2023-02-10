17. Internal Users Access Restriction for Publisher consumed APIs
------------------------------------------------------------------

Status
------

Accepted (November 2022)

Context
-------

Any internal or staff user visiting the Publisher Micro Frontend (MFE) has capability to view, create, or edit the course, course run, and staff information. Publisher being an MFE gets all the information from Catalog service, Discovery.
The APIs used by Publisher to view, create, and edit the course, course run, and staff information have certain permissions in place. However, those permissions only apply to **Course Editors**. The editors are not staff users.
The administrator checks are loose compared to course editor permissions. By default, any internal user has permission for data modifications through APIs.

Why is this important? Publisher is an interface to author marketing information for courses. Aside from the marketing-only information, there are sensitive and risk-prone data pieces such as price, schedule dates, etc. Any unintentional edits to these fields by an internal user
carry huge implications for marketing and financial data of the course's organization and for the platform as a whole. Therefore, it is essential to have access checks for internal users on APIs used by Publisher.

Decision
--------

The access checks will be implemented using role based authorization. With the help of `edx-rbac`_, the following actions will be performed:

* A new feature-based role, PUBLISHER_EDITOR, will be added in Discovery. There will not be any system-wide role because the access restrictions are focused only for Discovery and Publisher.
* The role will be assigned to internal users within Discovery. The role assignment will be accessible via an exposed endpoint. The role assignment will contain other information, such as the assignment date, the reason for giving access, access history, etc.
* Publisher will make an additional API call to get the users' assigned role. Based upon the assignment, the behavior of publisher will change.

 .. _edx-rbac: https://github.com/openedx/edx-rbac

Consequences
------------

* This change will not impact Project Coordinators, Course Editors, and Legal users. They will be provided appropriate access upon the implementation.
* The staff or internal users will have read-only access by default. To be able to create or edit course and course runs, they would need the appropriate role.
* This behavior will be toggleable via settings. This will enable open edX community to keep using Discovery and Publisher the way they are using if they do not require role-based authorization.

Alternates Considered
-----------------------

One option was to create a Django User group, assign the users the new group, and make decisions based on the group. This approach, however, falls short in adding metadata of the role assignment.
