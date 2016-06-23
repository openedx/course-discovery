import logging

from course_discovery.apps.core.data_loaders import AbstractDataLoader
from course_discovery.apps.course_metadata.models import Seat
from course_discovery.apps.programs.models import Program, CourseRequirement

logger = logging.getLogger(__name__)


class ProgramsApiDataLoader(AbstractDataLoader):
    """ Loads programs from the Programs API. """

    def ingest(self):
        client = self.api_client
        count = None
        page = 1

        logger.info('Refreshing Programs from %s...', self.api_url)

        while page:
            response = client.programs().get(page=page, page_size=self.PAGE_SIZE)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d programs...', len(results))

            if response['next']:
                page += 1
            else:
                page = None

            for program in results:
                program = self.clean_strings(program)
                self.update_programs(program)

        logger.info('Retrieved %d programs from %s.', count, self.api_url)

    def update_programs(self, program):
        defaults = {
            'name': program['name'],
            'subtitle': program['subtitle'],
            'category': program['category'],
            'status': program['status'],
            'marketing_slug': program['marketing_slug'],
        }
        program = Program.objects.update_or_create(external_id=program['id'], defaults=defaults)
        self.update_program_course_requirements(program['course_codes'], program)

    def update_program_course_requirements(self, course_codes, program):
        course_requirements = []
        for course_code in course_codes:
            defaults = {
                'display_name': course_code['display_name'],
            }
            course_requirement = CourseRequirement.objects.update_or_create(
                key=course_code['key'], defaults=defaults
            )
            course_requirements.append(course_requirement)
            self.associate_seats(course_code['run_modes'], course_requirement)

        program.course_requirements = course_requirements

    def associate_seats(self, run_modes, course_requirement):
        seats = []
        for run_mode in run_modes:
            mode_slug = run_mode['mode_slug']
            course_run_key = run_mode['course_key']
            seat = Seat.objects.filter(type=mode_slug, course_run__key=course_run_key).first()
            if seat:
                seats.append(seat)
            else:
                logger.error(
                    'Seat not found with type [%s] and course_run key [%s].', mode_slug, course_run_key
                )

        course_requirement.seats = seats
