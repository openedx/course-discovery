25. Support multiple verified seats for a course run
------------------------------------------------------------------

Status
------

Accepted (July 2023)

Context
-------

While implementing in app payments mobile team decided to use current ecommerce implementation as its backend. This way all the analytics, sales and refunds record will stay at a single place.
Mobile platforms e.g. play store and app store apply some restrictions on product price and sku names. Therefore a separate verified seat was needed for mobile.
The seat was added on ecommerce side and it worked perfectly with django oscars on ecommerce. But when discovery consumed this data, course publishers started having problems on publishing a course run.
During spike it turned out discovery was expecting only a single verified seat for a course run and code was written according to this logic.
We need to identify all the places and adjust our code to expect multiple verified seats for a single course run.

Decision
--------

Discovery will support multiple verified seats for a single course run.
All the places will be identified and fixed where we are expecting only a single verified seat for a course run.
We'll keep monitoring discovery and will fix any future issue regarding multiple verified skus.

Consequences
------------

Ecommerce can sync data having multiple verified skus without any error.

Course run can be changed without any issue on publisher.
