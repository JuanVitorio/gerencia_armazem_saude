from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0006_banco_de_dias_de_folga'),
    ]

    operations = [
        migrations.AddField(
            model_name='categoria',
            name='limite_estoque_baixo',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text=(
                    'Quantidade abaixo da qual produtos desta categoria entram no alerta '
                    'de estoque baixo. Deixe em branco para usar o limite padrão do sistema. '
                    'Um produto pode sobrescrever esse valor individualmente.'
                ),
                verbose_name='Limite de Estoque Baixo (categoria)',
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='limite_estoque_baixo',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text=(
                    'Sobrescreve o limite da categoria/sistema só para este produto. '
                    'Tem prioridade sobre tudo. Deixe em branco para não sobrescrever.'
                ),
                verbose_name='Limite de Estoque Baixo (produto)',
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='estoque_maximo',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Capacidade ideal deste produto — usada como referência do alerta por percentual, abaixo.',
                verbose_name='Estoque Máximo / Ideal',
            ),
        ),
        migrations.AddField(
            model_name='produto',
            name='percentual_alerta_estoque',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                help_text=(
                    'Alerta quando a quantidade atual cair abaixo desse percentual do '
                    '"Estoque Máximo / Ideal". Só funciona se os dois campos estiverem preenchidos. '
                    'Ex: Estoque Máximo = 100 e 20% → alerta abaixo de 20 unidades.'
                ),
                verbose_name='% Mínimo do Estoque Máximo',
            ),
        ),
    ]
