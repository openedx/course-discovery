15. Use Event Bus to Replace Refresh Course Metadata
----------------------------------------------------

Status
------

Accepted

Context
-------

In an effort to update and progress our overall system architecture, we have `made the decision to use an event bus`_ for communicating between services. Discovery
is a service that synchronizes data between itself and several other services, relying on a management command run on Jenkins, ``refresh_course_metadata``, that makes
REST api requests to both ecommerce and LMS. This work is being done by a non-owning team of discovery to prove out a use case for the event bus by utilizing an
already existing pattern.

.. _made the decision to use an event bus: https://open-edx-proposals.readthedocs.io/en/latest/architectural-decisions/oep-0052-arch-event-bus-architecture.html

Decision
--------

We will be duplicating an existing ``refresh_course_metadata`` workflow with a event that gets sent to and received from the event bus, replicating course information
published in Studio. While we would like to see all of ``refresh_course_metadata`` replaced with events, that work is outside the scope of this ADR.

Consequences
------------

- Changes in Studio will be reflected on Discovery in the Discovery database in a much more timely manner instead of being updated once a day with the run of RCM.
- The current implementation of this work with event bus will not replace, merely duplicate, the work done by ``refresh_course_metadata``. We are not removing the
  RCM course update code at this time, and it will act as a backstop for the event workflow until we are certain of event bus stability. Future work to remove
  ``refresh_course_metadata`` will have to be more careful without the backstop.
- This may be a small part of a larger effort to replace all of RCM with events, but this ADR only covers the Studio use case.
- We may see race conditions between events, and we will be relying on workarounds (making a new change to issue a new event) or another RCM run to fix the issue.
- An event consumer will be running on new infrastructure and will have to be maintained separately from the Discovery application deployment. See the `Managing Kafka Consumers ADR`_
  for more details.
- The event consumer will convert any instances of an event it receives into `a Django signal`_ that will indicate that course data has been updated.
  While we are implementing only one listener for this signal at the moment, other parts of the system could make use of it in the future.

.. _a Django signal: https://github.com/openedx/openedx-events/blob/7620775586f2746c77ffb391162094de901fb4b0/openedx_events/content_authoring/signals.py#L18
.. _Managing Kafka Consumers ADR: https://github.com/openedx/event-bus-kafka/blob/main/docs/decisions/0003-managing-kafka-consumers.rst
