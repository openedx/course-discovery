from social_core.backends.oauth import BaseOAuth2



class GoodGridOAuth2(BaseOAuth2):
    name = 'goodgrid'
    AUTHORIZATION_URL = 'https://findgood.goodgrid.com/AuthorizationServer/OAuth/Authorize'
    DEFAULT_SCOPE = ['personal']
    # TODO Work with Good Grid to support the code response type.
    RESPONSE_TYPE = 'token'
    REDIRECT_STATE = False
    STATE_PARAMETER = False
