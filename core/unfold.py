
"""Оформление, навигация и доступы Django Unfold."""

from django.apps import apps
from django.templatetags.static import static
from django.urls import NoReverseMatch, reverse, reverse_lazy


def can_view(permission):
    """Проверка доступа к разделу админки."""
    def check(request):
        user = request.user
        return (
            user.is_authenticated
            and user.is_active
            and user.has_perm(permission)
        )

    return check


def nav(title, icon, model):
    """Создать пункт навигации для модели Django."""
    app_label, model_name = model.lower().split(".")

    return {
        "title": title,
        "icon": icon,
        "link": reverse_lazy(
            f"admin:{app_label}_{model_name}_changelist"
        ),
        "permission": can_view(
            f"{app_label}.view_{model_name}"
        ),
    }


def optional_nav(title, icon, model):
    """
    Показывать пункт только при наличии модели,
    регистрации в admin и прав пользователя.
    """
    app_label, model_name = model.lower().split(".")

    def is_available(request):
        try:
            apps.get_model(app_label, model_name)
            reverse(
                f"admin:{app_label}_{model_name}_changelist"
            )
        except (LookupError, NoReverseMatch):
            return False

        return can_view(
            f"{app_label}.view_{model_name}"
        )(request)

    return {
        "title": title,
        "icon": icon,
        "link": reverse_lazy(
            f"admin:{app_label}_{model_name}_changelist"
        ),
        "permission": is_available,
    }


UNFOLD_CONFIG = {
    # Основные настройки
    "SITE_TITLE": "BNBroker · Управление",
    "SITE_HEADER": "BNBroker",
    "SITE_SYMBOL": "currency_exchange",
    "SITE_URL": None,

    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SHOW_LANGUAGES": False,

    # Дашборд
    "DASHBOARD_CALLBACK": "core.ops_dashboard.dashboard_callback",
    "DASHBOARD_TEMPLATE": "admin/index.html",

    # Стили
    "STYLES": [
        lambda request: static("css/admin.css"),
    ],

    # Фирменные цвета
    "COLORS": {
        "primary": {
            "50": "236 253 245",
            "100": "209 250 229",
            "200": "167 243 208",
            "300": "110 231 183",
            "400": "52 211 153",
            "500": "16 185 129",
            "600": "5 150 105",
            "700": "4 120 87",
            "800": "6 95 70",
            "900": "6 78 59",
            "950": "2 44 34",
        },
    },

    # Боковое меню
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,

        "navigation": [
            {
                "title": "Рабочее пространство",
                "separator": False,
                "items": [
                    {
                        "title": "Дашборд",
                        "icon": "space_dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                    nav(
                        "Пользователи",
                        "group",
                        "users.user",
                    ),
                ],
            },

            {
                "title": "Регистрация и безопасность",
                "separator": True,
                "items": [
                    nav(
                        "Коды подтверждения",
                        "mark_email_read",
                        "users.emailverificationcode",
                    ),
                    nav(
                        "Акцепты оферты",
                        "verified_user",
                        "users.offeracceptance",
                    ),
                ],
            },

            {
                "title": "Управление доступом",
                "separator": True,
                "items": [
                    nav(
                        "Группы и роли",
                        "admin_panel_settings",
                        "auth.group",
                    ),
                ],
            },

            {
                "title": "Криптовалюты",
                "separator": True,
                "items": [
                    nav(
                        "Валюты",
                        "currency_bitcoin",
                        "crypto.cryptocurrency",
                    ),
                    nav(
                        "Блокчейн-сети",
                        "hub",
                        "crypto.blockchainnetwork",
                    ),
                    nav(
                        "Валюты по сетям",
                        "account_tree",
                        "crypto.cryptonetwork",
                    ),
                    nav(
                        "Криптоадреса",
                        "account_balance_wallet",
                        "crypto.cryptoaddress",
                    ),
                ],
            },

            {
                "title": "Обмен и заявки",
                "separator": True,
                "items": [
                    optional_nav(
                        "Направления обмена",
                        "swap_horiz",
                        "exchange.exchangedirection",
                    ),
                    optional_nav(
                        "Курсы обмена", "currency_exchange", "exchange.exchangerate",
                    ),
                    optional_nav(
                        "История изменения курсов", "history", "exchange.exchangeratechange",
                    ),
                    optional_nav(
                        "Котировки клиентов", "query_stats", "exchange.exchangequote",
                    ),
                    optional_nav(
                        "Заявки клиентов",
                        "receipt_long",
                        "exchange.exchangeorder",
                    ),
                ],
            },

            {
                "title": "Проверки Ranex",
                "separator": True,
                "items": [
                    nav(
                        "KYC клиентов",
                        "verified_user",
                        "kyc.kycverification",
                    ),
                    nav(
                        "AML адресов и TxID",
                        "policy",
                        "compliance.amlcheck",
                    ),
                ],
            },
        ],
    },
}


def configure_admin(namespace):
    """Подключение Django Unfold к настройкам проекта."""

    installed_apps = [
        app
        for app in namespace["INSTALLED_APPS"]
        if app not in (
            "unfold",
            "unfold.contrib.filters",
        )
    ]

    installed_apps.insert(
        0,
        "unfold.contrib.filters",
    )
    installed_apps.insert(
        0,
        "unfold",
    )

    namespace["INSTALLED_APPS"] = installed_apps
    namespace["UNFOLD"] = UNFOLD_CONFIG
