from rest_framework import serializers

from .models import Project, Milestone, Task, BudgetEntry, next_number


class MilestoneSerializer(serializers.ModelSerializer):
    project_code = serializers.CharField(source='project.project_code', read_only=True)

    class Meta:
        model = Milestone
        fields = '__all__'
        extra_kwargs = {'project': {'required': False}}


class TaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True, default=None)
    milestone_title = serializers.CharField(source='milestone.title', read_only=True, default=None)
    project_code = serializers.CharField(source='project.project_code', read_only=True)

    class Meta:
        model = Task
        fields = '__all__'
        extra_kwargs = {'project': {'required': False}}


class BudgetEntrySerializer(serializers.ModelSerializer):
    project_code = serializers.CharField(source='project.project_code', read_only=True)
    variance = serializers.SerializerMethodField()

    class Meta:
        model = BudgetEntry
        fields = '__all__'
        extra_kwargs = {'project': {'required': False}}

    def get_variance(self, obj):
        return float((obj.budgeted_amount or 0) - (obj.actual_amount or 0))


class ProjectSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True, default=None)
    team_members_detail = serializers.SerializerMethodField()
    milestone_count = serializers.SerializerMethodField()
    task_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['project_code']

    def get_team_members_detail(self, obj):
        return [{'id': u.id, 'name': u.get_full_name() or u.username} for u in obj.team_members.all()]

    def get_milestone_count(self, obj):
        return obj.milestones.count()

    def get_task_count(self, obj):
        return obj.tasks.count()

    def create(self, validated_data):
        validated_data['project_code'] = next_number(Project, 'project_code', 'PRJ')
        team_members = validated_data.pop('team_members', [])
        project = super().create(validated_data)
        if team_members:
            project.team_members.set(team_members)
        return project
