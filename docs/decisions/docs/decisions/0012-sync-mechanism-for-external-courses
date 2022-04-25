Sync external course(s) in discovery
====================================

Status
======

In Review

Context
=======
In order to ingest the data of the external course(s) a middleware API(s) are needed to be created between Discovery and 2u Product lines which would serve as a gateway through which 2U systems will be adding data within Discovery. Therefore, it is necessary to create its implementation approach so that a sustainable solution would be suggested.

Decision
========

Pending

Approaches Considered
=====================

The course creation api(s) are expected to interact with external service(s) like e-commerce which may increase the response time because of the different architectural constraints in different systems.
Taking into account its context, there is a potential higher risk of poor-performance or possibly downtime of the discovery platform.
This gives birth to the inquiry of the feasible mechanism in terms of its execution(async/sync).

Middleware API ingest the data asynchronously
---------------------------------------------

- The architecture of the internal implementation of the middleware API should fulfill the request a-synchronously i.e. via celery workers so that poor-performance and possibly a downtime must be avoided.
- This approach must be aided with an API which is used to keep track of the status for a particular event/celery task.

Middleware API ingest the data synchronously
---------------------------------------------

- The architecture of the internal implementation of the middleware API should fulfill the request synchronously but under controlled conditions like throttling.
- The NR(newrelic) data related to performance of the discovery instance can be utilized to decide whether a synchronous approach is favourable or not.
- There is an added benefit of this approach i.e. a separate status API is not needed which would lessen the overhead in terms of implementations and communication with the concerned bodies.
