from django.urls import path
from .views import (QuotesView, OrdersView, OrderCreateView, OrderDetailView,
                    PaymentView, ReceiptUploadView, PaymentConfirmationView, ReportView, DirectionsView)
urlpatterns = [
    path('directions/', DirectionsView.as_view(), name='exchange-directions'),
    path('quotes/', QuotesView.as_view(), name='exchange-quotes'),
    path('orders/', OrdersView.as_view(), name='exchange-orders'),
    path('orders/create/', OrderCreateView.as_view(), name='exchange-order-create'),
    path('orders/<uuid:pk>/', OrderDetailView.as_view(), name='exchange-order-detail'),
    path('orders/<uuid:pk>/payment/', PaymentView.as_view(), name='exchange-payment'),
    path('orders/<uuid:pk>/receipt/', ReceiptUploadView.as_view(), name='exchange-receipt'),
    path('orders/<uuid:pk>/payment-confirmation/', PaymentConfirmationView.as_view(), name='exchange-payment-confirmation'),
    path('orders/<uuid:pk>/report/', ReportView.as_view(), name='exchange-report'),
]


# Register before legacy auto-generated directions route (if installed).
from .direction_api import ExchangeAssetsView, ExchangeDirectionsView
urlpatterns.insert(0, path('directions/', ExchangeDirectionsView.as_view(), name='exchange-managed-directions'))
urlpatterns.insert(0, path('assets/', ExchangeAssetsView.as_view(), name='exchange-managed-assets'))
