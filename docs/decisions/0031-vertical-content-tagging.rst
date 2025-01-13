31. Vertical Content Tagging
=============================

Status
--------
Accepted (January 2025)

Context
---------
The Open edX `course-discovery` service currently lacks an efficient and flexible way to categorize courses by 
granular subject areas and verticals. The existing mechanisms (e.g., tags, Primary Subject) are limited, primarily 
partner-driven, and often misaligned with business-specific needs for taxonomy and categorization.

For example, a partner might categorize a Python course under the broad umbrella of programming languages, aligning with general usage.
However, the business may wish to categorize the same course under Data Science tools,
highlighting its primary focus on enabling learners to apply Python in Data Science.

It is important to note that here `partner` and `business` can represent distinct entities with different taxonomical needs. 
However, in some installations, the partner and business could represent the same entity, so this distinction may not always apply.

Objective
-----------
1. Introduce a structured approach to categorizing courses by  aligning them with specific business objectives
2. Enable more effective classification of courses based on verticals, ensuring that courses can be easily discovered and grouped according to strategic priorities, thereby improving overall discoverability.

Decision
----------
A new app will be created for the Vertical Content Tagging functionality.

The following models will be added to the app:

- **Vertical:** This model will store the list of verticals that can be associated with product types to define the portfolio of products 
  that fall under a specific vertical.
- **SubVertical:** This model stores sub-verticals, which can be associated with vertical filters. These sub-verticals allow further
  categorization and refinement within a vertical.
- **BaseVertical:** This abstract model will be used to associate vertical and sub-vertical filters across product types.
- **CourseVertical:** This model will extend BaseVertical to enable the assignment of vertical and sub-vertical filters to courses.

Currently, the intention is to support vertical tagging for courses only. In the future, 
the same functionality can be extended to other product types (e.g., Programs, Degrees, etc.).

A new user group will be created to grant access to the admin panel for assigning vertical and sub-vertical tags to courses.
However, this user group will not have the permission to manage vertical and sub-vertical filters, this functionality will be restricted to superusers only.

This new user group will be managed using a base settings configuration variable.

Alternatives Considered
-------------------------
- Add New Models in course_metadata: Keeping functionality within a single app, simplifying integration. 
  However, it risks app bloat, increased coupling, and reduced readability due to the large number of existing models.
- Create a Separate Plugin: Decouples vertical tagging for better scalability and modularity, with a plug-and-play structure.
  However, it requires significant initial effort, coordination, and limits Django ORM relationships with course-discovery models.
