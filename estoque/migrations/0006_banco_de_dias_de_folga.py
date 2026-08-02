import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0005_banco_de_horas'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1) O banco de horas virou banco de DIAS de folga: renomeia o model
        #    e o campo, e troca o tipo de decimal (horas) para inteiro (dias).
        migrations.RenameModel(
            old_name='LancamentoBancoHoras',
            new_name='LancamentoFolga',
        ),
        migrations.AlterModelOptions(
            name='lancamentofolga',
            options={
                'ordering': ['-data_referencia', '-criado_em'],
                'verbose_name': 'Lançamento de Folga',
                'verbose_name_plural': 'Lançamentos de Folga',
            },
        ),
        migrations.RenameField(
            model_name='lancamentofolga',
            old_name='horas',
            new_name='dias',
        ),
        migrations.AlterField(
            model_name='lancamentofolga',
            name='dias',
            field=models.PositiveSmallIntegerField(verbose_name='Dias de folga'),
        ),
        migrations.AlterField(
            model_name='lancamentofolga',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('CREDITO', 'Crédito (dia de folga concedido)'),
                    ('DEBITO', 'Débito (dia de folga usado)'),
                ],
                max_length=7, verbose_name='Tipo',
            ),
        ),

        # 2) Novo model: o evento que gera os créditos em lote (ex: "Dia de Vacinação").
        migrations.CreateModel(
            name='EventoFolga',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(help_text='Ex: Dia de Vacinação, Mutirão de Saúde...', max_length=150, verbose_name='Nome do evento')),
                ('data', models.DateField(default=django.utils.timezone.localdate, verbose_name='Data do evento')),
                ('descricao', models.TextField(blank=True, verbose_name='Descrição')),
                ('dias', models.PositiveSmallIntegerField(default=1, help_text='Quantos dias de folga cada funcionário participante recebe.', verbose_name='Dias de folga por participante')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos_folga_criados', to=settings.AUTH_USER_MODEL, verbose_name='Registrado por')),
            ],
            options={
                'verbose_name': 'Evento de Folga',
                'verbose_name_plural': 'Eventos de Folga',
                'ordering': ['-data', '-criado_em'],
            },
        ),

        # 3) Cada lançamento pode apontar para o evento que o originou.
        migrations.AddField(
            model_name='lancamentofolga',
            name='evento',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lancamentos', to='estoque.eventofolga', verbose_name='Evento de origem'),
        ),
    ]
