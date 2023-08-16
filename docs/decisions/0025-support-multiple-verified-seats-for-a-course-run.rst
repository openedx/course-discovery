25. Support multiple verified seats for a course run
------------------------------------------------------------------

Status
------

Accepted (August 2023)

Context
-------

While implementing in app payments mobile team decided to use current ecommerce implementation as its backend. This way all the analytics, sales and refunds record will stay at a single place.
Mobile platforms e.g. play store and app store apply some restrictions on product price and sku names. Therefore a separate verified seat was needed for mobile.
The seat was added on ecommerce side and it worked perfectly with django oscars on ecommerce. But when discovery consumed this data, course publishers started having problems on publishing a course run.
During spike it turned out discovery was expecting only a single verified seat for a course run and code was written according to this logic.
Discovery repo code needs to be adjusted to handle multiple verified seats for a single course run.

Decision
--------

To support in app payments Discovery will support multiple verified seats for a single course run. In addition all services where discovery publishes course run changes(e.g. ecommerce, lms) are also required to expect multiple verified seats.
All the places will be identified and fixed where Discovery is expecting only a single verified seat for a course run.
Every mobile sku will have an identifier is sku name(e.g. android, ios). That is how discovery can differentiate between mobile and web skus of verified seat category.
Discovery service will be monitored and any future issue regarding multiple verified skus will be fixed.
Mobile team will do a discovery on how to push a mobile sku in discovery(whether to give an interface on publisher or push it through ecommerce api).

Consequences
------------

Discovery will have multiple verified skus having same or different price for a single course run. Discovery can differentiate between mobile and web skus of verified seat category by mobile keywords(android, ios) in sku value or title.

When there is a price change on publisher, course run will be updated and discovery pushes updated data to ecommerce, Ecommerce will detect this change and will update skus price on relevant mobile platforms(android, ios) through apis.

Ecommerce can sync data having multiple verified skus without any error.

Course run can be changed without any issue on publisher.

There will be a way to add mobile skus in discovery database.
