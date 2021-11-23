"""
Model definitions for the learner pathway app.
"""
from abc import ABCMeta, abstractmethod
from uuid import uuid4

from django.db import models
from django.utils.translation import ugettext_lazy as _

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
        return LearnerPathwayNode.get_node(self,uuid)

    def remove_node(self,uuid):
        node = self.get_node(uuid)
        if node:
            node.delete()


    def get_estimated_time_of_completion(self):
        return sum([node.get_estimated_time_of_completion() for node in self.get_nodes()])

    def get_skills(self):
        skills = set()
        for node in self.get_nodes():
            skills.update(node.get_skills())
        return list(skills)


