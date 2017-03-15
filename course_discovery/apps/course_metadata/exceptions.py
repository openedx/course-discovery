class MarketingSiteAPIClientException(Exception):
    """ The exception thrown from MarketingSiteAPIClient """
    pass


class ProgramPublisherException(Exception):
    """ The exception thrown during the program publishing process to marketing site """

    def __init__(self, message):
        super(ProgramPublisherException, self).__init__(message)
        suffix = 'The program data has not been saved. Please check your marketing site configuration'
        self.message = '{exception_msg} {suffix}'.format(exception_msg=message, suffix=suffix)


class PersonToMarketingException(Exception):
    """ The exception thrown during the person adding process to marketing site """

    def __init__(self, message):
        super(PersonToMarketingException, self).__init__(message)
        suffix = 'The person data has not been saved. Please check your marketing site configuration'
        self.message = '{exception_msg} {suffix}'.format(exception_msg=message, suffix=suffix)
