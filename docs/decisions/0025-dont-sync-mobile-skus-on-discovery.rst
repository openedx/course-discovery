25. Don't sync mobile skus in discovery
------------------------------------------------------------------

Status
------

Accepted (September 2023).

Context
-------

While implementing in-app payments, the mobile team decided to use the current e-commerce implementation as its backend. This way, all the analytics, sales, and refunds records will stay in a single place.
Mobile platforms (e.g., Play Store and App Store) apply some restrictions on product prices and SKU names. Therefore, a separate verified seat was needed for mobile.
The seat was added on the e-commerce side, and it worked perfectly with Django Oscars on e-commerce. However, when Discovery consumed this data, course publishers started having problems publishing a course run.
During a spike, it turned out that Discovery was expecting only a single verified seat for a course run, and the code was written according to this logic. Not just Discovery, but all other services behave in the same way. Since all services fetch data from Discovery, adding another verified seat directly into Discovery is not a good idea. Any service can start having problems, and we might not even know if there is any problem with that service or not.

Decision
--------

Since mobile SKUs aren't required anywhere other than e-commerce, there is no need to sync those SKUs in Discovery.
Mobile SKUs will stay in e-commerce, and any service that needs this data can fetch them from e-commerce.
Any mobile SKU that is synced in Discovery will be deleted, and all syncing jobs will discard them while fetching data from e-commerce.
Mobile SKUs, as `documented`_, will be created in a certain format, i.e., ``mobile.{platform name}.{web SKU}``. For example, a web SKU with value 123 will have an iOS SKU of ``mobile.ios.123``. In this way, it is easy to identify mobile SKUs from web SKUs, and we can filter any SKU in Discovery that has "mobile" in its name.

.. _documented: https://2u-internal.atlassian.net/wiki/spaces/MOBL/pages/283508791/Enable+IAP+for+a+course+in+mobile#iOS

Consequences
------------

Discovery will not sync mobile SKUs from e-commerce. Mobile SKUs will reside only in the e-commerce service and can be fetched from there.

Any service can differentiate between mobile and web SKUs of the verified seat category by the "mobile" keyword in the SKU value.
When there is a price change on the publisher, the course run will be updated, and Discovery will push updated data to e-commerce.
E-commerce will detect this change and update SKUs' prices on relevant mobile platforms (Android, iOS) through APIs.
