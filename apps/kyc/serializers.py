
from rest_framework import serializers
from .models import KYCVerification


class KYCSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCVerification
        fields = (
            "id",
            "provider",
            "level_name",
            "status",
            "review_reason",
            "verified_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class KYCStartSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32, required=False)


class KYCStartResponseSerializer(serializers.Serializer):
    verification = KYCSerializer()
    verification_url = serializers.URLField()


class KYCMeSerializer(serializers.Serializer):
    status = serializers.CharField()
    verification = KYCSerializer(allow_null=True)
