"""
Loader for adding or removing CourseEditor entries using CSV input.
"""

import logging
import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Q

from course_discovery.apps.course_metadata.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.data_loaders.constants import (
    COURSE_EDITOR_LOADER_ERROR_LOG_SEQUENCE, CourseEditorIngestionErrorMessages, CourseEditorIngestionErrors
)
from course_discovery.apps.course_metadata.data_loaders.mixins import DataLoaderMixin
from course_discovery.apps.course_metadata.models import Course, CourseEditor, Organization

logger = logging.getLogger(__name__)
User = get_user_model()


class CourseEditorsLoader(AbstractDataLoader, DataLoaderMixin):
    """
    Loads CourseEditor data from CSV and performs add/remove actions for each row.
    """

    BASE_REQUIRED_DATA_FIELDS = ['username_or_email', 'course_key_or_uuid', 'action']

    def __init__(
        self,
        partner,
        api_url=None,
        max_workers=None,
        is_threadsafe=False,
        csv_path=None,
        csv_file=None,
    ):
        """
        Initialize loader with CSV source and partner context.
        """
        super().__init__(partner=partner, api_url=api_url, max_workers=max_workers, is_threadsafe=is_threadsafe)
        self.error_logs = {key: [] for key in COURSE_EDITOR_LOADER_ERROR_LOG_SEQUENCE}
        self.reader = self.initialize_csv_reader(csv_path, csv_file)
        self.ingestion_summary = {
            'total_count': len(self.reader),
            'success_count': 0,
            'failure_count': 0,
            'errors': [],
        }

    def ingest(self):
        """
        Process each row in the CSV to add or remove course editors.
        """
        logger.info("Starting ingestion of course editor loader.")

        for index, row in enumerate(self.reader, start=1):
            row = self.transform_dict_keys(row)
            missing_fields = self.validate_course_data(row)

            if missing_fields:
                self.log_ingestion_error(
                    CourseEditorIngestionErrors.MISSING_REQUIRED_DATA,
                    CourseEditorIngestionErrorMessages.MISSING_REQUIRED_DATA.format(
                        index=index, missing_fields=missing_fields
                    )
                )
                continue

            user_identifier = row.get('username_or_email')
            course_identifier = row.get('course_key_or_uuid')
            action = row.get('action', '').strip().lower()

            user = self.get_user(user_identifier)
            if not user:
                self.log_ingestion_error(
                    CourseEditorIngestionErrors.USER_NOT_FOUND,
                    CourseEditorIngestionErrorMessages.USER_NOT_FOUND.format(
                        user_identifier=user_identifier, index=index
                    )
                )
                continue

            course = self.get_course(course_identifier)
            if not course:
                self.log_ingestion_error(
                    CourseEditorIngestionErrors.COURSE_NOT_FOUND,
                    CourseEditorIngestionErrorMessages.COURSE_NOT_FOUND.format(
                        course_identifier=course_identifier, index=index
                    )
                )
                continue

            if action == 'add':
                if not set(Organization.user_organizations(user)).intersection(course.authoring_organizations.all()):
                    self.log_ingestion_error(
                        CourseEditorIngestionErrors.USER_ORG_MISMATCH,
                        CourseEditorIngestionErrorMessages.USER_ORG_MISMATCH.format(
                            user_identifier=user_identifier,
                            course_title=course.title,
                            index=index
                        )
                    )
                    continue
                try:
                    _, created = CourseEditor.objects.get_or_create(user=user, course=course)
                    self.ingestion_summary['success_count'] += 1
                    if not created:
                        logger.info(f"[Row {index}] CourseEditor for user '{user.username}' and course "
                                    f"'{course.title}' already exists.")
                except IntegrityError as e:
                    self.log_ingestion_error(
                        CourseEditorIngestionErrors.COURSE_EDITOR_ADD_ERROR,
                        CourseEditorIngestionErrorMessages.COURSE_EDITOR_ADD_ERROR.format(
                            user_identifier=user_identifier,
                            course_title=course.title,
                            index=index,
                            exception=str(e)
                        )
                    )
            elif action == 'remove':
                try:
                    deleted, _ = CourseEditor.objects.filter(user=user, course=course).delete()
                    if deleted:
                        self.ingestion_summary['success_count'] += 1
                    else:
                        raise ValueError("CourseEditor entry does not exist.")
                except (IntegrityError, ValueError) as e:
                    self.log_ingestion_error(
                        CourseEditorIngestionErrors.COURSE_EDITOR_REMOVE_ERROR,
                        CourseEditorIngestionErrorMessages.COURSE_EDITOR_REMOVE_ERROR.format(
                            user_identifier=user_identifier,
                            course_title=course.title,
                            index=index,
                            exception=str(e)
                        )
                    )
            else:
                self.log_ingestion_error(
                    CourseEditorIngestionErrors.UNSUPPORTED_ACTION,
                    CourseEditorIngestionErrorMessages.UNSUPPORTED_ACTION.format(
                        index=index,
                        action=action
                    )
                )

        logger.info("Course editor ingestion complete.")
        logger.info(f"Ingestion Summary: {self.ingestion_summary}")
        self.render_error_logs(self.error_logs, COURSE_EDITOR_LOADER_ERROR_LOG_SEQUENCE)

        return {
            'summary': self.ingestion_summary,
            'errors': self.error_logs,
        }

    def validate_course_data(self, data, course_type=None):
        """
        Check for missing required fields in a CSV row.
        """
        missing = [field for field in self.BASE_REQUIRED_DATA_FIELDS if not data.get(field)]
        return ', '.join(missing) if missing else ''

    @staticmethod
    def get_user(identifier):
        """
        Fetch user by username or email.
        """
        return User.objects.filter(Q(username=identifier) | Q(email=identifier)).first()

    @staticmethod
    def get_course(identifier):
        """Fetch course by UUID or key."""
        try:
            uuid_obj = uuid.UUID(str(identifier))
            query = Q(uuid=uuid_obj)
        except (ValueError, TypeError):
            query = Q(key=identifier)

        return Course.objects.filter_drafts().filter(query).prefetch_related('authoring_organizations').first()

    def register_ingestion_error(self, error_key, error_message):
        """
        Log an ingestion error and increment failure count.
        """
        self.ingestion_summary['failure_count'] += 1
        self.error_logs[error_key].append(error_message)
