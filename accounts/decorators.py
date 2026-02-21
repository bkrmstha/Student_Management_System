# accounts/decorators.py
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps

def admin_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is an admin.
    """
    def check_admin(user):
        return user.is_authenticated and (user.role == 'admin' or user.is_superuser)
    
    actual_decorator = user_passes_test(
        lambda u: check_admin(u),
        login_url='login'
    )
    return actual_decorator(view_func)

def teacher_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a teacher.
    """
    def check_teacher(user):
        return user.is_authenticated and user.role == 'teacher'
    
    actual_decorator = user_passes_test(
        lambda u: check_teacher(u),
        login_url='login'
    )
    return actual_decorator(view_func)

def student_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a student.
    """
    def check_student(user):
        return user.is_authenticated and user.role == 'student'
    
    actual_decorator = user_passes_test(
        lambda u: check_student(u),
        login_url='login'
    )
    return actual_decorator(view_func)

def guardian_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a guardian.
    """
    def check_guardian(user):
        return user.is_authenticated and user.role == 'guardian'
    
    actual_decorator = user_passes_test(
        lambda u: check_guardian(u),
        login_url='login'
    )
    return actual_decorator(view_func)


def role_required(*allowed_roles):
    """
    Flexible decorator that checks if user has one of the allowed roles.
    Usage: @role_required('admin', 'teacher') or @role_required('student', 'guardian')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            user_role = getattr(request.user, 'role', None)
            if user_role in allowed_roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            else:
                raise PermissionDenied('You do not have permission to access this page.')
        
        return wrapper
    return decorator
