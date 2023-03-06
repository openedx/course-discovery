18. Add Product Source In Catalog
=================================

Status
======

Accepted (March 2023)

Context
=======

Owing to the platform focused marketing and revenue strategies, now there is a massive opportunity to improve the
marketplace architecture. As opposed to the Legacy Catalog that only had single platform courses, now it is
expanding and have other platform's products to plugged into the system that are accessible via Discovery's course and
program APIs. This will help to expand the system as marketplace where different platforms/sources can market their
own courses and programs, which may or may not have the same workflows and processes depending upon their business
context. So there is a requirement to maintain platform and their products at individual level in DB, that's why
system requires a new mechanism to identify different platforms and their products.


Decision
========

Create a new model named Source in DB and populate data of sources. Then associate each catalog
product (courses and programs) with the relevant product source.

For Ingestion
-------------
System can get CSVs from different sources. So update command `import_course_metadata` and `import_degree_data`
to accept product source as parameter and associate the ingested products with that product source.

For OFAC Restriction
--------------------
For Legal Review some products are being restricted on the basis of their type. Different sources can have different
product types which need to be restricted. So add restricted product types column in newly created ProductSource model,
and update code to automatically restrict products of that specific type in specific product source during
create or update operation of product.

For Organization Mapping
------------------------
Different sources can have different organizations with their own codes, that may already exist into the system so
rather than creating new organization there is a need to connect those organizations with system's organizations.
To resolve this, create a new model of OrganizationMapping associated with ProductSource and Organization model that
will contain organization codes of different source mapped with organizations present in our DB.


Consequences
============
* Product source value of any product must be given.
* Product source value will be returned in Course and Program APIs so should be handled accordingly.
* As there will be checks on the base of product source so default value must be defined for the products.
* Backfilling of the products which are not associated with product source will be needed.

Rejected Alternatives
=====================
* Create new enrollment track: It was rejected because enrollment tracks indicates course types and course type is on course level, but source is a high level entity which have courses, programs or organizations
* Add new source field in Program and Course model: It was rejected because there are some properties of product source itself (for example: add OFAC restricted product types of a product source) and without creating relation between source and product it will be difficult to manage and update product source

