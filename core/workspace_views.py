"""BNBroker's permission-aware, read-only operations workspace, with audited manual rate editing."""
from __future__ import annotations

from uuid import UUID

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, OuterRef, Subquery
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.core.paginator import Paginator

from apps.users.models import User
from apps.exchange.models import (ExchangeDirection, ExchangeOrder, ExchangeQuote,
                                  ExchangeRate, ExchangeRateChange)
from apps.kyc.models import KYCVerification
from apps.compliance.models import AMLCheck

PERMS = {
    'users': 'users.view_user',
    'orders': 'exchange.view_exchangeorder',
    'rates': 'exchange.view_exchangerate',
    'directions': 'exchange.view_exchangedirection',
    'applicants': 'kyc.view_kycverification',
    'aml': 'compliance.view_amlcheck',
}
MENU = (
    ('users', 'Все пользователи', 'bnb_ops_users'),
    ('applicants', 'Заявители KYC / KYB', 'bnb_ops_applicants'),
    ('orders', 'Все заявки', 'bnb_ops_orders'),
    ('rates', 'Ручные курсы', 'bnb_ops_rates'),
    ('directions', 'Направления обмена', 'bnb_ops_directions'),
    ('aml', 'AML-проверки', 'bnb_ops_aml'),
)

def allowed(request, key):
    if not request.user.has_perm(PERMS[key]):
        raise PermissionDenied('Недостаточно прав для этого раздела.')


def adm(name, obj=None):
    try:
        if obj is None:
            return reverse('admin:' + name)
        return reverse('admin:' + name, args=[obj.pk])
    except Exception:
        return ''


def link(name, pk=None):
    return reverse(name, args=[pk] if pk else [])


def frame(request, title, active, template, **values):
    request.current_app = admin.site.name
    context = admin.site.each_context(request)
    context.update({
        'title': title,
        'page_title': title,
        'section': active,
        'sections': [
            {'key': key, 'title': label, 'url': link(urlname)}
            for key, label, urlname in MENU if request.user.has_perm(PERMS[key])
        ],
        **values,
    })
    return render(request, template, context)


def clean_q(request):
    return request.GET.get('q', '').strip()[:100]


def filter_state(request, allowed_values):
    candidate = request.GET.get('status', '')
    return candidate if candidate in allowed_values else ''


def page_for(request, qs):
    return Paginator(qs, 25).get_page(request.GET.get('page', '1'))


def uuid_filter(value):
    try: return UUID(value)
    except (TypeError, ValueError, AttributeError): return None


def cell(value, url='', tone='', secondary=''):
    return {'value': value, 'url': url, 'tone': tone, 'secondary': secondary}


def tone_status(status):
    if status in {'approved', 'completed', 'paid', 'active'}: return 'success'
    if status in {'error', 'rejected', 'blocked', 'failed', 'cancelled'}: return 'danger'
    if status in {'pending', 'awaiting_payment', 'payment_review', 'manual_review', 'processing'}: return 'warn'
    return ''


def list_page(request, *, section, title, subtitle, qs, headers, row_builder,
              statuses=(), selected='', actions=(), summary=()):
    page = page_for(request, qs)
    rows = [{'cells': row_builder(obj), 'object': obj} for obj in page.object_list]
    params = request.GET.copy()
    params.pop('page', None)
    query_without_page = params.urlencode()
    return frame(request, title, section, 'admin/workspace/list.html',
        subtitle=subtitle, headers=headers, rows=rows, page=page,
        q=clean_q(request), statuses=statuses, selected=selected,
        actions=actions, summary=summary, query_without_page=query_without_page,
        result_count=page.paginator.count,
    )


def user_search(qs, q):
    if not q: return qs
    pred = Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q)
    u = uuid_filter(q)
    if u: pred |= Q(pk=u)
    return qs.filter(pred)


def latest_checks(qs):
    latest = KYCVerification.objects.filter(user_id=OuterRef('pk')).order_by('-created_at')
    return qs.annotate(last_check_status=Subquery(latest.values('status')[:1]),
                       last_check_level=Subquery(latest.values('level_name')[:1]),
                       last_check_date=Subquery(latest.values('created_at')[:1]))


def users(request):
    allowed(request, 'users')
    qs = latest_checks(user_search(User.objects.all(), clean_q(request))).order_by('-date_joined')
    typ = filter_state(request, {'individual', 'legal', 'verified', 'unverified', 'inactive'})
    if typ in ('individual', 'legal'): qs = qs.filter(account_type=typ)
    if typ == 'verified': qs = qs.filter(is_email_verified=True)
    if typ == 'unverified': qs = qs.filter(is_email_verified=False)
    if typ == 'inactive': qs = qs.filter(is_active=False)
    return list_page(request, section='users', title='Все пользователи', subtitle='Физические и юридические лица, регистрация и верификация',
        qs=qs, headers=['Клиент', 'Тип аккаунта', 'E-mail', 'Последняя проверка', 'Регистрация'],
        row_builder=lambda u: [cell(u.email, link('bnb_ops_user', u.pk), secondary=f'{u.first_name} {u.last_name}'.strip() or str(u.pk)[:8]),
            cell(u.get_account_type_display()), cell('Подтверждён' if u.is_email_verified else 'Не подтверждён', tone='success' if u.is_email_verified else 'warn'),
            cell(u.last_check_status or 'Не начата', tone=tone_status(u.last_check_status)),
            cell(timezone.localtime(u.date_joined).strftime('%d.%m.%Y %H:%M'))],
        statuses=[('individual','Физлица'), ('legal','Юрлица'),('verified','E-mail подтверждён'),('unverified','E-mail не подтверждён'),('inactive','Неактивные')], selected=typ,
        actions=[{'title': 'Создать клиента', 'url': link('bnb_ops_user_create'), 'primary': True}] if request.user.has_perm('users.add_user') else [],
        summary=[{'label': 'Всего', 'value': User.objects.count()}, {'label':'Юридических лиц', 'value':User.objects.filter(account_type='legal').count()}, {'label':'E-mail подтверждён', 'value':User.objects.filter(is_email_verified=True).count()}],
    )


def user_detail(request, pk):
    allowed(request, 'users')
    u = get_object_or_404(User, pk=pk)
    can_orders = request.user.has_perm(PERMS['orders'])
    can_kyc = request.user.has_perm(PERMS['applicants'])
    checks = list(KYCVerification.objects.filter(user=u).order_by('-created_at')[:8]) if can_kyc else []
    orders = list(ExchangeOrder.objects.filter(user=u).select_related('quote').order_by('-created_at')[:8]) if can_orders else []
    return frame(request, 'Карточка клиента', 'users', 'admin/workspace/user_detail.html', user_obj=u,
        checks=checks, orders=orders, can_orders=can_orders, can_kyc=can_kyc,
        edit_url=link('bnb_ops_user_edit', u.pk) if request.user.has_perm('users.change_user') else '',
        new_user_url=link('bnb_ops_user_create') if request.user.has_perm('users.add_user') else '',
    )



class UserDraftForm(forms.Form):
    email = forms.EmailField(label='Email клиента', max_length=254)
    account_type = forms.ChoiceField(label='Тип клиента', choices=User.AccountType.choices)
    first_name = forms.CharField(label='Имя', max_length=150, required=False)
    last_name = forms.CharField(label='Фамилия', max_length=150, required=False)
    phone = forms.CharField(label='Телефон', max_length=32, required=False)

    def clean_email(self):
        value = User.objects.normalize_email(self.cleaned_data['email']).strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise forms.ValidationError('Такой email уже зарегистрирован.')
        return value


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone')
        labels = {'first_name': 'Имя', 'last_name': 'Фамилия', 'phone': 'Телефон'}


def user_create(request):
    allowed(request, 'users')
    if not request.user.has_perm('users.add_user'):
        raise PermissionDenied('Недостаточно прав для создания клиента.')
    form = UserDraftForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                data = form.cleaned_data
                u = User(email=data['email'], account_type=data['account_type'],
                    first_name=data['first_name'], last_name=data['last_name'], phone=data['phone'],
                    is_active=False, is_email_verified=False, is_staff=False, is_superuser=False)
                u.set_unusable_password()  # Never issue working credentials from an operations screen.
                u.full_clean()
                u.save()
                admin.site._registry[User].log_addition(request, u, 'Создан черновик клиента через BNBroker Workspace.')
            messages.success(request, 'Черновик клиента создан. Для входа потребуется отдельная активация и подтверждение email.')
            return HttpResponseRedirect(link('bnb_ops_user', u.pk))
        except (ValidationError, IntegrityError):
            form.add_error('email', 'Не удалось создать клиента: проверьте данные и уникальность email.')
    return frame(request, 'Новый клиент', 'users', 'admin/workspace/user_form.html',
        form=form, creating=True, user_obj=None, admin_edit_url='')


def user_edit(request, pk):
    allowed(request, 'users')
    if not request.user.has_perm('users.change_user'):
        raise PermissionDenied('Недостаточно прав для изменения клиента.')
    u = get_object_or_404(User, pk=pk)
    form = UserProfileForm(request.POST or None, instance=u)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            u = form.save()
            admin.site._registry[User].log_change(request, u, 'Обновлены контактные данные через BNBroker Workspace.')
        messages.success(request, 'Контактные данные клиента сохранены.')
        return HttpResponseRedirect(link('bnb_ops_user', u.pk))
    return frame(request, 'Редактирование клиента', 'users', 'admin/workspace/user_form.html',
        form=form, creating=False, user_obj=u, admin_edit_url=adm('users_user_change',u))


def applicant_detail(request, pk):
    allowed(request, 'applicants')
    applicant = get_object_or_404(User, pk=pk)
    checks = KYCVerification.objects.filter(user=applicant).order_by('-created_at')[:100]
    last = checks[0] if checks else None
    return frame(request, 'Проверки заявителя', 'applicants', 'admin/workspace/applicant_detail.html',
        applicant=applicant, checks=checks,
        total_checks=KYCVerification.objects.filter(user=applicant).count(),
        last_status=last.get_status_display() if last else None,
        user_url=link('bnb_ops_user', applicant.pk) if request.user.has_perm(PERMS['users']) else '',
        can_change_kyc=request.user.has_perm('kyc.change_kycverification'))


def applicants(request):
    allowed(request, 'applicants')
    # One row per applicant, not one row per failed attempt. Include legal entities even without KYB.
    qs = latest_checks(User.objects.filter(Q(kyc_verifications__isnull=False) | Q(account_type='legal')).distinct())
    qs = user_search(qs, clean_q(request))
    state = filter_state(request, {'individual','legal','pending','approved','rejected','error','not_started'})
    if state in ('individual', 'legal'): qs = qs.filter(account_type=state)
    elif state == 'not_started': qs = qs.filter(last_check_status__isnull=True)
    elif state: qs = qs.filter(last_check_status=state)
    qs = qs.order_by('-date_joined')
    return list_page(request, section='applicants', title='Заявители KYC / KYB', subtitle='Каждый клиент показан один раз; статус — по последней попытке',
        qs=qs, headers=['Заявитель', 'Категория', 'Уровень', 'Последний статус', 'Дата проверки'],
        row_builder=lambda u: [cell(u.email, link('bnb_ops_applicant', u.pk), secondary=f'{u.first_name} {u.last_name}'.strip()),
            cell('KYB · компания' if u.account_type == 'legal' else 'KYC · физлицо'),
            cell(u.last_check_level or '—'), cell(u.last_check_status or 'Не начата', tone=tone_status(u.last_check_status)),
            cell(timezone.localtime(u.last_check_date).strftime('%d.%m.%Y %H:%M') if u.last_check_date else '—')],
        statuses=[('individual','Физлица'),('legal','Компании'),('pending','На проверке'),('approved','Одобрено'),('error','Ошибки'),('rejected','Отклонено'),('not_started','Без проверки')], selected=state,
        actions=[{'title':'Все попытки KYC/KYB','url':adm('kyc_kycverification_changelist')}] if request.user.has_perm(PERMS['applicants']) else [],
        summary=[{'label':'Всего проверок','value':KYCVerification.objects.count()}, {'label':'Ошибок','value':KYCVerification.objects.filter(status='error').count()}, {'label':'На проверке','value':KYCVerification.objects.filter(status='pending').count()}],
    )


def orders(request):
    allowed(request, 'orders')
    qs = ExchangeOrder.objects.select_related('user','quote','quote__asset_network','quote__asset_network__asset','quote__asset_network__network')
    q = clean_q(request)
    if q:
        pred = Q(user__email__icontains=q) | Q(txid__icontains=q) | Q(payment_reference__icontains=q)
        u = uuid_filter(q)
        if u: pred |= Q(pk=u) | Q(user__pk=u)
        qs = qs.filter(pred)
    state = filter_state(request, {x for x,_ in ExchangeOrder.Status.choices} | {'overdue'})
    if state == 'overdue': qs = qs.filter(status='awaiting_payment', quote__expires_at__lte=timezone.now())
    elif state: qs = qs.filter(status=state)
    return list_page(request, section='orders', title='Все заявки', subtitle='Оплаты, исполнение, сроки котировок и связь с клиентами',
        qs=qs.order_by('-created_at'), headers=['Заявка','Клиент','Обмен','Сумма, RUB','Статус','Создана'],
        row_builder=lambda o: [cell(str(o.pk)[:8]+'…', link('bnb_ops_order',o.pk)),
            cell(o.user.email, link('bnb_ops_user',o.user.pk) if request.user.has_perm(PERMS['users']) else ''),
            cell(o.quote.get_side_display(), secondary=str(o.quote.asset_network)), cell(o.quote.fiat_amount),
            cell(o.get_status_display(),tone=tone_status(o.status)), cell(timezone.localtime(o.created_at).strftime('%d.%m %H:%M'))],
        statuses=[(v,l) for v,l in ExchangeOrder.Status.choices]+[('overdue','Курс истёк, ожидает оплату')], selected=state,
        summary=[{'label':'Всего заявок','value':ExchangeOrder.objects.count()}, {'label':'Проверка оплаты','value':ExchangeOrder.objects.filter(status='payment_review').count()}, {'label':'Ожидают оплату','value':ExchangeOrder.objects.filter(status='awaiting_payment').count()}],
    )


def order_detail(request, pk):
    allowed(request, 'orders')
    o = get_object_or_404(ExchangeOrder.objects.select_related('quote','quote__asset_network','user','aml_check'),pk=pk)
    return frame(request, 'Карточка заявки', 'orders','admin/workspace/order_detail.html', order=o,
        expired=o.quote.expires_at <= timezone.now(),
        can_user=request.user.has_perm(PERMS['users']),
        edit_url=adm('exchange_exchangeorder_change',o) if request.user.has_perm('exchange.change_exchangeorder') else '',
        receipts=list(o.receipts.all().order_by('-uploaded_at')[:8]),
    )


def directions(request):
    allowed(request,'directions')
    qs=ExchangeDirection.objects.select_related('from_asset_network__asset','from_asset_network__network',
        'to_asset_network__asset','to_asset_network__network').order_by('id')
    q=clean_q(request)
    if q:
        qs=qs.filter(Q(from_asset_network__asset__symbol__icontains=q) | Q(to_asset_network__asset__symbol__icontains=q)
            | Q(from_asset_network__network__code__icontains=q) | Q(to_asset_network__network__code__icontains=q))
    state=filter_state(request,{'active','inactive'})
    if state: qs=qs.filter(is_active=state=='active')
    can_change=request.user.has_perm('exchange.change_exchangedirection')
    return list_page(request, section='directions', title='Направления обмена', subtitle='Доступные валютные пары и ограничения по сетям',
        qs=qs, headers=['Направление','Отдаёт','Получает','Статус','Управление'],
        row_builder=lambda d:[cell(str(d),adm('exchange_exchangedirection_change',d) if can_change else ''),
            cell(d.get_from_kind_display()),cell(d.get_to_kind_display()),
            cell('Включено' if d.is_active else 'Отключено',tone='success' if d.is_active else ''),
            cell('Открыть настройки',adm('exchange_exchangedirection_change',d) if can_change else '')],
        statuses=[('active','Активные'),('inactive','Неактивные')],selected=state,
        actions=[{'title':'Добавить направление','url':adm('exchange_exchangedirection_add'), 'primary':True}] if request.user.has_perm('exchange.add_exchangedirection') else [],
        summary=[{'label':'Всего направлений','value':ExchangeDirection.objects.count()}, {'label':'Активных','value':ExchangeDirection.objects.filter(is_active=True).count()}],
    )


def aml(request):
    allowed(request,'aml')
    qs=AMLCheck.objects.select_related('user','asset_network','asset_network__asset','asset_network__network')
    q=clean_q(request)
    if q:
        pred=Q(user__email__icontains=q) | Q(address__icontains=q) | Q(txid__icontains=q)
        u=uuid_filter(q)
        if u: pred |= Q(pk=u)
        qs=qs.filter(pred)
    state=filter_state(request,{x for x,_ in AMLCheck.Status.choices} | {x for x,_ in AMLCheck.Decision.choices})
    if state in dict(AMLCheck.Status.choices): qs=qs.filter(status=state)
    elif state: qs=qs.filter(decision=state)
    return list_page(request, section='aml',title='AML-проверки',subtitle='Результаты проверок адресов и транзакций Ranex',
        qs=qs.order_by('-created_at'),headers=['Проверка','Клиент','Тип','Сеть','Результат','Дата'],
        row_builder=lambda a:[cell(str(a.pk)[:8]+'…',adm('compliance_amlcheck_change',a)),
            cell(a.user.email if a.user else '—',link('bnb_ops_user',a.user_id) if a.user_id and request.user.has_perm(PERMS['users']) else ''),
            cell(a.get_kind_display()),cell(str(a.asset_network)),
            cell(a.get_decision_display(),tone=tone_status(a.decision)),
            cell(timezone.localtime(a.created_at).strftime('%d.%m %H:%M'))],
        statuses=[(v,l) for v,l in AMLCheck.Status.choices] + [(v,l) for v,l in AMLCheck.Decision.choices if v not in {'pending'}],selected=state,
        summary=[{'label':'Всего AML','value':AMLCheck.objects.count()}, {'label':'На проверке','value':AMLCheck.objects.filter(status='pending').count()}, {'label':'Ошибок','value':AMLCheck.objects.filter(status='failed').count()}],
    )


class RateForm(forms.ModelForm):
    class Meta:
        model = ExchangeRate
        fields = ('direction','rate','is_active')
        widgets = {
            'rate': forms.NumberInput(attrs={'step':'0.000000000001','min':'0.000000000001', 'placeholder':'Например, 95.50'}),
        }
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['direction'].queryset = ExchangeDirection.objects.filter(
            Q(from_kind='fiat',to_kind='crypto') | Q(from_kind='crypto',to_kind='fiat'))
        if self.instance.pk:
            self.fields['direction'].disabled=True


def rates(request):
    allowed(request,'rates')
    can_add=request.user.has_perm('exchange.add_exchangerate')
    can_edit=request.user.has_perm('exchange.change_exchangerate')
    edit_id = request.GET.get('edit', '') or request.POST.get('edit_id', '')
    instance = None
    if edit_id:
        try: edit_number=int(edit_id)
        except (ValueError,TypeError): raise Http404('Курс не найден')
        instance=get_object_or_404(ExchangeRate,pk=edit_number)
    if request.method=='POST':
        if instance and not can_edit: raise PermissionDenied
        if not instance and not can_add: raise PermissionDenied
        form=RateForm(request.POST,instance=instance)
        if form.is_valid():
            # Re-read and lock the actual DB record to audit the previous value accurately.
            try:
                with transaction.atomic():
                    current=None
                    old_rate=old_active=None
                    if instance:
                        current=ExchangeRate.objects.select_for_update().get(pk=instance.pk)
                        old_rate,old_active=current.rate,current.is_active
                        form=RateForm(request.POST,instance=current)
                        if not form.is_valid(): raise ValidationError('Повторите сохранение: данные изменились.')
                    obj=form.save(commit=False)
                    obj.updated_by=request.user
                    obj.full_clean()
                    changed = current is None or old_rate != obj.rate or old_active != obj.is_active
                    obj.save()
                    if changed:
                        ExchangeRateChange.objects.create(direction=obj.direction,
                            old_rate=old_rate,new_rate=obj.rate,old_active=old_active,
                            new_active=obj.is_active,changed_by=request.user)
                messages.success(request,'Курс сохранён. Изменение записано в историю.' if changed else 'Курс без изменений.')
                return HttpResponseRedirect(link('bnb_ops_rates'))
            except (ValidationError, IntegrityError) as err:
                form.add_error(None,'Не удалось сохранить: проверьте уникальность направления и значения курса.')
        else:
            messages.error(request,'Исправьте ошибки в форме курса.')
    else:
        form=RateForm(instance=instance)
    qs=ExchangeRate.objects.select_related('direction','direction__from_asset_network__asset','direction__to_asset_network__asset','updated_by')
    q=clean_q(request)
    if q:
        qs=qs.filter(Q(direction__from_asset_network__asset__symbol__icontains=q) | Q(direction__to_asset_network__asset__symbol__icontains=q)
            | Q(updated_by__email__icontains=q))
    state=filter_state(request, {'active','inactive'})
    if state: qs=qs.filter(is_active=state=='active')
    page=page_for(request,qs.order_by('direction_id'))
    params=request.GET.copy();params.pop('page',None)
    return frame(request,'Центр управления курсами','rates','admin/workspace/rates.html',
        form=form, editing=instance, can_add=can_add,can_edit=can_edit,
        rates=page, q=q, selected=state,query_without_page=params.urlencode(),
        total=ExchangeRate.objects.count(), active_count=ExchangeRate.objects.filter(is_active=True).count(),
        history_url=link('bnb_ops_rates_history') if request.user.has_perm('exchange.view_exchangeratechange') else '',
    )


def history(request):
    allowed(request,'rates')
    if not request.user.has_perm('exchange.view_exchangeratechange'): raise PermissionDenied
    qs=ExchangeRateChange.objects.select_related('direction','changed_by').order_by('-changed_at')
    q=clean_q(request)
    if q:
        qs=qs.filter(Q(changed_by__email__icontains=q) | Q(direction__from_asset_network__asset__symbol__icontains=q)
            | Q(direction__to_asset_network__asset__symbol__icontains=q))
    return list_page(request,section='rates',title='История изменения курсов',subtitle='Журнал всех изменений курса и доступности, с указанием оператора',
        qs=qs,headers=['Направление','Было, RUB','Стало, RUB','Статус','Кто изменил','Дата'],
        row_builder=lambda x:[cell(str(x.direction)),cell(x.old_rate if x.old_rate is not None else '—'),
            cell(x.new_rate),cell('Активен' if x.new_active else 'Отключён', tone='success' if x.new_active else ''),
            cell(x.changed_by.email if x.changed_by else '—'),cell(timezone.localtime(x.changed_at).strftime('%d.%m.%Y %H:%M'))],
        actions=[{'title':'Вернуться к курсам','url':link('bnb_ops_rates')}],
        summary=[{'label':'Всего изменений','value':ExchangeRateChange.objects.count()}],
    )
