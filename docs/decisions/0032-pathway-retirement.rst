32. Retirement Mechanism for Pathways
======================================

Status
--------
Accepted (Feb 2025)

Context
---------
Currently, there is no way to mark a pathway as retired. This is often necessary due to changing requirements
for credit recognition on the partner organization's end, or the discontinuation of programs offered by them.
In such cases, these pathways should be hidden from the learner dashboard and any credit requests against them
should not be accepted.

Decision
----------
A new field **status** will be added to the pathway model. This field will support three possible values: *unpublished*,
*published* and *retired*. Existing pathways will be assigned the *published* status (through a data migration), while any new pathways will be set
to *unpublished* by default.

The **status** field will be exposed in the pathways endpoint, and the API will also support filtering by its value.

Consequences
--------------
Consuming systems, such as credentials and edx-plaform, will have to ensure that they take the status field in consideration
while processing pathways. Specifically, credentials will need to ensure that it does not allow credit redemption requests
against retired pathways, and edx-platform will need to exclude retired pathways from the programs section of the learner dashboard.

Alternatives Considered
-------------------------
One alternative considered was to hide retired pathways by default in the API responses. However, this approach
was soon determined to be problematic because it could cause issues on the Credentials side, which has its own
Pathway model (regularly synced with Discovery) having protected constraints with some other models. Additionally,
it is more transparent to place the responsibility of correct usage on the consuming systems, rather than automatically
filtering retired objects on discovery's end.
