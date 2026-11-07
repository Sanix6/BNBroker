# Xchange — Django + Unfold + PostgreSQL

## Запуск
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Заполните `.env` (уже создан без значений). Для Gmail нужен пароль приложения Google и SMTP `smtp.gmail.com:587`, TLS=true.
4. Создайте базу и пользователя PostgreSQL.
5. `python manage.py migrate`
6. `python manage.py createsuperuser`
7. `python manage.py runserver`
8. Панель `/admin/`, API `/api/users/` (см. `apps/users/urls.py`).

Коды: 6 цифр, 10 минут, максимум 5 попыток, повторная отправка через 60 секунд. Коды хранятся только в виде хеша.

Дашборд пока показывает реальные метрики пользователей; блоки заявок, AML и финансов появятся после реализации моделей.

Важно: тесты с реальными PostgreSQL и Gmail SMTP не выполнялись. Перед production необходимы HTTPS, ограничения запросов на уровне proxy, отдельная защита от перебора, аудит и проверка безопасности.

## Настройки Unfold

Все параметры темы, боковое меню и ссылки на зарегистрированные модели находятся в `core/unfold.py`.
Для добавления модели сначала зарегистрируйте её в `apps/<app>/admin.py`, затем добавьте `nav("Название", "icon_name", "app_label.modelname")` в `SIDEBAR.navigation`.
В `core/settings.py` Unfold подключается через `configure_admin(globals())`.
