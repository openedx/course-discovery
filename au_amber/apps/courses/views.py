from django.views.generic import TemplateView


class QueryPreviewView(TemplateView):
    template_name = 'catalogs/preview.html'
