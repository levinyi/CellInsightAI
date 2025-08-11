from django.urls import path
from . import views

urlpatterns = [
    path('tasks', views.create_task, name='create_task'),
    path('tasks/<uuid:id>', views.get_task_status, name='get_task_status'),
]