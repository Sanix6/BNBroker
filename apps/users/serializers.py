from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from .models import User, OfferAcceptance, EmailVerificationCode
from .services import send_verification_code

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id','email','first_name','last_name','phone','account_type','is_email_verified','date_joined')
        read_only_fields = ('id','email','is_email_verified','date_joined')

class RegisterSerializer(serializers.ModelSerializer):
    account_type = serializers.ChoiceField(
        choices=User.AccountType.choices,
        required=True,
    )
    password = serializers.CharField(write_only=True, validators=[validate_password])
    accept_offer = serializers.BooleanField(write_only=True, required=False)
    offer_version = serializers.CharField(write_only=True, required=False, max_length=32)


    class Meta:
        model = User
        fields = ('email','password','account_type','accept_offer','offer_version')

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Этот Email уже зарегистрирован')
        return value

    def validate_accept_offer(self, value):
        if not value:
            raise serializers.ValidationError('Необходимо принять публичную оферту')
        return value

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('accept_offer')
        version = validated_data.pop('offer_version')
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        request = self.context.get('request')
        ip = request.META.get('REMOTE_ADDR') if request else None
        OfferAcceptance.objects.create(user=user, document_version=version, ip_address=ip)
        send_verification_code(user)
        return user

class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.RegexField(r'^\d{6}$')

    def validate(self, attrs):
        try:
            user = User.objects.get(email__iexact=attrs['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError('Неверный код или Email')
        record = EmailVerificationCode.objects.filter(user=user,used_at__isnull=True,).exclude(code_hash__startswith="reset:").first()
        if not record or not record.is_valid:
            raise serializers.ValidationError('Код недействителен или истёк')
        record.attempts += 1
        record.save(update_fields=['attempts'])
        if not check_password(attrs['code'], record.code_hash):
            raise serializers.ValidationError('Неверный код или Email')
        attrs['user'] = user
        attrs['record'] = record
        return attrs

class ResendSerializer(serializers.Serializer):
    email = serializers.EmailField()



class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.RegexField(regex=r"^\d{6}$")


class PasswordResetConfirmSerializer(serializers.Serializer):
    reset_token = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )
    confirm_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Пароли не совпадают"
            })
        return attrs
