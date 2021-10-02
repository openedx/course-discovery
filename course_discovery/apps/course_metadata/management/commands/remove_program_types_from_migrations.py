"""
Remove migration-borne program type records (e.g. to make way for fixture-loaded data)
"""
from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.models import ProgramType

# from migration code
# see 0191_add_microbachelors_program_type and 0090_degree_curriculum_reset
MB_PROGRAM_TYPES = ("microbachelors",)
M_PROGRAM_TYPES = ("masters",)


class Command(BaseCommand):
    """
    Remove ProgramTypes with slugs matching those created by migrations
    """
    # pylint: disable=unused-argument
    def handle(self, *args, **kwargs):
        program_types = ProgramType.objects.filter(slug__in=MB_PROGRAM_TYPES + M_PROGRAM_TYPES)
        program_types.delete()
