from rest_framework import serializers
from .models import RunningJob, Schedule

from .models import User



class SigninSerializer(serializers.ModelSerializer):
    password = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['username', 'password']



class RunningJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = RunningJob
        fields = ['task_id', 'status','type', 'start_date']

class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model =  Schedule
        fields = "__all__"


class ScheduleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = ['interval_days'] 