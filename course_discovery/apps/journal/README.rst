=======
Journal
=======

The Journal app in discovery is meant to the source of truth for most journal related information. It includes two models: Journal and JournalBundle.

**Journal**:

The journal product is similar to a course run in the fact that it has content is linked to an organization and you can purchase/receive access to it. One notable difference is that a Journal will have an access_length, which determines the amount of time the learner will have access to it post-purchase. This is our first stage towards a subscription model.

**JournalBundle**:

The journal bundle is a collection of journals and courses. It works similar to a program in the bundling aspect, the difference lies in the fact that it doesn't necessarily constitute a progression of courses. The first (and possibly most common) use case that will use this is bundling a single course with a single journal.

**Things to note**:

- The journals app was intentionally decoupled as much as possible from the rest of the discovery, both for future developer sanity, and to minimally affect the rest of the discovery platform should the scope of the journals product change.

- The journals product has a seperate IDA (Journals) which works as the publishing platform, the consumption platform, and the marketing platform. This is different from the structure of studio/lms and so some information may be handled differently in this application.
