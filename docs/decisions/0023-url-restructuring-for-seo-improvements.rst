URL Restructuring for SEO Improvements (Subdirectory URL Slug Pattern)
======================================================================

Status
------
Accepted (June 2023)

Context
-------
The default breadcrumbing structure for Open Courses in Discovery currently generates course slugs based on the course title.
For example, the course slug for the course "Introduction to Linux" is ``introduction-to-linux``.
This slug is used to generate the course URL, which is ``{marketing_url_path}/course/introduction-to-linux``.
However, this URL structuring does not provide an SEO-friendly sitemap for Google indexing and fails to reflect the desired branding
tone and voice on the edx.org website. The aim is to improve search engine results pages (SERPs) and Google indexing by updating the URL slug pattern.

Decision
--------
To improve search engine results pages (SERPs) and Google indexing, the URL slug pattern for Open Courses in Discovery will be updated.
Instead of generating the slug solely from the course title, the new pattern will include the course title, primary subject,
and organization to create a more descriptive and SEO-friendly URL structure.

The source for generating the new URL slugs will be the course metadata. When a course run is submitted for review,
the system will automatically generate the subdirectory URL slug pattern using the ``course title``, ``primary subject``, and ``organization``.
This automated process will ensure that the new slugs are generated consistently and reflect the relevant course information. It is also possible to
add a slug in the subdirectory format and skip auto-generation depending upon SEO use-case.

To enable the subdirectory slug pattern for a course, a waffle switch named ``course_metadata.is_subdirectory_slug_format_enabled``
can be created through the Discovery admin. When the waffle switch is enabled, the system will generate the subdirectory URL slug pattern for the new courses and
having **default product source** such as OCM courses. It's important to note that the existing URL slug pattern will not be impacted
unless the ``course_metadata.is_subdirectory_slug_format_enabled`` switch is turned on. This ensures that the change does not disrupt the existing flow of slugs generation.

To update the URL slugs for existing courses and ensure consistency, ``migrate_course_slugs`` management command is provided to backfill the new subdirectory slug pattern.
This command can be executed to update the URLs of courses that were created prior to the implementation of the subdirectory slug pattern.


Consequences
------------
- By implementing the new subdirectory URL slug pattern, the SEO-friendliness of Open Courses' URL structure will be improved.
- The inclusion of primary subject and organization in the slug will provide more context and relevance to search engines.
- This change will not affect the existing URL slugs generation flow unless the ``course_metadata.is_subdirectory_slug_format_enabled switch`` is enabled.
- The backfilling command will allow for the systematic update of URLs for existing courses, ensuring consistency across the platform.
