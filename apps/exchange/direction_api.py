"""Read-only public catalog of operator-enabled exchange pairs."""
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from .models import ExchangeDirection


def active_directions():
    return (ExchangeDirection.objects.filter(is_active=True)
        .filter(
            Q(from_kind='fiat') |
            Q(from_asset_network__is_active=True,
              from_asset_network__asset__is_active=True,
              from_asset_network__network__is_active=True,
              from_asset_network__deposit_enabled=True)
        ).filter(
            Q(to_kind='fiat') |
            Q(to_asset_network__is_active=True,
              to_asset_network__asset__is_active=True,
              to_asset_network__network__is_active=True,
              to_asset_network__withdrawal_enabled=True)
        ).select_related(
            'from_asset_network__asset', 'from_asset_network__network',
            'to_asset_network__asset', 'to_asset_network__network',
        ).order_by('id'))


def node(direction, side):
    kind = getattr(direction, f'{side}_kind')
    if kind == 'fiat':
        return {'id': 'fiat:RUB', 'kind': 'fiat', 'currency': 'RUB',
                'asset_network_id': None, 'network': None}
    item = getattr(direction, f'{side}_asset_network')
    return {'id': f'crypto:{item.pk}', 'kind': 'crypto',
            'currency': item.asset.symbol, 'asset_network_id': item.pk,
            'network': item.network.code}


def serialize(direction):
    left, right = node(direction, 'from'), node(direction, 'to')
    return {'id': direction.pk, 'from': left, 'to': right,
            'from_currency': left['currency'], 'to_currency': right['currency'],
            'is_active': True}


class ExchangeAssetsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=['Exchange'], responses={200: dict})
    def get(self, request):
        directions = list(active_directions())
        from_nodes, to_nodes = {}, {}
        for direction in directions:
            left, right = node(direction, 'from'), node(direction, 'to')
            from_nodes[left['id']] = left
            to_nodes[right['id']] = right
        return Response({'from': sorted(from_nodes.values(), key=lambda x: x['id']),
                         'to': sorted(to_nodes.values(), key=lambda x: x['id'])})


class ExchangeDirectionsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Exchange'],
        parameters=[
            OpenApiParameter('from', str, description='Node ID, e.g. fiat:RUB or crypto:4'),
            OpenApiParameter('to', str, description='Node ID, e.g. fiat:RUB or crypto:4'),
        ],
        responses={200: dict},
    )
    def get(self, request):
        from_id = request.query_params.get('from')
        to_id = request.query_params.get('to')
        for name, value in [('from', from_id), ('to', to_id)]:
            if value and value != 'fiat:RUB':
                if not value.startswith('crypto:') or not value[7:].isdigit() or int(value[7:]) < 1:
                    raise ValidationError({name: 'Используйте fiat:RUB или crypto:<asset_network_id>.'})
        directions = active_directions()
        if from_id:
            if from_id == 'fiat:RUB':
                directions = directions.filter(from_kind='fiat')
            else:
                directions = directions.filter(from_kind='crypto', from_asset_network_id=int(from_id[7:]))
        if to_id:
            if to_id == 'fiat:RUB':
                directions = directions.filter(to_kind='fiat')
            else:
                directions = directions.filter(to_kind='crypto', to_asset_network_id=int(to_id[7:]))
        return Response([serialize(direction) for direction in directions])
