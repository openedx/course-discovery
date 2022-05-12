"""
Serializers for learner_pathway app.
"""
from rest_framework import serializers

from course_discovery.apps.learner_pathway import models


class LearnerPathwayCourseSerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathwayCourse model.
    """
    key = serializers.CharField(source="course.key")
    title = serializers.CharField(source="course.title")
    short_description = serializers.CharField(source="course.short_description")
    content_type = serializers.CharField(source="NODE_TYPE")
    card_image_url = serializers.CharField(source="course.image_url")

    class Meta:
        model = models.LearnerPathwayCourse
        fields = ('key', 'title', 'short_description', 'card_image_url', 'content_type')


class LearnerPathwayProgramSerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathwayProgram model.
    """
    uuid = serializers.CharField(source="program.uuid")
    title = serializers.CharField(source="program.title")
    short_description = serializers.CharField(source="program.subtitle")
    content_type = serializers.CharField(source="NODE_TYPE")
    card_image_url = serializers.SerializerMethodField()

    class Meta:
        model = models.LearnerPathwayProgram
        fields = ('uuid', 'title', 'short_description', 'card_image_url', 'content_type')

    def get_card_image_url(self, step):
        program = step.program
        if program.card_image:
            return program.card_image.url
        return program.card_image_url


class LearnerPathwayBlockSerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathwayBlock model.
    """

    class Meta:
        model = models.LearnerPathwayBlock
        fields = ('uuid', 'step', 'course', 'block_id')


class LearnerPathwayStepSerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathwayStep model.
    """
    courses = LearnerPathwayCourseSerializer(source="learnerpathwaycourse_set", many=True)
    programs = LearnerPathwayProgramSerializer(source="learnerpathwayprogram_set", many=True)

    class Meta:
        model = models.LearnerPathwayStep
        fields = ('uuid', 'min_requirement', 'courses', 'programs',)


class LearnerPathwaySerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathway model.
    """
    steps = LearnerPathwayStepSerializer(many=True)

    class Meta:
        model = models.LearnerPathway
        fields = ('id', 'uuid', 'title', 'status', 'banner_image', 'card_image', 'overview', 'steps',)
