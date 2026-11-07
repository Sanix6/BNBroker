from django.contrib import admin
from unfold.admin import ModelAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, EmailVerificationCode, OfferAcceptance
@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    ordering = ('-date_joined',)
    list_display = ('email','account_type','is_email_verified','is_staff','date_joined')
    list_filter = ('account_type','is_email_verified','is_staff','is_active')
    search_fields = ('email','first_name','last_name')
    readonly_fields = ('date_joined','updated_at')
    fieldsets = ((None, {'fields':('email','password')}),
                 ('Профиль',{'fields':('first_name','last_name','phone','account_type')}),
                 ('Доступ',{'fields':('is_active','is_email_verified','is_staff','is_superuser','groups','user_permissions')}),
                 ('Даты',{'fields':('last_login','date_joined','updated_at')}))
    add_fieldsets = ((None,{'classes':('wide',),'fields':('email','password1','password2','is_staff','is_superuser')}),)
@admin.register(OfferAcceptance)
class OfferAcceptanceAdmin(ModelAdmin):
    list_display = ('user','document_version','accepted_at','ip_address')
    readonly_fields = ('user','document_version','accepted_at','ip_address')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(ModelAdmin):
    list_display = ('user','created_at','expires_at','attempts','used_at')
    readonly_fields = ('user','code_hash','created_at','expires_at','attempts','used_at')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
