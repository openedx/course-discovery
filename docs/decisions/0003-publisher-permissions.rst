Publisher Roles and Permissions
===============================

Status
------

Accepted

Context
-------

As we develop a new frontend for Publisher, we wanted to rethink and simplify
the current roles system.

- We need some way to distinguish which users are allowed to perform sensitive
  actions like publish new courses.

- We want to use the same accounts as the rest of the Open edX ecosystem.

- We want to allow as much of a self-service experience for course teams as
  possible. So very few checkpoints relying on staff users.

- But we do want to allow for staff users to provide some legal oversight
  and to assist with the publisher experience.

- We do not want to mix studio and publisher permissions, since those are
  often handled by different people on the partner side.

Decision
--------

Normal staff users will have access to everything by default, but nothing
will require their participation.

Legal staff users will have an extra bit of control to toggle some settings
like whether a course is OFAC restricted, for example. There may be some
checkpoints waiting on them before a course team can publish. These users will
be marked by belonging to a particular group. That group should be configurable.

Membership in an org group will be managed by staff users. But once you're in
that group, you can create courses and course runs for that org. Once you do,
you are the first and only editor of that course. Any current editor can add
any other editor from that same org. Or can remove any editor.

Consequences
------------

Removing a user from an org group should remove editor privileges to all
courses in that org. Likewise deleting a user.

If a course has no editors left, rather than orphaning that course, anyone
in that org should be able to edit it. Once an editor is added back to it,
normal rules apply again.

But mostly, this setup will be able to reuse current organization and permission
models. We already have OrganizationExtension that connects organizations to
groups, which users can belong to.

And JWT tokens already tell us who is staff.
