from django.urls import reverse
from apps.users.models import User, EmailVerificationCode

def dashboard_callback(request, context):
    context.update({
        "total_users": User.objects.count(),
        "verified_users": User.objects.filter(is_email_verified=True).count(),
        "unverified_users": User.objects.filter(is_email_verified=False).count(),
        "recent_users": User.objects.order_by("-date_joined")[:8],
        "user_changelist_url": reverse("admin:users_user_changelist"),
    })
    return context
