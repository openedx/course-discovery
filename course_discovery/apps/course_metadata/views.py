from django.views.generic import TemplateView


class QueryPreviewView(TemplateView):
    template_name = 'demo/query_preview.html'


class SearchDemoView(TemplateView):
    template_name = 'demo/search.html'
