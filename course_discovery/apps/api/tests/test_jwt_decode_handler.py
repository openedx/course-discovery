import jwt
from django.test import TestCase

from course_discovery.apps.api.jwt_decode_handler import decode
from course_discovery.apps.api.tests.jwt_utils import generate_jwt_payload, generate_jwt_token
from course_discovery.apps.core.tests.factories import UserFactory


class JWTDecodeHandlerTests(TestCase):
    def setUp(self):
        super(JWTDecodeHandlerTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.payload = generate_jwt_payload(self.user)
        self.jwt = generate_jwt_token(self.payload)

    def test_decode_success(self):
        self.assertDictEqual(decode(self.jwt), self.payload)

    def test_decode_error(self):
        with self.assertRaises(jwt.InvalidTokenError):
            decode("not.a.valid.jwt")
