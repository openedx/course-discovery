"""
Various constants across different data loaders.
"""


class CSVIngestionErrors:
    """
    Enumerate errors possible during CSVLoader ingestion.
    """
    MISSING_ORGANIZATION = 'MISSING_ORGANIZATION'
    MISSING_COURSE_TYPE = 'MISSING_COURSE_TYPE'
    MISSING_COURSE_RUN_TYPE = 'MISSING_COURSE_RUN_TYPE'
    MISSING_REQUIRED_DATA = 'MISSING_REQUIRED_DATA'
    COURSE_CREATE_ERROR = 'COURSE_CREATE_ERROR'
    IMAGE_DOWNLOAD_FAILURE = 'IMAGE_DOWNLOAD_FAILURE'
    LOGO_IMAGE_DOWNLOAD_FAILURE = 'LOGO_IMAGE_DOWNLOAD_FAILURE'
    COURSE_UPDATE_ERROR = 'COURSE_UPDATE_ERROR'
    COURSE_RUN_UPDATE_ERROR = 'COURSE_RUN_UPDATE_ERROR'


class CSVIngestionErrorMessages:
    """
    String templates for various CSV ingestion error messages.
    """
    MISSING_ORGANIZATION = '[MISSING_ORGANIZATION] Unable to locate partner organization with key {org_key} ' \
                           'for the course titled {course_title}.'

    MISSING_COURSE_TYPE = '[MISSING_COURSE_TYPE] Unable to find the course enrollment track "{course_type}"' \
                          ' for the course {course_title}'

    MISSING_COURSE_RUN_TYPE = '[MISSING_COURSE_RUN_TYPE] Unable to find the course run enrollment track' \
                              ' "{course_run_type}" for the course {course_title}'

    MISSING_REQUIRED_DATA = '[MISSING_REQUIRED_DATA] Course {course_title} is missing the required data for ' \
                            'ingestion. The missing data elements are "{missing_data}"'

    COURSE_CREATE_ERROR = '[COURSE_CREATE_ERROR] Unable to create course {course_title} in the system. The ingestion' \
                          'failed with the exception: {exception_message}'

    COURSE_UPDATE_ERROR = '[COURSE_UPDATE_ERROR] Unable to update course {course_title} in the system. The update' \
                          'failed with the exception: {exception_message}'

    COURSE_RUN_UPDATE_ERROR = '[COURSE_RUN_UPDATE_ERROR] Unable to update course run of the course {course_title} ' \
                              'in the system. The update failed with the exception: {exception_message}'

    IMAGE_DOWNLOAD_FAILURE = '[IMAGE_DOWNLOAD_FAILURE] The course image download failed for the course' \
                             ' {course_title}.'

    LOGO_IMAGE_DOWNLOAD_FAILURE = '[LOGO_IMAGE_DOWNLOAD_FAILURE] The logo image download failed for the course ' \
                                  '{course_title}.'
