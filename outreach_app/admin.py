from django.contrib import admin
from .models import User, Schedule, RunningJob
# Register your models here.

class UserAdmin(admin.ModelAdmin):
    fields = ("username","password")
    list_display = ("username","password")

admin.site.register(User,UserAdmin)


class ScheduleAdmin(admin.ModelAdmin):
    fields = ("interval_days",)
    list_display = ("interval_days",)

admin.site.register(Schedule, ScheduleAdmin)


class RunningjobAdmin(admin.ModelAdmin):
    fields = ("task_id", "status","type", "start_date",)
    list_display = ("task_id", "status","type", "start_date",)

admin.site.register(RunningJob, RunningjobAdmin)