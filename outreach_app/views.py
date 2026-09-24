from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate, login
from rest_framework_simplejwt.tokens import RefreshToken
from outreach_ai_tasks.celery_task.tasks import originate,sales_force
from outreach_app.search import Search
from outreach_app.utils import Utils
from outreach_app.zoom_info import ZoomInfo
from .models import RunningJob,Schedule
from .serializers import RunningJobSerializer, ScheduleSerializer, ScheduleUpdateSerializer
from rest_framework.authentication import TokenAuthentication
from celery.result import AsyncResult 
from django.utils import timezone
from outreach_ai_tasks.celery_service import celery_app
from rest_framework import status as drf_status



class EmailGeneration(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        last_task = RunningJob.objects.last()
        if last_task:
            status = last_task.status
           
            if status == "RUNNING":
                return Response({"message": "Previous task is still running"}, status=drf_status.HTTP_400_BAD_REQUEST)
            else:
                work_sheet_name = request.data.get("work_sheet_name")
                company_sheet_name = request.data.get("company_sheet_name")
                contact_sheet_name = request.data.get("contact_sheet_name")
                input_sheet_url = request.data.get("input_sheet_url")
                output_sheet_url = request.data.get("output_sheet_url")
                task = originate.delay(work_sheet_name, company_sheet_name, contact_sheet_name, input_sheet_url, output_sheet_url)

                current_datetime = timezone.now()
                task_id = str(task.id)

                job = RunningJob.objects.create(
                    task_id = task_id,
                    status = "RUNNING",
                    type = "Email Generation",
                    start_date = current_datetime
                )
                job.save()

                response_data ={
                    "task_id": task.id,
                    "status": "RUNNING",
                    "start_date": current_datetime
                }
                return Response(response_data, status=drf_status.HTTP_200_OK)
        
        else:
            work_sheet_name = request.data.get("work_sheet_name")
            company_sheet_name = request.data.get("company_sheet_name")
            contact_sheet_name = request.data.get("contact_sheet_name")
            input_sheet_url = request.data.get("input_sheet_url")
            output_sheet_url = request.data.get("output_sheet_url")
            task = originate.delay(work_sheet_name, company_sheet_name, contact_sheet_name, input_sheet_url, output_sheet_url)

            current_datetime = timezone.now()
            task_id = str(task.id)

            job = RunningJob.objects.create(
                task_id = task_id,
                status = "RUNNING",
                type = "Email Generation",
                start_date = current_datetime
            )
            job.save()

            response_data ={
                "task_id": task.id,
                "status": "RUNNING",
                "start_date": current_datetime
            }
            return Response(response_data, status=drf_status.HTTP_200_OK)
    


class Login(APIView):

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        
        user = authenticate(request, username=username, password=password)

        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    

class RunningTasks(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tasks = RunningJob.objects.all()
        serializer = RunningJobSerializer(tasks, many=True)
        return Response(serializer.data)



class ScheduleIntervals(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ):
        schedule_intervals = Schedule.objects.all()
        if not schedule_intervals:
            return Response({"message": "Schedule not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ScheduleSerializer(schedule_intervals, many=True)
        return Response(serializer.data)
    


class UpdateScheduleIntervals(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, interval_id):
        schedule = Schedule.objects.filter(pk=interval_id).first()

        if not schedule:
            return Response({"message": "There is no Schedule Interval"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ScheduleUpdateSerializer(schedule, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        

class SalesforceEnrichment(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        last_task = RunningJob.objects.last()
        if last_task:
            status = last_task.status
           
            if status == "RUNNING":
                return Response({"message": "Previous task is still running"}, status=drf_status.HTTP_400_BAD_REQUEST)
            else:
                current_datetime = timezone.now()
                task = sales_force.delay()
                task_id = str(task.id)
                job = RunningJob.objects.create(
                    task_id = task_id,
                    status = "RUNNING",
                    type = "Sales Force",
                    start_date = current_datetime
                    
                )
                job.save()
                response_data = {
                "task_id": task.id,
                "status": "RUNNING",
                "start_date": current_datetime
                }
                return Response(response_data, status=drf_status.HTTP_200_OK)
            
        else:
            current_datetime = timezone.now()
            task = sales_force.delay()
            task_id = str(task.id)
            job = RunningJob.objects.create(
                task_id = task_id,
                status = "RUNNING",
                type = "Sales Force",
                start_date = current_datetime
            )
            job.save()

            response_data = {
                "task_id": task.id,
                "status": "RUNNING",
                "start_date": current_datetime
            }
            return Response(response_data, status.HTTP_200_OK)



class TerminateRunningTask(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_id = request.data.get("task_id")
        if not task_id:
            return Response({"response": "Task ID is empty or invalid"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = AsyncResult(task_id)
            task = RunningJob.objects.filter(task_id=task_id).first()

            if task:
                if result.state == 'PENDING' or "RUNNING":
                    celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')
                    task.status = "TERMINATED"
                    task.save(update_fields=['status'])
                    
                    return Response({"status": "Task has been successfully terminated"}, status=status.HTTP_200_OK)
                return Response({"status": "Task is already terminated"}, status=status.HTTP_400_BAD_REQUEST)
           
            else:
                return Response({"status": "There is no task against this ID"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"An error occurred": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
