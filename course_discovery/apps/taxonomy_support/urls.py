from django.urls import include, path

app_name = 'taxonomy_support'

urlpatterns = [
    path('', include('taxonomy.urls')),
    path('api/v1/', include('taxonomy_support.api.v1.urls'), name='v1'),
]
