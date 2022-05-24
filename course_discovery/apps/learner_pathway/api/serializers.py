"""
Serializers for learner_pathway app.
"""
from rest_framework import serializers

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.learner_pathway import models


class LearnerPathwayCourseMinimalSerializer(serializers.ModelSerializer):
    """
    Minimal course and coursrun data serializer for LearnerPathwayCourse model.
    """
    key = serializers.CharField(source="course.key")
    course_runs = serializers.SerializerMethodField()

    class Meta:
        model = models.LearnerPathwayCourse
        fields = ('key', 'course_runs')

    def get_course_runs(self, obj):
        return obj.course.course_runs.filter(status=CourseRunStatus.Published).values('key')


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


class LearnerPathwayProgramMinimalSerializer(serializers.ModelSerializer):
    """
    Minimal data serializer for LearnerPathwayProgram model.
    """
    uuid = serializers.CharField(source="program.uuid")

    class Meta:
        model = models.LearnerPathwayProgram
        fields = ('uuid',)


class LearnerPathwayProgramSerializer(LearnerPathwayProgramMinimalSerializer):
    """
    Serializer for LearnerPathwayProgram model.
    """
    uuid = serializers.CharField(source="program.uuid")
    title = serializers.CharField(source="program.title")
    short_description = serializers.CharField(source="program.subtitle")
    content_type = serializers.CharField(source="NODE_TYPE")
    card_image_url = serializers.SerializerMethodField()

    class Meta(LearnerPathwayProgramMinimalSerializer.Meta):
        model = models.LearnerPathwayProgram
        fields = LearnerPathwayProgramMinimalSerializer.Meta.fields + (
            'uuid',
            'title',
            'short_description',
            'card_image_url',
            'content_type'
        )

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


class LearnerPathwayStepMinimalSerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathwayStep model.
    """
    courses = LearnerPathwayCourseMinimalSerializer(source="learnerpathwaycourse_set", many=True)
    programs = LearnerPathwayProgramMinimalSerializer(source="learnerpathwayprogram_set", many=True)

    class Meta:
        model = models.LearnerPathwayStep
        fields = ('uuid', 'min_requirement', 'courses', 'programs',)


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


class LearnerPathwayMinimalSerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerPathway Snapshot data.
    """
    steps = LearnerPathwayStepMinimalSerializer(many=True)

    class Meta:
        model = models.LearnerPathway
        fields = ('id', 'uuid', 'status', 'steps',)
