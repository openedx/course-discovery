from django.conf.urls import include
from django.urls import path

app_name = 'taxonomy_support'

urlpatterns = [
    path('', include('taxonomy.urls')),
]
