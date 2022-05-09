External product lines in discovery
===================================

Status
======

In Review

Decision
========

Pending

Context
=======

To sync products data in discovery from other lines of businesses without causing
downtime or poor performance, the interface that will accept data payload in a
pre-defined format is required. The representational differences in data between
LoBs and discovery would be resolved via transformers. Field mapping and validation
of the incoming data can be done using a data transformer.
While syncing data from an external source, a compatible payload and data
transformers must be placed before the invocation of creation/update API(s) so
that the payload is reshaped and validated as per the API(s) need.
While creating/updating a product, one should also consider that multiple
internal and external API(s) must be invoked, like the instructor and eCommerce,
respectively.

At any given time, there is a probability that the discovery may encounter a
high flux of data from different lines of businesses(LoBs).The current API(s)
are not well-written to validate all the edge-cases in data payload that may
result in flooding validation errors. Other than that, database operations would
be drastically affected which can result in availability issues.

Moreover, to create/update a product, multiple APIs need to be invoked in a
queue pattern. So, if the invocation order is not maintained, data integrity
will be compromised. This situation would create overhead in communication
because multiple teams need to be connected to resolve the data integrity conflict.

Possible Approaches
===================

To better solve the above potential issues, there are two approaches either of
them can be utilized.

- a management command responsible for populating products data which can ensure
data management and invocation order of API(s).
- A new API that can be written to serve the same purpose.

Selected Approach
=================

A separate API for this job is better suited, which would take care of the management
of data payload as well as invocation sequence of API(s).

By modeling the changes in LoB products as events, which will
follow the scope of a requested change, i.e., whether the change impacts
instructor, degree, course, course-run etc. or a complete operation of product
creation. This flexibility in the process demands different payload(s) as per
the nature of a needed change. The API(s) are already part of the system would
create a communication gap as they would have to deal with multiple APIs for
various operations, which can be overwhelming.

Based on the context and already existing functional constraints, a separate API
is better suited because it would be readily available. In contrast to the API,
the management command must be triggered manually. Currently, there is no API
in the discovery that can be used to handle the data from an external source and
create/update products objects accordingly, so if a new API is designed, it is
expected to be responsible for:

- Management of external products data.
- Invocation order of the API(s).
- A better developer experience of feedback to locate the exact point of failure.
- Bridging different lines of businesses(LoBs)
- Payload management based on an event name

To avoid downtime and poor performance, the incoming request to the API is
served under controlled conditions like throttling. An added benefit
to this approach is that a separate status API is not needed, which would lessen the
overhead in terms of communication and implementation with concerned external bodies.

Note: This API act as a gateway by which external products are created and
updated in discovery. A single API can serve the purpose better than multiple
API(s) in async operations.

Rejected Alternatives
=====================

Async execution can also be considered via celery workers. If this approach is
considered then it will demand another API which gives the feedback related to
event/celery task.

In addition to this, it may cost infrastructure in terms of creation and
managing a celery queue independently.
