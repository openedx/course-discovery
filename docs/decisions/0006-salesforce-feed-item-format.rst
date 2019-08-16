Publisher Salesforce Feed Item Format
=====================================

Status
------

Accepted


Terminology
-----------

Comment: An single post between an external user and an edX employee

Case: For example, each course in Publisher has a single Case that holds all the Comments for that course.

FeedItem: A Salesforce object to wrap the actual Comments

Context
-------

Salesforce Cases have a Chatter Feed that displays actions that occur within a Case. In order
to share information from Publisher to Salesforce, we need a User, a Course Run Key,and a
Comment. We cannot create Users because they are tied to Salesforce licenses, but even if we create
them just-in-time to associate with a comment, then disable their active status, our Salesforce
team does not think creating > 400 "dead" users is reasonable to leave in our system. Additionally,
SObjects (a Salesforce type), cannot be customized, so we cannot leave any additional information
(email, first/last name) tied onto the SObject itself. FeedItems are an SObject, and are the way we
can associate anything with a Case itself.

Decision
--------

We will create a format which will represent the user, the course run key (if it exists), and the
comment itself. This will all be stored on the FeedItem.Body, and we will write custom parsing to
handle the serialization for both reading and writing to/from Salesforce. We will attempt to get the
match to our pattern before defaulting to the Salesforce author and the raw comment body when
returning this over the API


Benefits
--------

- It allows us to use Salesforce and the default Salesforce views/workflows for Cases and Chatter

- We control both the reads and the rights from our system to Salesforce, so all entries will adhere
  to our format

- Easy to discern information at a glance, and end users won't know the difference


Consequences
------------

- This is a less elegant solution than having specific field types inside of Salesforce

- It is fragile in the sense that updating our format will always need to be backwards compatible,
  or that we will need a migration script to update old entries

- Loses out on all User data in Salesforce and instead just has a username and first name/last name,
  though this is not a negotiable consequence

