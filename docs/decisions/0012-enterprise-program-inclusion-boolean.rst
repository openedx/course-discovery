Adding Subscription Inclusion toggle to Publisher/Studio
============================================================

Status
======

In progress

Context
=======

Our edX catalog has many subsets, which add distinctions onto which are allowed to be enrolled 
in by our enterprise customers. 

- Enterprise Catalog: The entirety of the enrollable edX courses excluding Stanford and UPenn
- Subscription Catalog: A subset of the Enterprise Catalog including self-paced courses from participating partners. Sometimes referred to as OC Catalog 
- B2B Subscription Catalog: A subset of the Subscription Catalog excluding Harvard

Currently, our system for subscription tagging is brittle and relies on communication between 
two individuals, which leaves us open to a risk multiple issues including:

- Data Integrity: We copy or pull data from 4 different platforms (Discovery/Publisher, Explore Catalog, Google Sheet, and Django/LMS)
- Course Key Tagging: Recently published courses are excluded as the process is manual and is therefore time-gapped
- Source of Truth/SME Ownership: Current process is owned by one (overworked) member of enterprise and not owners of partner relationships 

The full process must be repeated on a weekly basis and whenever a new partner is included 
in subscriptions to ensure that the catalog accurately reflects courses that should be included
in the catalog. Therefore, when either of these members are busy or on PTO, we do not have 
the most updated catalog for our customers. 

Decision
========

This proposal will change this process so that subscription tagging is done at the Publisher
level. This will enable us to remove the necessity of a manual process by using a binary flag
to tag a subscription course within the metadata. In the future, querying for subscription 
courses through a course field will allow us to refine a particular catalog if we choose to
pursue an opportunity like specialized (sub) subscription catalogs. Also, moving away from 
Google Sheets gives various stakeholders visibility into which partners participate in the 
catalog. This will pave the way for work that can be done in the future to more fully 
integrate SFDC with Publisher and truly automate this process. 

The types of Partner participation in subscriptions are as follows: 

- Traditional: All courses/programs in both the OCE and B2B catalog 
    Excludes MicroMasters, instructor-led courses, and any specific courses the org wants excluded
- Not Participating: None of the partners courses will be available in the subs catalog

The tagging system will be structured by inheritance from both the organization level and
the course level. If the organization’s inclusion is set to false, none of the courses or 
programs from this organization will be included in the catalog. If the org flag is set to true, 
partners do have the option of opting out of courses, which will be manually set for every course
they wish to exclude. For inclusion flags for both program and course run, this is a calculated 
field, not manually set like organization and course. For programs, if every course in the program
is included in that catalog, we will set the flag to true. Course runs are set to true only if
the parent course is set to true and the course run is not instructor-led. 

There are some existing organizations with unique customizations. Because of the value-add of 
these partner’s courses, we have allowed places like Harvard to exclude their courses from
the B2B catalog. However, these are the exception and not the rule, and we intend not to 
generally allow or advertise these customization options for future partners. 
