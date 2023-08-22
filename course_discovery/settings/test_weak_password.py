#! /usr/bin/env python
# -*- coding: utf-8 -*-

from django.test import TestCase
from django.contrib.auth.hashers import make_password

class WeakPasswordTest(TestCase):
    def test_weak_password_hashing(self):
        weak_password = "password123"
        hashed_password = make_password(weak_password)
        print("Hashed Password:", hashed_password)

        # Ensure the weak password is hashed using UnsaltedMD5PasswordHasher
        self.assertTrue(hashed_password.startswith('md5$'))
