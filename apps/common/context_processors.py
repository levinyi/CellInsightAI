"""
Global context processors for templates
"""
import json
from django.utils.safestring import mark_safe

def app_urls(request):
    """
    Provides centralized URL constants for templates.
    This helps maintain consistency and makes it easier to update URLs.
    """
    urls = {
        # Page routes
        'HOME': '/',
        'PROJECTS': '/projects',
        'WORKBENCH': '/workbench',
        'MEMBERS': '/members',
        'ORGANIZATION_MEMBERS': '/organization-members',
        'SUBSCRIPTION': '/subscription',
        'PROFILE': '/profile',
        'LOGIN': '/login',
        
        # API routes
        'API_PREFIX': '/api/v1',
        'API_USERS_BASE': '/api/v1/users',
        'API_USER_ME': '/api/v1/users/users/me/',
        'API_DEMO_LOGIN': '/api/v1/users/demo-login/',
        'API_LOGOUT': '/api/v1/users/logout/',
        'API_MEMBERSHIPS': '/api/v1/users/memberships/',
        'API_PROFILES': '/api/v1/users/profiles/',
        'API_ORGANIZATIONS': '/api/v1/users/organizations/',
        'API_ORGS': '/api/v1/users/organizations/',
        'API_LOGIN_HISTORY': '/api/v1/users/login-history/',
        
        # Core APIs - updated for new model structure
        'API_CORE_BASE': '/api/v1/core',
        'API_PROJECTS': '/api/v1/core/projects/',
        'API_DATASETS': '/api/v1/core/datasets/',
        'API_SESSIONS': '/api/v1/core/sessions/',
        'API_SAMPLES': '/api/v1/core/samples/',  # deprecated but kept for compatibility
        'API_STEPS': '/api/v1/core/steps/',
        'API_STEP_RUNS': '/api/v1/core/step-runs/',
        'API_ARTIFACTS': '/api/v1/core/artifacts/',
        'API_ADVICE': '/api/v1/core/advice/',
        'API_AUDIT_LOGS': '/api/v1/core/audit-logs/',
        'API_CORE_RUN': '/api/v1/core/run/',
        
        # Storage APIs
        'API_STORAGE_BASE': '/api/v1/storage',
        'API_STORAGE_PRESIGN': '/api/v1/storage/presign',
        'API_STORAGE_UPLOAD': '/api/v1/storage/upload',
        
        # Reports APIs
        'API_REPORTS_BASE': '/api/v1/reports',
    }
    
    return {
        'APP_URLS': urls,
        'APP_URLS_JSON': mark_safe(json.dumps(urls))
    }