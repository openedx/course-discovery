""" API v1 URLs. """
from rest_framework import routers

from au_amber.apps.api.v1 import views

urlpatterns = []

router = routers.SimpleRouter()
router.register(r'catalogs', views.CatalogViewSet)
router.register(r'courses', views.CourseViewSet, base_name='course')

urlpatterns += router.urls
