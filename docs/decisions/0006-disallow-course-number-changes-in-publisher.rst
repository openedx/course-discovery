Disallowing Course Number Changes in Publisher
==============================================

Status
------

Accepted


Terminology
-----------

Course team - The team of people from a partner Organization that work in
Publisher to create and manage Courses and Course Runs.

Course number - Course team defined number of their Course. Becomes part of the
Course key. Looks like CS101.

Course key - Combination of the Organization and the Course number.
Looks like edX+CS101

Course Run key - Combination of Course key and term (based on start date).
Looks like course-v1:edX+CS101+2T2019. Immutable after creation.


Context
-------

Upon Course Run creation, the Course key is used to create the Course Run
key. The Course Run key is then used as part of the URL in the LMS and in many
other places throughout the edX ecosystem.

In today's world, if a Course team wants to change their Course number, they
have to create a brand new Course with the number they want, despite the actual
course content being identical to the old Course. All runs created under the new
Course will have the new Course number reflected in their Course Run key, and
thus LMS URL. When this happens, Course teams will also move their old (or new)
Course Runs to point to the new (or old) Course so all of their Course Runs
continue to live together.

::

    Example:
        Current Course Number: 100x
        Current Course Run Key: course-v1:edX+100x+2T2019

        *New Course is created with Course Number 101x*

        New Course Number: 101x
        Newly created Course Run Key: course-v1:edX+101x+3T2019

        *PC repoints course-v1:edX+100x+2T2019 at the new Course edX+101x
        (creating the Course/Course Run key mismatch)*


It was previously thought that the Course key would always be a substring of the
Course Run key. However, with the above situation, it is possible to end up in
the case where the Course Run key and the Course key differ because the Course
Run has been remapped to a different Course. Since this assumption about Course
keys being a substring was already invalid, we wanted to investigate if we could
instead enable Course teams to change their Course numbers so we do not have to
create new Courses to have the desired result.


Decision
--------

At this time, we **disallow** modifying the Course number in both the Publisher app and the Publisher Microfrontend.
The Course number is used as a matching string between data sets in too many places.

But we **do allow** setting a separate Course field that controls what key new reruns use as a course key.
So if we want to rename a course key, we'll instead set this new key.
The course key will remain constant at the old value and continue to be able to be used for matching data sets.
But all new reruns in that course will use course run keys derived from this new field.

I believe this could (and should) change in the future to simply allow renaming a course key,
so I am documenting below the investigation I did including some of the changes that would need
to happen before allowing that.


Investigation
-------------

Upon inspection of the course-discovery code base as well as the Ecommerce,
Prospectus, and edx-platform repos, we determined that Course keys were not
being used in such a way that would require them to be immutable and decided to
look into allowing Course teams to freely alter their Course numbers. The
relevant `JIRA ticket can be found here.
<https://openedx.atlassian.net/browse/DISCO-1222?oldIssueView=true>`_ Although
switching Course numbers could be supported in this code base, the decision to
not allow modifying Course numbers was confirmed after speaking to many of the
stakeholders involved that could or do use Course keys. Below is documentation
of the different groups spoken to and the outcomes of those conversations. It
also includes some avenues that were not explored, but should be if we ever
decide to revisit this decision.


**Marketing** - uses course keys as part of their scripts or reporting. Open to
switching to UUIDs, but would need to make the switch. See thread here::

    Dillon Dumesnil
        Hi Marketing! I’ve been looking into the possibility of changing
        Course numbers (NOT Course Run keys) and was curious if anyone here
        currently uses them in any manually maintained lists or spreadsheets.
        If so, please let me know in a thread here so we can talk further.
        Thanks for your help!

    Ned Elwell
        Can you give an example of a course number? (our terminology isn't
        great in the course key, course number department)

    Dillon Dumesnil
        Totally understand. Something like this: Say you have the course key
        MichiganX+PUBLIB606x. The idea would be to allow them to change it to
        something like MichiganX+PUBLIB616x. The change being going from 606x
        to 616x

    Ned Elwell
        We don't have any manual sheets that key off of that, but it would
        break a LOT of reporting.
        Unless we're equipped to redo reporting on a value that's not related
        to course number/name, I can foresee problems with this.

    Dillon Dumesnil
        Would UUID be a potential fix for this issue?

    Ned Elwell
        I think the uuid fix would unblock any marketing reporting. it's just
        a major perspective shift. Otherwise, I see no issues as almost all
        other reporting is based on course run.

    [Paraphrased]
    Ned Elwell
        Would there be no historical record of the Course once the number
        changes?

    Dillon Dumesnil
        Well the row will continue to exist, but the course key on that row
        would be changed. We do have historical course tables in
        course_metadata that would see these changes, but as far as the actual
        table goes, that one row would just change course keys

**Data Engineering** - Brian Wilson did research into this and does not believe
there are any major concerns here. Should also encourage to always use UUIDs.
See thread here::

    Brian Wilson
        I’m assuming that the only things in SQL scripts that would actually
        break on a change to values in
        discovery_read_replica.course_metadata_course.key would be tables that
        are calculated incrementally and store and make use of this value.
        I’ve identified the following as incremental tables:
            * business_intelligence.user_session_summary
            * finance.recognized_certificate_revenue_total
            * business_intelligence.activity_engagement_user_daily
            * business_intelligence.identify
            * business_intelligence.deprecated_user_activity_engagement_eligible_users
            * business_intelligence.survey_history
            * business_intelligence.experiment_exposure
            * business_intelligence.utm_touch
            * business_intelligence.country_region_mapping
            * financial_reporting.intermediate_organization_courserun_previously_paid
        The main one I’m worried about is
        finance.recognized_certificate_revenue_total.  As we’ve seen before,
        it’s not the easiest set of queries to analyze.

        I should also note that this change would also affect
        production.d_course., not just course_metadata_course.

        finance.recognized_certificate_revenue_total, of course, depends on
        both.

        Okay, the latter table doesn’t actually persist a course-level
        identifier, only the course run key (as course_id).  And it looks like
        all the places that group by the catalog_course will switch to using
        the new values in case of any change. So I think things should be okay.

        One level where there may be issues is with a lag between
        course_metadata_course changing, and when the change shows up in
        production.d_course. That lag effect might be an issue. But I’m
        hoping it would be only temporary.

**Data Science** - Details for the impact to financial reporting if we change
course keys (as reported by Jacqueline Finkielsztein):

::

    We have some policy tables that hold exceptions for revenue share contract
    business logic. These policy tables come from google sheets that partner
    managers fill out in which they only provide us with course keys. We take
    these course keys and join them on other tables in our database. However,
    these are hardcoded keys on a google sheet. Therefore, when we join these
    policy tables to tables in our database, the course keys wouldn't match if
    we were to change them in our database tables. The tables are:
        financial_reporting.policy_organization_course_addition,
        financial_reporting.policy_organization_course_mapping,
        financial_reporting.policy_course_mapping,
        financial_reporting.policy_course_revshare,
        financial_reporting.policy_joint_course_revshare

I believe a potential fix for this issue is to get partner managers to start
using UUIDs and change the scripts to match on UUIDs instead of Course keys. On
that note, I think we should encourage Data Science to always use UUIDs if possible.

**Support** - I reached out if this change could cause any issues and heard no
response. This is to be expected since Support deals more with Learners who
would not really be affected by this change.

**Enterprise** - There is an issue with catalogs (stored in the LMS) and those being
updated since they use course keys now. Additionally, they construct URLs that
businesses use to enroll their users in courses that utilize course keys and
would break if course keys began changing. Solution is to move to UUIDs, but
will likely require a script to pull in all of the UUIDs based on the course
keys they have now and also ensuring there is backwards compatibility. Benefit
is they already use UUIDs for subjects so this wouldn’t be a huge change once
we are able to start using UUIDs for courses in their URLs.

**PCs** - Very open to the idea and didn’t identify any causes of concern.

**Revenue/edx-platform** - The StackedConfigurationModel inside of platform has a
field called org_course that uses course keys and can choose to include or
exclude course runs from different experiments based on that. Additionally, if
the course (being course run in this case) is passed in, it will create the
org_course based on the course run key and that may not always match with what
is in the database. The current models that utilize the StackedConfigurationModel
are DiscountRestrictionConfig, CourseDurationLimitConfig, and ContentTypeGatingConfig.
Possible solution to this problem could be to add in some course information in
the CourseOverview model in platform, but definitely going to need this
information in platform so we can have quick lookups

**edx-platform Repo** - Do a double check in edx-platform to look for anything using
org+course relationships

**Research data packages for Partners** - Brian Wilson looked into this and found we
only use Course Run keys as part of the research data packages. Specifically, we
pull the org from the course run and map the org to Partner, so there’s no
concept of course — just course_run and org.
