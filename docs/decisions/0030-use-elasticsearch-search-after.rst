30. Introduce `/api/v2/search` Endpoint to Address v1 Limitations with search_after Pagination for Large Query Results
========================

Status
--------
Accepted (December 2024)

Context
---------
ElasticSearch enforces a strict limit on the number of records that can be retrieved in a single query. 
This limit is controlled by the `MAX_RESULT_WINDOW` setting, which defaults to 10,000. 
When this limit is exceeded, data loss occurs in responses retrieved from the `api/v1/search/all/` endpoint. 
Increasing this limit is not a viable solution. Doing so can have a significant impact on performance. 
It can also lead to an increase in the heap memory consumed by ElasticSearch, potentially degrading the system's stability.

To address this issue, we need a more efficient way to paginate large query results. 
The solution must allow for seamless and reliable pagination without imposing excessive resource demands on the system. 
Furthermore, it should ensure that the existing search functionality and search responses remain unaffected in the current version of the endpoint.

Decision
----------
A new version (v2) of the `search/all/` endpoint will be introduced to enhance functionality while ensuring that the existing v1 functionality remains unaffected. 
This version will utilize ElasticSearch's search_after pagination mechanism, specifically designed to handle large query results efficiently.

In the v2 implementation, response documents will include a `sort` field that can be used as the `search_after` query parameter in subsequent queries. 
This approach enables scalable retrieval of large datasets by bypassing the `MAX_RESULT_WINDOW` limitations. 
To support this, a new `SearchAfterPagination` class will be introduced, which will parse the `search_after` query parameter to facilitate efficient pagination of ElasticSearch results.

Additionally, new serializers will be integrated for the v2 implementation. 
Specifically, the `AggregateSearchListSerializerV2` will extend the existing `AggregateSearchListSerializer`, 
supporting the `search_after` pagination mechanism and incorporating newer serializer versions for the same document types.

New versions of the serializers `CourseRunSearchDocumentSerializer`, `CourseSearchDocumentSerializer`, `ProgramSearchDocumentSerializer`, `LearnerPathwaySearchDocumentSerializer`, and `PersonSearchDocumentSerializer` will be introduced to include additional search index fields, specifically "sort" and "aggregate_uuid," in their responses. 

Consumers will interact with the new v2 search endpoint by making an initial request to `/search/all/v2/`, 
which returns search results along with a `next` field representing the `sort` value of the last document. 
For subsequent pages, they simply include this `next` value as the `search_after` parameter in their next request.

For example:
```
# First request
response1 = requests.get('/search/all/v2/')
results1 = response1.json()
next_page_search_after = results1['next']  # This is the sort value of the last document

# Next request using the 'next' value
response2 = requests.get(f'/search/all/v2/?search_after={json.dumps(next_page_search_after)}')
```
