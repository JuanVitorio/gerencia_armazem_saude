import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0004_categorias_pre_cadastradas'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Funcionario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=150, verbose_name='Nome')),
                ('cargo', models.CharField(blank=True, max_length=100, verbose_name='Cargo / Função')),
                ('matricula', models.CharField(blank=True, max_length=30, verbose_name='Matrícula')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('unidade', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='funcionarios', to='estoque.unidade', verbose_name='Unidade')),
            ],
            options={
                'verbose_name': 'Funcionário',
                'verbose_name_plural': 'Funcionários',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='LancamentoBancoHoras',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('CREDITO', 'Crédito (horas trabalhadas/extras)'), ('DEBITO', 'Débito (horas compensadas/folga)')], max_length=7, verbose_name='Tipo')),
                ('horas', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='Horas')),
                ('data_referencia', models.DateField(default=django.utils.timezone.localdate, verbose_name='Data de referência')),
                ('motivo', models.CharField(blank=True, max_length=255, verbose_name='Motivo / Observação')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('funcionario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lancamentos', to='estoque.funcionario', verbose_name='Funcionário')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lancamentos_banco_horas', to=settings.AUTH_USER_MODEL, verbose_name='Registrado por')),
            ],
            options={
                'verbose_name': 'Lançamento de Banco de Horas',
                'verbose_name_plural': 'Lançamentos de Banco de Horas',
                'ordering': ['-data_referencia', '-criado_em'],
            },
        ),
    ]
