29. JWT roles based Throttling
==============================

Status
--------
Accepted (Dec 2024)

Context
---------
Course Discovery APIs are used by a number of consumers like external partners and marketers, the LMS, Publisher, and the
enterprise-catalog service. One of these consumers that stands out is the Enterprise Learner Portal. Just like Publisher, this
portal is an MFE that queries discovery at runtime. However, unlike Publisher, where our users are mostly staff and partners, the
learner portal is intended to be used by regular enterprise learners and admins i.e those without any staff or privileged access.

As of late, our regular throttling limits have proven to be a little too aggressive for some of these learners. As this is clearly 
non-malicious traffic, we would like to find a way to set more lenient throttling limits for these learners.

Decision
----------
Since these learners authenticate with Discovery by using JWT tokens issued by the LMS, we have decided to use the `roles` key
in the JWT to identify them. Enterprise customers are guaranteed to have one of a small number of fixed roles assigned to them. 
Once we identify that an incoming request's user has one of these roles in their JWT, we will enable higher rate limits for them.

Two new settings, `ENHANCED_THROTTLE_JWT_ROLE_KEYWORDS` AND `ENHANCED_THROTTLE_LIMIT` will be added. The `ENHANCED_THROTTLE_JWT_ROLE_KEYWORDS`
setting accepts a list of strings representing keywords that identify privileged JWT roles. Each keyword is matched against the
roles in a JWT token; if a keyword is found in any role, the user's throttle limits are set to the value of `ENHANCED_THROTTLE_LIMIT`.  

Consequences
--------------
- Some regular users (i.e without staff or any django group privileges) will have privileged rate limits
- We will need to be vigilant to ensure that the list of roles we consider privileged is accurate i.e its entries should only
  be associated to enterprise learners (i.e the users we need higher limits for). Furthermore, it should be impossible for
  "other" users to attain those roles.

Alternatives Considered
-------------------------
- Raise the throttle limits for everyone. However, that increases the possibility of scraping and service degradation attacks
  by malicious actors
- Extend the user model in discovery to store identification information for users with enhanced throttle limits. However, that
  conflicts with the responsibility of the LMS as the sole authentication provider. Furthermore, adding this information in 
  discovery for each enterprise user would needlessly complicate the enterprise onboarding and offboarding process.
