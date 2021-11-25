"""
Model definitions for the learner pathway app.
"""
from abc import ABCMeta, abstractmethod
from uuid import uuid4

from django.db import models
from django.utils.translation import ugettext_lazy as _
from taxonomy.utils import get_whitelisted_serialized_skills

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.course_metadata.utils import get_course_run_estimated_hours


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
    def get_estimated_time_of_completion(self) -> str:
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
    def get_subclasses(cls):
        return cls.__subclasses__()

    @classmethod
    def get_node(cls, uuid):
        for node_class in cls.get_subclasses():
            node = node_class.objects.filter(uuid=uuid).first()
            if node:
                return node
        return None


class LearnerPathwayStep(models.Model):
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True, verbose_name=_('UUID'))

    def get_nodes(self):
        return LearnerPathwayNode.get_nodes(self)

    def get_node(self, uuid):
        return LearnerPathwayNode.get_node(uuid)

    def remove_node(self, uuid):
        node = self.get_node(uuid)
        if node:
            node.delete()

    def get_estimated_time_of_completion(self):
        return sum([node.get_estimated_time_of_completion() for node in self.get_nodes()])

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


class LearnerPathwayCourse(LearnerPathwayNode):

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='learner_pathway_courses')

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

        return None

    def get_skills(self) -> [str]:
        """
        Return list of dicts where each dict contain skill name and skill description.
        """
        return get_whitelisted_serialized_skills(self.course.key)
