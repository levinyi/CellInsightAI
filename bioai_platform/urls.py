"""bioai_platform URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.http import HttpResponse


def health(_):
    return HttpResponse("ok")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz', health),
    path('', TemplateView.as_view(template_name='landing.html'), name='landing'),
    path('workbench', TemplateView.as_view(template_name='workbench.html'), name='workbench'),
    path('login', TemplateView.as_view(template_name='login.html'), name='login'),
    path('members', TemplateView.as_view(template_name='members.html'), name='members'),
    path('subscription', TemplateView.as_view(template_name='subscription.html'), name='subscription'),
    path('api/v1/', include('apps.steps.urls')),
    path('api/v1/core/', include('apps.projects.urls')),
    path('api/v1/storage/', include('apps.storage.urls')),
    path('api/v1/reports/', include('apps.reports.urls')),
    path('api/v1/users/', include('apps.users.urls')),
    # Optional: allauth endpoints for register/email/forgot (enable when templates ready)
    # path('accounts/', include('allauth.urls')),
]
