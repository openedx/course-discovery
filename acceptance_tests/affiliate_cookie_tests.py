"""
Tests for affiliate tracking cookies.
"""
from django.test import TestCase
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from acceptance_tests.config import (
    AFFILIATE_COOKIE_NAME, BASIC_AUTH_PASSWORD, BASIC_AUTH_USERNAME, COOKIE_DOMAIN, ECOMMERCE_URL_ROOT, LMS_URL_ROOT,
    MARKETING_SITE_URL_ROOT
)


def _with_basic_auth(url):
    """
    If basic auth parameters have been provided, return the given URL
    with auth added. Otherwise, just returns the URL unchanged.
    """
    if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
        return url.replace('://', '://{username}:{password}@'.format(
            username=BASIC_AUTH_USERNAME,
            password=BASIC_AUTH_PASSWORD
        ))
    return url


class AffiliateCookieTestMixin:
    """
    Test mixin for affiliate tracking cookies. Classes inheriting from
    this should also inherit from TestCase and define a `url` property
    which will be used to test cookie tracking.
    """

    cookie_value = "test_partner"

    def setUp(self):
        super().setUp()
        opts = Options()
        opts.set_headless()
        self.browser = webdriver.Firefox(opts)
        self.cookie_name = AFFILIATE_COOKIE_NAME
        self.cookie_domain = COOKIE_DOMAIN

    def tearDown(self):
        super().tearDown()
        self.browser.quit()

    def test_without_query(self):
        """Verify that no cookie is set without affiliate query parameters."""
        self.browser.get(self.url)
        self.assertIsNone(self.browser.get_cookie(self.cookie_name))

    def test_with_query(self):
        """Verify that GTM drops a cookie when the correct query parameters are present."""
        self.browser.get(
            '{root}?utm_source={partner}&utm_medium=affiliate_partner'.format(
                root=self.url, partner=self.cookie_value
            )
        )
        cookie = self.browser.get_cookie(self.cookie_name)
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie['value'], self.cookie_value)
        self.assertEqual(cookie['domain'], self.cookie_domain)

    def test_with_query_wrong_medium(self):
        """Verify that requests without utm_medium=affiliate_partner do not get a cookie."""
        self.browser.get('{root}?utm_source={partner}&utm_medium=nope'.format(
            root=self.url,
            partner=self.cookie_value
        ))
        self.assertIsNone(self.browser.get_cookie(self.cookie_name))


class MarketingSiteCookieTest(AffiliateCookieTestMixin, TestCase):
    """Cookie tests for the marketing site."""

    url = MARKETING_SITE_URL_ROOT


class LmsCookieTest(AffiliateCookieTestMixin, TestCase):
    """Cookie tests for the LMS."""

    url = _with_basic_auth(LMS_URL_ROOT + '/login')


class EcommerceCookieTest(AffiliateCookieTestMixin, TestCase):
    """Cookie tests for ecommerce."""

    url = ECOMMERCE_URL_ROOT + '/basket/'
