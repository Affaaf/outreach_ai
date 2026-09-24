from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    username = models.CharField(max_length=255, null=False, blank=False, unique=True)
    password = models.CharField(max_length=30, null=False, blank=False)



class Schedule(models.Model):
    interval_days = models.PositiveIntegerField(help_text="Interval in days")
   
    def __str__(self):
        return f"Interval: {self.interval_days} days"



class RunningJob(models.Model):
    task_id = models.CharField(max_length=100 ,null=True, blank=True)
    status = models.CharField(max_length=20, null=True, blank=True)
    type = models.CharField(max_length=20, null=True, blank=True)
    start_date = models.DateTimeField( null=True, blank=True)

    def __str__(self):
        return f"{self.task_id} - {self.start_date} - {self.status}"
    