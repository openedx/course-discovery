import os

ELASTICSEARCH_DSL = {'default': {'hosts': os.environ.get('TEST_ELASTICSEARCH_URL', 'localhost:9200')}}
# We use the RealtimeSignalProcessor here to ensure that our index is
# updated, so that we can search for data that we create in our tests.
ELASTICSEARCH_DSL_SIGNAL_PROCESSOR = 'course_discovery.apps.course_metadata.search_indexes.signals.RealTimeSignalProcessor'
ELASTICSEARCH_INDEX_NAMES = {
    'course_discovery.apps.course_metadata.search_indexes.documents.course': 'test_course',
    'course_discovery.apps.course_metadata.search_indexes.documents.course_run': 'test_course_run',
    'course_discovery.apps.course_metadata.search_indexes.documents.learner_pathway': 'learner_pathway',
    'course_discovery.apps.course_metadata.search_indexes.documents.person': 'test_person',
    'course_discovery.apps.course_metadata.search_indexes.documents.program': 'test_program',
}

SYNONYMS_MODULE = 'course_discovery.settings.test_synonyms'

EDX_DRF_EXTENSIONS = {
    'OAUTH2_USER_INFO_URL': 'http://example.com/oauth2/user_info',
}

DEFAULT_PARTNER_ID = 1

# Enable offline compression of CSS/JS
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

SOLO_CACHE = None
