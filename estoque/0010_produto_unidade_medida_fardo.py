from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Só adiciona 'Fardo' (FD) às opções de Unidade de Medida do Produto —
    não altera dados existentes, é apenas metadado de choices (não muda
    a coluna no banco).
    """

    dependencies = [
        ('estoque', '0009_categoria_material_hospitalar'),
    ]

    operations = [
        migrations.AlterField(
            model_name='produto',
            name='unidade_medida',
            field=models.CharField(
                choices=[
                    ('UN', 'Unidade'),
                    ('CX', 'Caixa'),
                    ('PC', 'Pacote'),
                    ('KG', 'Quilograma'),
                    ('G', 'Grama'),
                    ('L', 'Litro'),
                    ('ML', 'Mililitro'),
                    ('DS', 'Dose'),
                    ('FR', 'Frasco'),
                    ('AMP', 'Ampola'),
                    ('PAR', 'Par'),
                    ('RO', 'Rolo'),
                    ('SC', 'Saco'),
                    ('FD', 'Fardo'),
                ],
                default='UN',
                max_length=3,
                verbose_name='Unidade de Medida',
            ),
        ),
    ]
