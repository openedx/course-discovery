import json
from algoliasearch.search_client import SearchClient
from django.core.management import BaseCommand, CommandError

# write script to grab data from prod
# write script to push data to stage
# delete data file
# add arguments

applicationID = 'meowmeow'
adminAPIKey = 'meowmeow'
indexName = 'meowmeow'

class Command(BaseCommand):
    client = SearchClient.create(applicationID, apiKey)
    index = client.init_index(indexName)

    hits = []

    for hit in index.browse_objects({'query': ''}):
        hits.append(hit)

    with open('algolia_prod_data.py', 'w') as f:
        json.dump(hits, f)

