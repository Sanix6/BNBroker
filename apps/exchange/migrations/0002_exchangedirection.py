from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('exchange', '0001_initial'),
        ('crypto', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='ExchangeDirection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_kind', models.CharField(choices=[('fiat', 'Фиат'), ('crypto', 'Криптовалюта')], default='fiat', max_length=6)),
                ('to_kind', models.CharField(choices=[('fiat', 'Фиат'), ('crypto', 'Криптовалюта')], default='crypto', max_length=6)),
                ('is_active', models.BooleanField(db_index=True, default=False, verbose_name='Доступно')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('from_asset_network', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exchange_directions_from', to='crypto.cryptonetwork', verbose_name='Отдаёт: сеть криптовалюты')),
                ('to_asset_network', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exchange_directions_to', to='crypto.cryptonetwork', verbose_name='Получает: сеть криптовалюты')),
            ],
            options={'verbose_name': 'Направление обмена', 'verbose_name_plural': 'Направления обмена', 'ordering': ('id',)},
        ),
        migrations.AddConstraint(
            model_name='exchangedirection',
            constraint=models.UniqueConstraint(
                fields=('from_kind', 'from_asset_network', 'to_kind', 'to_asset_network'),
                name='exchange_direction_unique_pair', nulls_distinct=False,
            ),
        ),
    ]
