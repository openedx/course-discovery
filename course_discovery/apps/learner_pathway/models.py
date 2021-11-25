"""
Model definitions for the learner pathway app.
"""
from abc import ABCMeta, abstractmethod
from uuid import uuid4

from django.db import models
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.utils import get_course_run_estimated_hours
from taxonomy.utils import get_whitelisted_serialized_skills


class AbstractModelMeta(ABCMeta, type(models.Model)):
    pass


class LearnerPathwayNode(models.Model, metaclass=AbstractModelMeta):
    """
    Abstract model for learner pathway related models.
    """
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))

    class Meta:
        abstract = True

    @abstractmethod
    def get_estimated_time_of_completion(self) -> str:
        """
        Subclasses must implement this method to calculate and return the estimated time of completion of the node.
        """

    @abstractmethod
    def get_skills(self) -> [str]:
        """
        Subclasses must implement this method to calculate and return the list of aggregated skills.
        """


class LearnerPathwayProgram(LearnerPathwayNode):

    title = models.CharField(max_length=255)

    def get_estimated_time_of_completion(self) -> str:
        """
        Returns the average estimated work hours to complete the course run.
        """
        program_estimated_time_of_completion = 0
        for learner_pathway_course in self.courses:
            program_estimated_time_of_completion += learner_pathway_course.get_course_run_estimated_hours() or 0

        return program_estimated_time_of_completion

    def get_skills(self) -> [str]:
        """
        Return list of dicts where each dict contain skill name and skill description.
        """
        program_skills = []
        for learner_pathway_course in self.courses:
            program_skills += learner_pathway_course.get_skills()

        return program_skills


class LearnerPathwayCourse(LearnerPathwayNode):

    course = models.OneToOneField(Course, on_delete=models.CASCADE)
    program = models.ForeignKey(LearnerPathwayProgram, on_delete=models.CASCADE, related_name='courses')

    def get_estimated_time_of_completion(self) -> str:
        """
        Returns the average estimated work hours to complete the course run.
        """
        active_course_runs = self.course.active_course_runs
        if self.course.advertised_course_run:
            advertised_course_run_uuid = self.course.advertised_course_run.uuid
            for course_run in active_course_runs:
                if course_run.uuid == advertised_course_run_uuid:
                    return get_course_run_estimated_hours(course_run)

    def get_skills(self) -> [str]:
        """
        Return list of dicts where each dict contain skill name and skill description.
        """
        return get_whitelisted_serialized_skills(self.course.key)