28. Use elastic search's search_after pagination
========================

Status
--------
Accepted (December 2024)

Context
---------
ElasticSearch enforces a strict limit on the number of records that can be retrieved in a single query, 
controlled by the MAX_RESULT_WINDOW setting, which defaults to 10,000.
This limit results in loss of api response we get from `search/all/` endpoint.

Decision
----------
A new version (v2) of the `search/all/` endpoint will be introduced, 
utilizing ElasticSearch's `search_after` pagination mechanism while ensuring that the existing v1 functionality remains unaffected. 
A sort field will be included in the response documents, and its value can be used in the `search_after` query parameter to enable efficient pagination in subsequent queries.
