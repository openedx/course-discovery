Introduction
============

The distribution of edX's data has grown over time. Any given feature on edx.org may need information from Studio, the LMS, the Ecommerce service, and/or the Drupal marketing site. Discovery is a data aggregator whose job is to collect, consolidate, and provide access to information from these services.

Discovery allows services internal to an Open edX installation to consume a consolidated source of metadata for presentation to users. For example, search on edx.org is provided by Discovery. Discovery also allows external parties to access data about content in an Open edX installation from a single, central location in a secure way that doesn't impact performance of said installation.

Courses and Course Runs
-----------------------

One of Discovery's distinguishing features is the way it formalizes the relationship between courses and course runs. For example, ``course-v1:foo+bar+fall`` and ``course-v1:foo+bar+spring`` identify fall and spring runs of the same course, ``foo+bar``. You can think of courses as collections of course runs. Discovery infers this relationship when collecting data from other services. This hierarchy is the foundation for catalogs and programs, two additional structures provided by Discovery.

Catalogs
--------

Catalogs are dynamic groups of courses. A catalog is defined with an Elasticsearch query. Catalogs are used to give external parties scoped views of edX content. They are also used to implement coupons on the Ecommerce service. For example, a coupon providing a 25% discount on courses from a specific organization would be tied to a catalog identifying those courses.

Programs
--------

Programs are fixed collections of courses whose completion results in the awarding of a credential. Discovery only stores program metadata. For example, Discovery is responsible for keeping track of which courses belong to a program. Other program-related features such as calculating completion and awarding credentials are the responsibilities of separate systems.

Data Loading
------------

Data about courses and course runs is collected from Studio, the LMS, the Ecommerce service, and, for edx.org, the Drupal marketing site. The data loading pipeline used to collect this data can be run with a management command called ``refresh_course_metadata``. edX runs this command several times a day using a Jenkins job. It can be manually run to populate a local environment with data. The data loading framework is designed to make adding additional systems easy.

Search
------

Discovery uses Elasticsearch to index data about courses, course runs, and programs. Indexing can be run at any time with a management command called ``update_index``. The Discovery API can be used to run search queries against the Elasticsearch index.

API
---

Access to information about courses, course runs, catalogs, programs, and more is provided by a REST API. For more about the API, use your browser to visit ``/api-docs`` hosted by a running Discovery instance.


Creating/Accessing the Discovery Service Super Admin
---
To access the super admin Django panel, follow the below steps.
1. Login to your openedx instance
2. sudo -H -u discovery bash
3. source ~/discovery_env
4. cd ~/discovery
5. python ./manage.py createsuperuser --username=USERNAME --email=username@example.com

Now you can access Discovery Django admin at http://yourdomain:18381/admin
login with the username and password created above.

