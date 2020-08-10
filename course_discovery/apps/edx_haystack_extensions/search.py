import copy
from elasticsearch_dsl import Search as OriginSearch

from course_discovery.apps.edx_haystack_extensions.elasticsearch_boost_config import get_elasticsearch_boost_config
from course_discovery.apps.edx_haystack_extensions.response import DSLResponse


class BoostedSearch(OriginSearch):
    """
    Boosted search.

    Extends original search class to provide `function_score` block,
    which should improve the order of the output of the results,
    where the best will have the highest score.
    """

    def to_dict(self, *args, **kwargs):
        query_dict = super().to_dict(*args, **kwargs)
        function_score_config = get_elasticsearch_boost_config()['function_score']
        function_score_config['query'] = query_dict.pop('query')
        function_score = {'function_score': function_score_config}
        query_dict['query'] = function_score

        return query_dict


class FacetedSearch(OriginSearch):
    """
    Faceted search.

    Extends original search class to provide `DSLResponse` response class.
    The class adds a facet property to final response.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._response_class = DSLResponse

    def _clone(self, klass=None, using=None, index=None, doc_type=None):
        """
        Overwrite `_clone` method to be able a class, which be used to clone.
        """
        if klass is None:
            return super()._clone()
        if using is None:
            using = self._using
        if index is None:
            index = self._index
        if doc_type is None:
            doc_type = self._doc_type

        clone = klass(using=using, index=index, doc_type=doc_type)

        clone._response_class = self._response_class
        clone._sort = self._sort[:]
        clone._source = copy.copy(self._source) if self._source is not None else None
        clone._highlight = self._highlight.copy()
        clone._highlight_opts = self._highlight_opts.copy()
        clone._suggest = self._suggest.copy()
        clone._script_fields = self._script_fields.copy()
        for x in ('query', 'post_filter'):
            getattr(clone, x)._proxied = getattr(self, x)._proxied

        # copy top-level bucket definitions
        if self.aggs._params.get('aggs'):
            clone.aggs._params = {'aggs': self.aggs._params['aggs'].copy()}

        return clone
