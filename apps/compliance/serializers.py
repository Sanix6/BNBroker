from rest_framework import serializers
from apps.compliance.models import AMLCheck
from apps.crypto.models import CryptoNetwork


class AMLAddressCheckSerializer(serializers.Serializer):
    asset_network_id = serializers.PrimaryKeyRelatedField(
        queryset=CryptoNetwork.objects.filter(
            is_active=True,
            asset__is_active=True,
            network__is_active=True,
        ),
        source="asset_network",
    )
    address = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
    )

    def validate(self, attrs):
        asset_network = attrs["asset_network"]
        network = asset_network.network

        if not network.ranex_network_code:
            raise serializers.ValidationError({
                "asset_network_id": "AML-проверка этой сети не поддерживается."
            })

        from apps.integrations.ranex.constants import RanexNetwork

        if network.ranex_network_code not in RanexNetwork.SUPPORTED:
            raise serializers.ValidationError({
                "asset_network_id": "Сеть не поддерживается Ranex."
            })

        return attrs


class AMLCheckSerializer(serializers.ModelSerializer):
    asset_network_id = serializers.IntegerField(
        read_only=True,
    )

    class Meta:
        model = AMLCheck
        fields = [
            "id",
            "asset_network_id",
            "kind",
            "address",
            "provider",
            "status",
            "decision",
            "risk_score",
            "risk_category",
            "created_at",
            "screened_at",
        ]
        read_only_fields = fields
