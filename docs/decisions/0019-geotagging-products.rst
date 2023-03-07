19. Geotargetting Courses and Programs in Discovery
------------------------------------------------------------------

Status
------

Accepted

Context
-------

The various products offered on edX that are modeled in Discovery are associated with a specific organization or partner. The partner organizations on the platform can be from
any region of the world. But the question is, why is product location important?

The geographical location is important for search experiences in the following scenarios:

* Provided a user's location in form of longitude and latitude, the products close to that location should be higher up in search results.
* Blacklisting or whitelisting a product in certain locations should not display that product in those regions.

Discovery does not have capabilities to add geolocation information  and configure geolocation restriction to a product. These features can be useful for larger community in enhancing the search experience of  their catalogs configured on Discovery.

Decision
--------

Two new models are to be added in Discovery course_metadata Django app:

1. GeoLocation
2. AbstractLocationRestrictionModel

   * CourseLocationRestriction
   * ProgramLocationRestriction

GeoLocation model will be associated with Course and Program models. The association will allow tagging a product to a particular geographical location.

AbstractLocationRestrictionModel contains the information of countries and states where the product will be either whitelisted or blacklisted. The abstract model is used to create Course and Program specific location restriction models which are then associated with respective product model.

Future Enhancements
--------------------

* Provide Geolocation and LocationRestriction information on an Organization level and use Course/Program level geolocation fields as an override.
