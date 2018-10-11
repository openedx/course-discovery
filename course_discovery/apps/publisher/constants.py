"""
Group names to create publisher user groups.
"""
ADMIN_GROUP_NAME = 'Publisher Admins'
INTERNAL_USER_GROUP_NAME = 'Internal Users'
PARTNER_MANAGER_GROUP_NAME = 'Partner Managers'
PROJECT_COORDINATOR_GROUP_NAME = 'Project Coordinators'
REVIEWER_GROUP_NAME = 'Marketing Reviewers'
PUBLISHER_GROUP_NAME = 'Publishers'
LEGAL_TEAM_GROUP_NAME = 'Legal Team Members'

GENERAL_STAFF_GROUP_NAME = 'General Staff'
PARTNER_SUPPORT_GROUP_NAME = 'Partner Support Members'

# Being used in old migration `0019_create_user_groups`.
PARTNER_COORDINATOR_GROUP_NAME = 'Partner Coordinators'

# Waffle switches
PUBLISHER_CREATE_AUDIT_SEATS_FOR_VERIFIED_COURSE_RUNS = 'publisher_create_audit_seats_for_verified_course_runs'
PUBLISHER_REMOVE_PACING_TYPE_EDITING = 'publisher_remove_pacing_type_editing'
PUBLISHER_REMOVE_START_DATE_EDITING = 'publisher_remove_start_date_editing'
