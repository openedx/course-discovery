class EcommerceSiteAPIClientException(Exception):
    pass


class MarketingSiteAPIClientException(Exception):
    pass


class MarketingSitePublisherException(Exception):
    pass


class AliasCreateError(MarketingSitePublisherException):
    pass


class AliasDeleteError(MarketingSitePublisherException):
    pass


class FormRetrievalError(MarketingSitePublisherException):
    pass


class NodeCreateError(MarketingSitePublisherException):
    pass


class NodeDeleteError(MarketingSitePublisherException):
    pass


class NodeEditError(MarketingSitePublisherException):
    pass


class NodeLookupError(MarketingSitePublisherException):
    pass


class PersonToMarketingException(Exception):
    """ The exception thrown during the person adding process to marketing site """

    def __init__(self, message):
        super().__init__(message)
        suffix = 'The person data has not been saved. Please check your marketing site configuration'
        self.message = f'{message} {suffix}'


class UnpublishError(MarketingSitePublisherException):
    pass
