34. Default Verified Upgrade Deadline On End Date Change
=========================================================

Status
--------
Accepted (April 2025)

Context
---------
Once the Verified Upgrade Deadline (VUD) of an Open Course (OC) has been overridden, there is 
currently no way for it to automatically revert to the system's default setting (10 days before 
the course end date) when the end date is updated. This limitation leads to several challenges. 
For example, if a partner updates the end date of a course that previously had its VUD overridden, 
the deadline does not automatically adjust to reflect the new course timeline. As a result, 
Project Coordinators (PCs) must manually update the VUD, creating additional operational workload. 
Furthermore, if we are not informed of a course end date extension, the outdated VUD may prevent 
learners from upgrading, since it no longer aligns with the new course schedule.

Decision
----------
When a partner updates the end date of a course run, the Discovery service should automatically 
detect the change and reset the Verified Upgrade Deadline (VUD) override to ``null``.

Consequences
--------------
- **Verified Upgrade Deadlines Stay Aligned**: By nullifying the ``verified_deadline_override`` 
  when the course end date is updated, the system will default to using the standard logic 
  (10 days before course end date), keeping the upgrade window aligned with course timelines automatically.

- **Reduced Operational Overhead**: Partners and Project Coordinators (PCs) will no longer 
  need to manually adjust the VUD every time a course end date changes, reducing human error and 
  administrative overhead.

Alternatives Considered
-------------------------
An alternative approach considered was replacing the ``verified_deadline_override`` with a new field 
called ``verified_deadline_offset``. This offset would determine how many days before the course end 
date the Verified Upgrade Deadline (VUD) should be set. By default, it would follow the 
``PUBLISHER_UPGRADE_DEADLINE_DAYS`` setting (10 days), allowing the VUD to be calculated dynamically 
rather than entered manually.
However, this approach offers limited benefit when applied solely at the course run level. 
While it avoids hardcoding a specific date, it still requires manual entry of the offset for each course run. 
This does not substantially reduce operational workload. In practice, it only shifts the complexity from setting a 
date to setting an offset, without solving the underlying problem of inconsistency or repetitive configuration.
