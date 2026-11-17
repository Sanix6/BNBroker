from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import User
from .serializers import RegisterSerializer, VerifyEmailSerializer, ResendSerializer, UserSerializer
from .services import send_verification_code
from drf_spectacular.utils import extend_schema

class AuthThrottle(AnonRateThrottle):
    rate = '10/hour'

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthThrottle]

class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Подтверждение email",
        description="Проверка шестизначного кода подтверждения email.",
        request=VerifyEmailSerializer,
        responses={200: None},
    )
    @transaction.atomic
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        record = serializer.validated_data['record']
        record.used_at = timezone.now()
        record.save(update_fields=['used_at'])
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        return Response({'detail':'Email подтверждён'})

class ResendEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthThrottle]

    @extend_schema(
        tags=["Authentication"],
        summary="Повторная отправка кода",
        description="Отправка нового кода подтверждения email.",
        request=ResendSerializer,
        responses={200: None},
    )
    def post(self, request):
        serializer = ResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data['email'], is_email_verified=False).first()
        if user:
            try:
                send_verification_code(user)
            except ValueError:
                pass
        return Response({'detail':'Если адрес зарегистрирован и не подтверждён, код будет отправлен'})

class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthThrottle]

class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    def get_object(self):
        return self.request.user
