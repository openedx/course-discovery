28. Fixed USD Pricing
========================

Status
--------
Accepted (Jul 2024)

Context
---------
Course Discovery is equipped with the capability to ingest and update courses from external sources (through the csv_loader).
These external courses may be priced in various currencies, necessitating conversion to a standardized currency (USD) before
their introduction into discovery. Given the volatility of exchange rates, the product prices coming into discovery may fluctuate with
each data ingestion.

The regular fluctuation in prices poses challenges for customers, especially those purchasing courses in bulk (B2B). These fluctuations can lead to
situations where a customer plans to make a purchase within budget, only to find that prices have changed unfavorably when
they proceed with the transaction. This inconsistency may disrupt budgetary planning and affect decision-making processes for
customers. This is particularly problematic for B2B customers, who may have predefined contracts and can not exceed their budget constraints. 

Decision
----------
A new field, fixed_price_usd, will be introduced to the course run model within Course Discovery. This field will be accessible
through the standard course and search APIs. Consumers will have the ability to retrieve and utilize this field from Discovery APIs,
enabling them to price their offerings based on this stable fixed price in USD. It is assumed that the fixed price will remain
relatively stable over time, minimizing the impact of currency fluctuations for B2B customers.

The existing pricing fields and their associated logic will remain unchanged within Course Discovery. It will be the responsibility
of consumers, such as enterprise, to appropriately manage any potential implications of using the fixed price field within their own
systems and processes.

Consequences
--------------
- The current Pricing flow in Discovery will remain as is.
- There will be no impact on Seats, Entitlements, and their associated logic.
- The current flow of propagation of pricing information to Ecommerce will remain as is.
- Analytics/Data teams will need to ensure that they track Enterprise Customers' purchases against the fixed price appropriately.

Alternatives Considered
-------------------------

- It would have been preferable to add this field at the Seat level somehow, and not clutter the CourseRun model unnecessarily.
  However, due to some historical reasons, Executive Education courses (for which we need this functionality), only have unpaid
  seats. It would be confusing to add pricing information to an unpaid seat.

- The field could have been integrated at the course level, aligning with the current discovery flows where the course price (CourseEntitlement)
  is applied to all course runs. However, this approach does not accommodate pricing at the course run level, which has been a significant
  issue for discovery users in the past. Although there are some workarounds, such as manually adjusting prices in the database, these solutions
  are both cumbersome and inefficient.
