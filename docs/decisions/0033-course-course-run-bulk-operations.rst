33. Course and Course Run Bulk Operations
=========================================

Status
-------
Accepted (April, 2025)

Context
--------
Course Discovery is the catalog and data aggregator service in Open edX. It communicates with platform and ecommerce, exchanges relevant information, and is an entry point for creating courses and course runs using Publisher MFE.
For an organization partner, Discovery is not required to create the courses on platform (Studio), but the usage of discovery and publisher MFE speeds up the management of courses and their respective course runs.

While the combination of publisher and discovery is impactful, there are limitations in the process of getting the product data in the system.
It is common for partner organizations to use spreadsheets, CSVs, or documents to manage the data. Their document of choice will contain the information about a product, its active runs, and upcoming or planned dates.
To get that information into the system (discovery in this case), they need to go to publisher, create a new course/course run (or search and open the existing page), make their edits, save, and repeat. This activity is time-consuming and redundant.
If the information is already present in a commonly used format, there should be a capability to use that data and create or update records within the system. The ADR explains the additions being made to support such a use-case.


Decision
---------
To add bulk operations capability in course-discovery, a variety of additions will be made:

1. Add a new model to contain bulk operation task information
2. Add new CSV loaders for different bulk operations
3. Add a new celery task to execute bulk operations
4. Install `django-celery-results <https://github.com/celery/django-celery-results>`_ to store celery task results

Bulk Operation Model
^^^^^^^^^^^^^^^^^^^^
A new model will be added to record the bulk operation tasks. The model will have the information of operation type, data csv,data csv uploader, the status of the task, the task summary, and a few related fields. At the time of the writing, the following bulk operations are planned to be added:

- Course Creation
- Course Updates
- Course Run re-run
- Course Run Updates
- Course Editor Updates


New CSV Loaders
^^^^^^^^^^^^^^^
In the context section, it was explained that partners manage the data on their end, in majority of cases, in spreadsheets, documents, or individual CSVs. To handle the bulk operations, not all the data documents could be used as an input to the system.
It was decided to use CSVs to define the data format for different operations. The selection of CSV over JSON, XML, or other formats was done because CSV is frequently used in industry, by technical and non-technical users alike, to manage the data.

CSVs will have a different format depending upon the operation type. To handle the different CSVs, new CSV loaders will be added. The loaders will correspond to one or more bulk operation type. The following CSV loaders will be added to support the bulk operations:

- Course Run re-run CSV loader
- Course Loader

  - Course Creation
  - Course Updates
  - Course Run Updates
- Course Editor Loader

CSV loaders will heavily utilize the existing course and course run APIs in the discovery for data ingestion. Those APIs are already in use by Publisher MFE and handle the side-effects according to data (change the status, creating non-draft entries, pushing to ecommerce, etc.).
The use of the APIs will ensure CSV loaders' working is on the same lines as the publisher.

Running Bulk Operations
^^^^^^^^^^^^^^^^^^^^^^^
In a CSV, there will be multiple rows and processing each row would take time. Doing the bulk operation synchronously will not be scalable. Hence, the bulk operations will be executed as a new celery task. When a new bulk operation model entry is created, a new celery task will be queued.
The celery task will be responsible for:

- Validating the CSV with regards to chosen operation type
- Select the appropriate loader and initiate ingestion
- Update bulk operation model object
- Send the email after the ingestion completes

django-celery-results
^^^^^^^^^^^^^^^^^^^^^^
The bulk operation model will contain the information about bulk operation request. It will not contain the details of executed celery task. To store the results of a celery task executed against a bulk operation, a new third-party package django-celery-results will be added to course-discovery.
It defines a new model TaskResult which holds the important information about a celery task, such as task name, result, task id, task arguments, etc. The task id will also be stored in Bulk Operation model object to establish the connection between the both objects.

Objective
---------

- Reduce the human effort needed to get the bulk of products into the catalog.
- Speed up partner onboarding by providing an easy to use CSV format to bulk create courses and course runs.
- Add the capability to perform multiple edits across various products without needing to visit each product page.

Alternatives Considered
------------------------
- Expand the existing csv_loader used primarily for external courses ingestion. That loader is already doing a lot of things to ingest external courses and handling the new use-cases in it would make it difficult to understand what the loader was doing.
- Writing the TaskResult like model in the codebase. The new model will contain the information about the celery task, the arguments, the time taken, the related bulk operation request, etc. However, django-celery-results does the same thing and is already in use in other Open edX repositories (enterprise-catalog, edx-platform).
- Add only one new loader to handle all the bulk operations. While handling the validations and operations would have worked in a single loader, it would have made future maintenance and enhancements difficult and prone to break.