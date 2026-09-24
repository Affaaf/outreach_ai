from django.urls import path, include
from .views import EmailGeneration, Login, RunningTasks, SalesforceEnrichment, UpdateScheduleIntervals, ScheduleIntervals, TerminateRunningTask

urlpatterns = [

    path('/email-generation', EmailGeneration.as_view()),
    path('/login', Login.as_view()),
    path('/jobs', RunningTasks.as_view()),
    path('/start', SalesforceEnrichment.as_view()),
    path('/update-intervals/<int:interval_id>',UpdateScheduleIntervals.as_view()),
    path('/intervals',ScheduleIntervals.as_view()),
    path('/terminate',TerminateRunningTask.as_view()),

]
