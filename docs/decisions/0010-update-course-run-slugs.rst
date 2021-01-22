Course Run Keys in Course Run URL slugs
=======================================

Status
------

Accepted


Context
-------

The marketing site used to use the most recent (modulo some business logic) course run URL as the main URL for the whole course, redirecting all other course run URLs to the currently active course run URL. At this time, course run URLs were generated from the course title, while course URLs were generated from the course key and were not used at all on the marketing site.

Since November 2019, the marketing site uses course URLs, and all course run URLs redirect to the single course URL. When the switch to single course URLs was made, course URL slugs were updated to use the course title instead of the course key, since the course title was more human-readable and SEO-friendly. This has led to collisions between course URLs and course run URLs of courses with similar titles. 

Decision
--------

In order to decrease the likelihood of collisions, going forward, all course run URLs will be generated from a combination of the course title and the course run key, eg http://edx.org/course/my-course-course-v1edxcmct12020 instead of http://edx.org/course/my-course

Alternative Approaches Considered
---------------------------------
* Doing away with course run URL slugs entirely, since on the marketing site they just redirect to the course URL. We believe that these course run-level URL slugs are still in use by affiliate APIs so it is not possible to deprecate them entirely. Moreover since Drupal is not completely deprecated at this point we want to avoid accidentally sending users to the Drupal page for a course run.
* Use a random number at the end of the URL. This would avoid exposing an internal concept like course run keys, but course keys are already exposed in the LMS, which operates as a marketing site for many Open edX installations. Therefore we do not think there is any major security risk. Also, adding the course run key instead of a random number will be more similar to the current behavior, which will be friendlier to the Open edX community.
