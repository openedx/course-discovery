"""
Tests for custom model code in the programs app.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from course_discovery.apps.programs import models
from course_discovery.apps.programs.constants import ProgramStatus, ProgramCategory
from course_discovery.apps.programs.models import Program
from course_discovery.apps.programs.tests import factories


class TestProgram(TestCase):
    """Tests of the Program model."""
    def test_empty_marketing_slug(self):
        """Verify that multiple Programs can be saved with an empty marketing slug."""
        for i in range(2):
            Program.objects.create(
                name='test-program-{}'.format(i),
                external_id=i,
                subtitle='test-subtitle',
                category=ProgramCategory.XSERIES,
                status=ProgramStatus.UNPUBLISHED,
                marketing_slug='',
            )

            # Verify that the program was created successfully.
            self.assertEqual(Program.objects.count(), i + 1)

    def test_marketing_slug_uniqueness(self):
        """Verify that multiple Programs can share a non-empty marketing slug."""
        kwargs = {
            'name': 'primary-program',
            'external_id': 0,
            'subtitle': 'test-subtitle',
            'category': ProgramCategory.XSERIES,
            'status': ProgramStatus.UNPUBLISHED,
            'marketing_slug': 'test-slug',
        }

        Program.objects.create(**kwargs)

        kwargs['name'] = 'alternate-program',
        Program.objects.create(**kwargs)

        self.assertEqual(len(Program.objects.filter(marketing_slug='test-slug')), 2)

    def test_xseries_activation(self):
        """Verify that an XSeries Program can't be activated with an empty marketing slug."""
        with self.assertRaises(ValidationError) as context:
            Program.objects.create(
                name='test-program',
                external_id=0,
                subtitle='test-subtitle',
                category=ProgramCategory.XSERIES,
                status=ProgramStatus.ACTIVE,
                marketing_slug='',
            )

        self.assertEqual('Active XSeries Programs must have a valid marketing slug.', str(context.exception.message))


class TestProgramOrganization(TestCase):
    """
    Tests for the ProgramOrganization model.
    """

    def test_one_org_max(self):
        """
        Ensure that a Program cannot be associated with more than one organization
        (the relationship is modeled as m2m, but initially, we will only allow
        one organization to be associated).
        """
        program = factories.ProgramFactory.create()
        org = factories.OrganizationFactory.create()
        orig_pgm_org = factories.ProgramOrganizationFactory.create(program=program, organization=org)

        # try to add a second association
        org2 = factories.OrganizationFactory.create()
        pgm_org = factories.ProgramOrganizationFactory.build(program=program, organization=org2)
        with self.assertRaises(ValidationError) as context:
            pgm_org.save()
        self.assertEqual('Cannot associate multiple organizations with a program.', str(context.exception.message))

        # make sure it works to update an existing association
        orig_pgm_org.organization = org2
        orig_pgm_org.save()


class TestProgramCourseRequirement(TestCase):
    """
    Tests for the ProgramCourseRequirement model.
    """

    def setUp(self):
        """
        DRY object initializations.
        """
        self.program = factories.ProgramFactory.create()
        self.org = factories.OrganizationFactory.create()
        factories.ProgramOrganizationFactory.create(program=self.program, organization=self.org)
        super(TestProgramCourseRequirement, self).setUp()

    def test_one_program_max(self):
        """
        Ensure that a CourseRequirement cannot be associated with more than one program
        (the relationship is modeled as m2m, but initially, we will only allow
        one organization to be associated).
        """
        course_requirement = factories.CourseRequirementFactory.create(organization=self.org)
        orig_pgm_course = factories.ProgramCourseRequirementFactory.create(
            program=self.program, course_requirement=course_requirement
        )

        program2 = factories.ProgramFactory.create()
        pgm_course = factories.ProgramCourseRequirementFactory.build(
            program=program2, course_requirement=course_requirement
        )
        with self.assertRaises(ValidationError) as context:
            pgm_course.save()
        self.assertEqual(
            'Cannot associate multiple programs with a course requirement.', str(context.exception.message)
        )

        # make sure it works to reassign the existing association to the other program
        orig_pgm_course.program = program2
        orig_pgm_course.save()

    def test_position(self):
        """
        Ensure that new ProgramCourseRequirement rows get automatically assigned an automatically incrementing
        position, and that results are returned by default sorted by ascending position.
        """
        for _ in range(3):
            course_requirement = factories.CourseRequirementFactory.create(organization=self.org)
            factories.ProgramCourseRequirementFactory.create(
                program=self.program, course_requirement=course_requirement
            )

        res = models.ProgramCourseRequirement.objects.filter(program=self.program)
        self.assertEqual([1, 2, 3], [pgm_course.position for pgm_course in res])

        # shuffle positions.  not worrying about gaps for now.
        res[0].position = 10
        res[0].save()
        # re-fetch, expecting reordering.
        res = models.ProgramCourseRequirement.objects.filter(program=self.program)
        self.assertEqual([2, 3, 10], [pgm_course.position for pgm_course in res])

    def test_organization(self):
        """
        Ensure that it is not allowed to associate a course requirement with a program
        when the course requirement's organization does not match one of the program's
        organizations.
        """
        org2 = factories.OrganizationFactory.create()
        course_requirement = factories.CourseRequirementFactory.create(organization=org2)
        pgm_course = factories.ProgramCourseRequirementFactory.build(
            program=self.program, course_requirement=course_requirement
        )
        with self.assertRaises(ValidationError) as context:
            pgm_course.save()
        self.assertEqual(
            'Course requirement must be offered by the same organization offering the program.',
            str(context.exception.message)
        )
