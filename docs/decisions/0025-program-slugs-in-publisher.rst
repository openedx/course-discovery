25. Program Slugs in Publisher
-------------------------------

Status
------

Accepted (July 2023)

Context
-------

SEO teams want to be able change the program slugs. These slugs are used in generating url for each type of programs.
These program slugs will be programmatically generated, just like courses.
In order to grant SEO teams the ability to update slugs for programs, we're going to display programs on Publisher due to it's ease of access control.
Only the slugs will be allowed to be updated for programs in Publisher

Decision
--------

* A new tab will be added on Publisher named "Programs/Degrees" in the header
* Upon clicking the tab, the user will be shown a list of programs with minimal info
* Each item in the list will take the user to it's detail page where an input field will be available for slugs and a save button
* Each user must have the permission before the program list and detail pages can be visited


Consequences
------------

* Programs will available on Publisher
* SEO teams will have the ability to edit program slugs, contributing in formatting marketing url
* Proper access control will ensure that only authorized users can view and modify programs
