from rest_framework_simplejwt.authentication import default_user_authentication_rule

def verified_user_authentication_rule(user):
    return default_user_authentication_rule(user) and user.is_email_verified
