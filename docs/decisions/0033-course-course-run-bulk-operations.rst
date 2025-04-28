33. Course and Course Run Bulk Operations
=========================================

Status
-------
Accepted (April, 2025)

Context
--------
Course Discovery is the catalog and data aggregator service in Open edX. It communicates with platform and ecommerce, exchanges relevant information, and is an entry point for creating courses and course runs using Publisher MFE.
For an organization, Discovery is not required to create the courses on platform (Studio), but the usage of discovery and publisher MFE speeds up the management of courses and their respective course runs.

While the combination of publisher and discovery is impactful, there are limitations in the process of getting the product data in the system.
It is common for partners to use spreadsheets, CSVs, or documents to manage the product data. The data document will contain the information about a product, its active runs, and upcoming or planned dates.
To get that information into the catalog, they need to follow a process. Starting from publisher, they create a new course and course run (or search and open the existing page), perform their edits, save, and repeat. This activity is time-consuming and redundant.
If the information is already present in a commonly used format, there should be a capability to use that data and create or update records within the system. The ADR explains the additions being made to support such a use-case.


Decision
---------
To add bulk operations capability in course-discovery, a variety of additions will be made:

1. Add a new model ``BulkOperationTask`` to contain bulk operation task information
2. Add new CSV Data loaders for different bulk operations
3. Add a new celery task to execute bulk operations
4. Install `django-celery-results <https://github.com/celery/django-celery-results>`_ to store celery task results

Bulk Operation Model
^^^^^^^^^^^^^^^^^^^^
A new model, ``BulkOperationTask``, will be added to record the bulk operation tasks. The model will have the information of operation type, data csv, csv uploader, the status of the task, the task summary, and a few related fields. At the time of the writing, the following bulk operations are planned to be added:

- Course Creation

  - Creating a new course and course run from scratch
- Course Updates

  - Updating course fields of an existing course
- Course Re-runs

  - Creating new runs from an existing run of a course
- Course Run Updates

  - Updating course run fields of an already created course run
- Course Editor Updates

  - Adding or Removing editors to a course


New CSV Data Loaders
^^^^^^^^^^^^^^^^^^^^^
In the context section, it was explained that partners manage the data on their end, in majority of cases, in spreadsheets, documents, or individual CSVs. To handle the bulk operations, not all the partner-supplied documents could be an input to the system.
It was decided to use CSVs to define the data format for different operations. The selection of CSV over JSON, XML, or other formats was done because CSV is frequently used in industry, by technical and non-technical users alike, to manage the bulk data.

CSVs will have a different format depending upon the operation type. To handle them, new CSV loaders will be added. The loaders will correspond to one or more bulk operation type:

- Course Re-run CSV loader
- Course Loader

  - Course Creation and Updates
  - Course Run Creation and Updates
- Course Editor Loader

CSV loaders will utilize the existing course and course run APIs in the discovery for data ingestion. Those APIs are already in use by Publisher MFE and handle the side-effects (change the status, creating non-draft entries, pushing to ecommerce, etc.).
The use of the APIs will ensure data loaders behave along the same lines as Publisher.

Running Bulk Operations
^^^^^^^^^^^^^^^^^^^^^^^
In a CSV, there will be multiple rows and processing each row would take time. Doing the bulk operation synchronously would not be scalable. Hence, the bulk operations will be executed as a new celery task. When a new bulk operation model entry is created, a new celery task will be queued.
The celery task will be responsible for:

- Select the appropriate loader
- Perform CSV validation and Initiate ingestion
- Update bulk operation model object
- Send the notification email after the ingestion completes

django-celery-results
^^^^^^^^^^^^^^^^^^^^^^
The bulk operation model will contain the information about bulk operation request. It will not contain the details of executed celery task. To store the results of a celery task executed against a bulk operation, a new third-party package django-celery-results will be added to course-discovery.
It defines a new model TaskResult which holds the important information about a celery task, such as task name, result, task id, task arguments, etc. The task id will also be stored in Bulk Operation model object to establish the connection between both objects.

Objective
---------

- Reduce the human effort needed to get the bulk of products into the catalog.
- Speed up partner onboarding by providing an easy to use CSV format to bulk create courses and course runs.
- Add the capability to perform multiple edits across various products without needing to visit each product page.

Alternatives Considered
------------------------
- Expand the existing csv_loader used primarily for external courses ingestion. That loader is already doing a lot of things to ingest external courses and handling the new use-cases in it would make it difficult to understand what the loader was doing.
- Writing the TaskResult model in the codebase from scratch. The new model will contain the information about the celery task, the arguments, the time taken, the related bulk operation request, etc. However, django-celery-results does the same thing and is already in use in other Open edX repositories (enterprise-catalog, edx-platform).
- Add only one new loader to handle all the bulk operations. While handling the validations and operations would have worked in a single loader, it would have made future maintenance and enhancements difficult and prone to break.