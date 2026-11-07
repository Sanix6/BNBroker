"""Оформление, навигация и доступы Django Unfold."""
from django.templatetags.static import static
from django.urls import reverse_lazy


def can_view(permission):
    return lambda request: request.user.is_active and request.user.has_perm(permission)


def nav(title, icon, model):
    app_label, model_name = model.lower().split(".")
    return {
        "title": title,
        "icon": icon,
        "link": reverse_lazy(f"admin:{app_label}_{model_name}_changelist"),
        "permission": can_view(f"{app_label}.view_{model_name}"),
    }


UNFOLD_CONFIG = {
    "SITE_TITLE": "Xchange · Управление",
    "SITE_HEADER": "Xchange",
    "SITE_SYMBOL": "currency_exchange",
    "SITE_URL": None,
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SHOW_LANGUAGES": False,
    "DASHBOARD_CALLBACK": "core.dashboard.dashboard_callback",
    "DASHBOARD_TEMPLATE": "admin/index.html",
    "STYLES": [lambda request: static("css/admin.css")],
    "COLORS": {
        "primary": {
            "50": "236 253 245", "100": "209 250 229", "200": "167 243 208",
            "300": "110 231 183", "400": "52 211 153", "500": "16 185 129",
            "600": "5 150 105", "700": "4 120 87", "800": "6 95 70",
            "900": "6 78 59", "950": "2 44 34",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {"title": "Рабочее пространство", "separator": False, "items": [
                {"title": "Дашборд", "icon": "space_dashboard", "link": reverse_lazy("admin:index")},
                nav("Пользователи", "group", "users.user"),
            ]},
            {"title": "Регистрация и безопасность", "separator": True, "items": [
                nav("Коды подтверждения", "mark_email_read", "users.emailverificationcode"),
                nav("Акцепты оферты", "verified_user", "users.offeracceptance"),
            ]},
            {"title": "Управление доступом", "separator": True, "items": [
                nav("Группы и роли", "admin_panel_settings", "auth.group"),
            ]},
            {"title": "Криптовалюты", "separator": True, "items": [
                nav("Валюты", "currency_bitcoin", "crypto.cryptocurrency"),
                nav("Блокчейн-сети", "hub", "crypto.blockchainnetwork"),
                nav("Валюты по сетям", "account_tree", "crypto.cryptonetwork"),
                nav("Криптоадреса", "account_balance_wallet", "crypto.cryptoaddress"),
            ]},
            {"title": "Проверки Ranex", "separator": True, "items": [
                nav("KYC клиентов", "verified_user", "kyc.kycverification"),
                nav("AML адресов и TxID", "policy", "compliance.amlcheck"),
            ]},
        ],
    },
}


def configure_admin(namespace):
    apps = [app for app in namespace["INSTALLED_APPS"] if app not in ("unfold", "unfold.contrib.filters")]
    apps.insert(0, "unfold.contrib.filters")
    apps.insert(0, "unfold")
    namespace["INSTALLED_APPS"] = apps
    namespace["UNFOLD"] = UNFOLD_CONFIG
