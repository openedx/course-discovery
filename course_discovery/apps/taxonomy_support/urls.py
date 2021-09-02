from django.conf.urls import include, url

app_name = 'taxonomy_support'

urlpatterns = [
    url(r'', include('taxonomy.urls')),
]
