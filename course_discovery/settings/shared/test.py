

# We use the RealtimeSignalProcessor here to ensure that our index is
# updated, so that we can search for data that we create in our tests.
HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.RealtimeSignalProcessor'

SYNONYMS_MODULE = 'course_discovery.settings.test_synonyms'

EDX_DRF_EXTENSIONS = {
    'OAUTH2_USER_INFO_URL': 'http://example.com/oauth2/user_info',
}

DEFAULT_PARTNER_ID = 1

# Enable offline compression of CSS/JS
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

SOLO_CACHE = None
