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
----------
A new version (v2) of the `search/all/` endpoint will be introduced to enhance functionality while ensuring that the existing v1 functionality remains unaffected. 
This version will utilize ElasticSearch's search_after pagination mechanism, specifically designed to handle large query results efficiently.

*How search_after Works:**
`search_after` is a pagination mechanism that allows retrieving results beyond the standard window limit by using the sort values of the last document from the previous page. 
Instead of using traditional offset-based pagination, it uses the actual sort values of the last retrieved document to fetch the next set of results, ensuring efficient and accurate pagination for large datasets.

In the v2 implementation, response documents will include a `sort` field that can be used as the `search_after` query parameter in subsequent queries. 
This approach enables scalable retrieval of large datasets by bypassing the `MAX_RESULT_WINDOW` limitations. 
To support this, a new `SearchAfterPagination` class will be introduced, which will parse the `search_after` query parameter to facilitate efficient pagination of ElasticSearch results.

Additionally, new serializers will be integrated for the v2 implementation. 
Specifically, the AggregateSearchListSerializerV2 will extend the existing AggregateSearchListSerializer,
supporting the `search_after` pagination mechanism and incorporating newer serializer versions for the same document types.

New versions of the serializers 
- CourseRunSearchDocumentSerializer
- CourseSearchDocumentSerializer
- ProgramSearchDocumentSerializer
- LearnerPathwaySearchDocumentSerializer
- PersonSearchDocumentSerializer

will be introduced to include additional search index fields, specifically `sort`` and `aggregate_uuid` in their responses. 

Consumers will interact with the new v2 search endpoint by making an initial request to `/api/v2/search/all/`, 
which returns search results along with a `next` field representing the `sort` value of the last document. 
For subsequent pages, they simply include this `next` value as the `search_after` parameter in their next request.

Example Usage:
```
# First request
response1 = requests.get('/api/v2/search/all/')
results1 = response1.json()
next_page_search_after = results1['next']  # This is the sort value of the last document

# Next request using the 'next' value
response2 = requests.get(f'/api/v2/search/all/?search_after={json.dumps(next_page_search_after)}')
```

Consequences
--------------
- The v2 search endpoint will introduce two new fields, `aggregate_uuid` and `sort`, in response to support the search_after pagination mechanism.

Next Steps
-------------------------
- Create SearchAfter Mixin: Develop a mixin to enable search_after functionality in the Django shell.
- Extend SearchAfter Functionality: Implement `search_after` for other Elasticsearch search endpoints.
- Notify Users: Inform consumers about the changes and provide support during the transition.
- Monitor Performance: Track the performance of the new endpoint post-deployment.
