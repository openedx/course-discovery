"""
Serializers for learner_pathway app.
"""
from rest_framework import serializers

from course_discovery.apps.learner_pathway import models


class LearnerPathwaySerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathway model.
    """

    class Meta:
        model = models.LearnerPathway
        fields = ('uuid', 'name', )


class LearnerPathwayStepSerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathwayStep model.
    """

    class Meta:
        model = models.LearnerPathwayStep
        fields = ('uuid', 'pathway', )


class LearnerPathwayCourseSerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathwayCourse model.
    """

    class Meta:
        model = models.LearnerPathwayCourse
        fields = ('uuid', 'step', 'course', )


class LearnerPathwayProgramSerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathwayProgram model.
    """

    class Meta:
        model = models.LearnerPathwayProgram
        fields = ('uuid', 'step', 'program', )
