30. New search endpoints powered by ES SearchAfter
========================

Status
--------
Accepted (December 2024)

Context
---------
Elasticsearch enforces a strict limit on the number of records that can be retrieved in a single query,
controlled by the `MAX_RESULT_WINDOW` setting, which defaults to 10,000.
When a query attempts to retrieve more results than this limit, Elasticsearch does not simply truncate the results—instead,
it can lead to partial or incomplete data retrieval across search endpoints, potentially causing significant data loss or incomplete query responses.

Increasing this limit is not a viable solution, as it can lead to significant performance issues,
including increased memory usage and query latency, which can degrade the cluster's overall stability.

To address this issue, we need a more efficient way to paginate large query results.
The solution must allow for seamless and reliable pagination without imposing excessive resource demands on the system.
Furthermore, it should ensure that the existing search functionality and search responses remain unaffected in the current version of the endpoint.

Decision
=========
We will implement custom functionality based on ElasticSearch's `search_after` pagination mechanism to efficiently handle large query results.

SearchAfterPagination
---------------------
A new `SearchAfterPagination` class will be introduced to facilitate efficient pagination of ElasticSearch results.

**How It Works**

- Instead of traditional offset-based pagination, it relies on the sort values of the last retrieved document to fetch the next set of results.
- This mechanism ensures that large datasets can be paginated efficiently without hitting the `MAX_RESULT_WINDOW` limitation.
- The `SearchAfterPagination` class will parse the `search_after` query parameter to retrieve and return the appropriate set of results.

SearchAfterMixin
----------------
A new mixin, `SearchAfterMixin`, will be created to enable the `search_after` functionality in catalog query endpoints.

**Features**

- It can replace `PkSearchableMixin` in various models.
- Introduces custom parameters such as `queryset` and `documents` to enable filtering at the query level, minimizing the need to fetch all entries from ElasticSearch, improving efficiency.
- Supports the new endpoint while ensuring that `v1` functionality remains unaffected.

v2 Search Endpoint Implementation
---------------------------------

**Key Enhancements**

- A new version (`v2`) of the `/search/all/` endpoint will be introduced to enhance functionality while maintaining backward compatibility with `v1`.
- Response documents will include a `sort` field to be used as the `search_after` query parameter for subsequent queries.
- This approach enables scalable retrieval of large datasets by bypassing the `MAX_RESULT_WINDOW` limitations.

**Serializer Updates**

New serializers will be integrated for the `v2` implementation:
- `AggregateSearchListSerializerV2` will extend `AggregateSearchListSerializer`, supporting the `search_after` pagination mechanism and incorporating newer serializer versions for the same document types.
- New versions of the following serializers will include additional search index fields, specifically `sort` and `aggregation_uuid`, in their responses:

- `CourseRunSearchDocumentSerializer`
- `CourseSearchDocumentSerializer`
- `ProgramSearchDocumentSerializer`
- `LearnerPathwaySearchDocumentSerializer`
- `PersonSearchDocumentSerializer`

**Consumer Interaction**

Consumers will interact with the new `v2` search endpoint by making an initial request to `/api/v2/search/all/`, which returns search results along with a `next` URL, generated through the `sort` value of the last document.
For subsequent pages, consumers can follow the `next` link.

**Example Usage**

.. code-block:: python

    # First request
    response1 = requests.get('/api/v2/search/all/')
    results1 = response1.json()
    next_page_search_after = results1['next']  # This is the sort value of the last document

    # Next request using the 'next' value
    response2 = requests.get(next_page_search_after)

Consequences
------------
- The v2 search endpoint will introduce two new fields, `aggregation_uuid` and `sort`, in response to support the search_after pagination mechanism.
- The v2 `CatalogQueryContainsViewSet` features optimized querying and leverages the SearchAfterMixin to utilize search_after pagination.

Next Steps
-------------------------
- Extend SearchAfter Functionality: Implement `search_after` for other Elasticsearch search endpoints.
- Notify Users: Inform consumers about the changes and provide support during the transition.
- Monitor Performance: Track the performance of the new endpoint post-deployment.
