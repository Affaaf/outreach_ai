from outreach_ai_tasks.celery_service import celery_app
from outreach_app.models import RunningJob, Schedule
from datetime import datetime
from rest_framework.response import Response
from rest_framework import status
from outreach_ai_tasks.celery_task.tasks import sales_force
from django.utils import timezone



@celery_app.task(bind=True, name="schedule_tasks")
def schedule_tasks(self):

    task = RunningJob.objects.last()
    if task is None:
        scheduled = Schedule.objects.last()
        if scheduled:
            
            now = timezone.now()
            task = sales_force.delay()
            task_id = str(task.id)
            job = RunningJob.objects.create(
                task_id = task_id,
                type = "Beat Sales Force",
                status = "RUNNING",
                start_date = now
            )
            job.save()
            return {"task_id": task.id}
        else:
            return {"status": "There is no schedule interval"}
    
    else:
        task_status = task.status
        if task_status == "RUNNING":
            pass
        
        else: 
            scheduled = Schedule.objects.last()
            if scheduled is not None:
                interval = scheduled.interval_days
                start_date = task.start_date
                now = timezone.now()
                days_passed = (now - start_date).days
                if days_passed >= interval:
                    task = sales_force.delay()
                    task_id = str(task.id)
                    job = RunningJob.objects.create(
                        task_id = task_id,
                        status = "RUNNING",
                        type = "Beat Sales Force",
                        start_date = now
                    )
                    job.save()
                    return ({"task_id": task.id})
                else:
                    return ({"Status": "Interval is not reached"})
            else:
                return ({"status":"There is no Schedule Interval"})

        
            
                

    
    
    


