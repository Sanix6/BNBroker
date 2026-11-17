"""Protected custom Unfold workspace. Must be included BEFORE admin.site.urls."""
from django.contrib import admin
from django.urls import path
from core import workspace_views as v

urlpatterns = [
    path('users/', admin.site.admin_view(v.users), name='bnb_ops_users'),
    path('users/create/', admin.site.admin_view(v.user_create), name='bnb_ops_user_create'),
    path('users/<uuid:pk>/', admin.site.admin_view(v.user_detail), name='bnb_ops_user'),
    path('users/<uuid:pk>/edit/', admin.site.admin_view(v.user_edit), name='bnb_ops_user_edit'),
    path('applicants/', admin.site.admin_view(v.applicants), name='bnb_ops_applicants'),
    path('applicants/<uuid:pk>/', admin.site.admin_view(v.applicant_detail), name='bnb_ops_applicant'),
    path('orders/', admin.site.admin_view(v.orders), name='bnb_ops_orders'),
    path('orders/<uuid:pk>/', admin.site.admin_view(v.order_detail), name='bnb_ops_order'),
    path('rates/', admin.site.admin_view(v.rates), name='bnb_ops_rates'),
    path('rates/history/', admin.site.admin_view(v.history), name='bnb_ops_rates_history'),
    path('directions/', admin.site.admin_view(v.directions), name='bnb_ops_directions'),
    path('aml/', admin.site.admin_view(v.aml), name='bnb_ops_aml'),
]
