"""
Model definitions for the learner pathway app.
"""
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from uuid import uuid4

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from opaque_keys.edx.django.models import UsageKeyField
from stdimage.models import StdImageField
from taxonomy.choices import ProductTypes
from taxonomy.utils import get_whitelisted_serialized_skills

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import Course, Program
from course_discovery.apps.course_metadata.utils import UploadToFieldNamePath
from course_discovery.apps.learner_pathway import constants
from course_discovery.apps.learner_pathway.choices import PathwayStatus
from course_discovery.apps.learner_pathway.utils import avg, get_advertised_course_run_estimated_hours


class AbstractModelMeta(ABCMeta, type(models.Model)):
    pass


class LearnerPathwayNode(models.Model, metaclass=AbstractModelMeta):
    """
    Abstract model for learner pathway related models.
    """
    step = models.ForeignKey('LearnerPathwayStep', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))

    class Meta:
        abstract = True

    @abstractmethod
    def get_estimated_time_of_completion(self) -> int:
        """
        Subclasses must implement this method to calculate and return the estimated time of completion of the node.
        """

    @abstractmethod
    def get_skills(self) -> [str]:
        """
        Subclasses must implement this method to calculate and return the list of aggregated skills.
        """

    @classmethod
    def get_nodes(cls, step):
        nodes = []
        for node_class in cls.get_subclasses():
            nodes += node_class.objects.filter(step=step).all()
        return nodes

    @classmethod
    def get_node_type_count(cls, step):
        node_type_count = defaultdict(int)
        for node_class in cls.get_subclasses():
            node_type_count[node_class.NODE_TYPE] = node_class.objects.filter(step=step).count()

        return dict(node_type_count)

    @classmethod
    def get_subclasses(cls):
        return cls.__subclasses__()

    @classmethod
    def get_node(cls, uuid):
        for node_class in cls.get_subclasses():
            node = node_class.objects.filter(uuid=uuid).first()
            if node:
                return node
        return None


class LearnerPathway(TimeStampedModel):
    """
    Top level model for learner pathway.
    """
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))
    title = models.CharField(max_length=255, null=False, blank=False, help_text=_('Title of the learner pathway.'))
    partner = models.ForeignKey(Partner, models.CASCADE, null=True, blank=False)
    visible_via_association = models.BooleanField(
        default=True, help_text=_('Course/Program associated pathways also appear in search results')
    )
    status = models.CharField(
        help_text=_('The active/inactive status of this Pathway.'),
        max_length=16, default=PathwayStatus.Inactive,
        choices=PathwayStatus.choices
    )
    banner_image = StdImageField(
        upload_to=UploadToFieldNamePath(populate_from='uuid', path='media/learner_pathway/banner_images'),
        blank=True,
        null=True,
        variations={
            'large': (1440, 480),
            'medium': (726, 242),
            'small': (435, 145),
            'x-small': (348, 116),
        },
        help_text='image that will be displayed on learner pathway modal',
    )
    card_image = StdImageField(
        upload_to=UploadToFieldNamePath(populate_from='uuid', path='media/learner_pathway/card_images'),
        blank=True,
        null=True,
        variations={
            'card': (378, 225),
        },
        help_text='image that will be displayed on learner pathway cards',
    )
    overview = models.TextField(blank=True)

    class Meta:
        verbose_name = _('Learner Pathway')
        verbose_name_plural = _('Learner Pathways')

    @property
    def time_of_completion(self) -> float:
        """
        Return the aggregated time to completion.
        """
        completion_time = 0
        for step in self.steps.all():
            completion_time += avg(step.get_estimated_time_of_completion())
        return completion_time

    @property
    def skills(self) -> [str]:
        """
        Return the list of aggregated skills.
        """
        skills = []
        for step in self.steps.all():
            step_skills = step.get_skills()
            for step_skill in step_skills:
                if step_skill not in skills:
                    skills.append(step_skill)
        return skills

    def __str__(self):
        """
        Create a human-readable string representation of the object.
        """
        return f'{self.title} - {self.uuid}'

    def __repr__(self):
        """
        Return string representation.
        """
        return f'<LearnerPathway title="{self.title}" uuid="{self.uuid}">'


class LearnerPathwayStep(models.Model):
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))
    pathway = models.ForeignKey(LearnerPathway, related_name='steps', on_delete=models.CASCADE)
    min_requirement = models.PositiveSmallIntegerField(
        default=1,
        validators=[
            MinValueValidator(1)
        ],
        help_text=_('Minimum number of nodes to complete this step of the pathway')
    )

    class Meta:
        verbose_name = _('Learner Pathway Step')
        verbose_name_plural = _('Learner Pathway Steps')

    def get_nodes(self):
        return LearnerPathwayNode.get_nodes(self)

    def get_node(self, uuid):
        return LearnerPathwayNode.get_node(uuid)

    def remove_node(self, uuid):
        node = self.get_node(uuid)
        if node:
            node.delete()

    def get_node_type_count(self):
        return LearnerPathwayNode.get_node_type_count(self)

    def get_estimated_time_of_completion(self) -> (int, int):
        """
        Get a range of estimated time of completion.

        Returns:
            (tuple<int, int>): A tuple containing the min and max of estimated time of completion.
        """
        estimated_completion_times_of_nodes = sorted(
            [node.get_estimated_time_of_completion() for node in self.get_nodes()]
        )
        # get the lowest and largest estimated time of completion and return that as a tuple in respective order.
        # To get the lowest estimated time of completion by getting the N smallest numbers, where N is `min_requirement`
        # and sum them up to get lowest estimated time of completion.
        # To get the highest estimated time of completion by getting the N largest numbers, where N is `min_requirement`
        # and sum them up to get highest estimated time of completion.
        return (
            sum(estimated_completion_times_of_nodes[:self.min_requirement]),
            sum(estimated_completion_times_of_nodes[-self.min_requirement:]),
        )

    def get_skills(self):
        already_added_skills = set()
        skills_aggregated = []
        for node in self.get_nodes():
            skills = node.get_skills()
            for skill in skills:
                if skill['name'] not in already_added_skills:
                    skills_aggregated.append(skill)
                    already_added_skills.add(skill['name'])
        return skills_aggregated

    def __str__(self):
        """
        Create a human-readable string representation of the object.
        """
        return f'UUID: {self.uuid}, Pathway: {self.pathway.title}'

    def __repr__(self):
        """
        Return string representation.
        """
        return f'<LearnerPathwayStep pathway="{self.pathway.uuid}" uuid="{self.uuid}">'


class LearnerPathwayCourse(LearnerPathwayNode):

    NODE_TYPE = constants.NODE_TYPE_COURSE

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='learner_pathway_courses')

    class Meta:
        verbose_name = _('Learner Pathway Course')
        verbose_name_plural = _('Learner Pathway Courses')
        unique_together = (
            ('step', 'course'),
        )

    def get_estimated_time_of_completion(self) -> int:
        """
        Returns the average estimated work hours to complete the course run.
        """
        return get_advertised_course_run_estimated_hours(self.course) or 0

    def get_skills(self) -> [str]:
        """
        Return list of dicts where each dict contain skill name and skill description.
        """
        return get_whitelisted_serialized_skills(self.course.key, product_type=ProductTypes.Course)

    def __str__(self):
        """
        Create a human-readable string representation of the object.
        """
        return f'UUID: {self.uuid}, Course: {self.course.title}'

    def __repr__(self):
        """
        Return string representation.
        """
        return f'<LearnerPathwayCourse course="{self.course.key}" uuid="{self.uuid}">'


class LearnerPathwayProgram(LearnerPathwayNode):

    NODE_TYPE = constants.NODE_TYPE_PROGRAM

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='learner_pathway_programs')

    class Meta:
        verbose_name = _('Learner Pathway Program')
        verbose_name_plural = _('Learner Pathway Programs')
        unique_together = (
            ('step', 'program'),
        )

    def get_estimated_time_of_completion(self) -> int:
        """
        Returns the sum of estimated work hours to complete the course run for all program courses.
        """
        program_estimated_time_of_completion = 0
        for program_course in self.program.courses.all():
            program_estimated_time_of_completion += get_advertised_course_run_estimated_hours(program_course) or 0

        return program_estimated_time_of_completion

    def get_skills(self) -> [str]:
        """
        Return list of dicts where each dict contain skill name and skill description.
        """
        program_skills = []
        for program_course in self.program.courses.all():
            program_skills += get_whitelisted_serialized_skills(program_course.key, product_type=ProductTypes.Course)

        return program_skills

    def get_linked_courses_and_course_runs(self) -> [dict]:
        """
        Returns list of dict where each dict contains a course key linked with program and all its course runs
        """
        courses = []
        for course in self.program.courses.all():
            course_runs = list(course.course_runs.filter(status=CourseRunStatus.Published).values('key'))
            courses.append({"key": course.key, "course_runs": course_runs})
        return courses

    def __str__(self):
        """
        Create a human-readable string representation of the object.
        """
        return f'UUID: {self.uuid}, Program: {self.program.title}'

    def __repr__(self):
        """
        Return string representation.
        """
        return f'<LearnerPathwayProgram program="{self.program.uuid}" uuid="{self.uuid}">'


class LearnerPathwayBlock(LearnerPathwayNode):
    """
    Mode for storing course block information from a learner pathway.
    """
    NODE_TYPE = constants.NODE_TYPE_BLOCK

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='learner_pathway_blocks')
    block_id = UsageKeyField(max_length=255)

    def get_estimated_time_of_completion(self) -> int:
        """
        Returns the average estimated work hours to complete the course run.
        """
        return 0

    def get_skills(self) -> [str]:
        """
        Return list of dicts where each dict contain skill name and skill description.
        """
        return get_whitelisted_serialized_skills(self.course.key, product_type=ProductTypes.Course)

    def __str__(self):
        """
        Create a human-readable string representation of the object.
        """
        return f'UUID: {self.uuid}, Course: {self.course.title}, Block: {self.block_id}'

    def __repr__(self):
        """
        Return string representation.
        """
        return f'<LearnerPathwayCourse course="{self.course.key}" uuid="{self.uuid}" block= "{self.block_id}">'
