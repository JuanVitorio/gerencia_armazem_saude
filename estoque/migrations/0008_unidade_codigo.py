from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0007_estoque_baixo_parametrizavel'),
    ]

    operations = [
        migrations.AddField(
            model_name='unidade',
            name='codigo',
            field=models.CharField(
                blank=True, null=True, max_length=20, unique=True,
                help_text='Código curto de identificação da unidade (ex: PS-01, SEC-CENTRAL). Opcional.',
                verbose_name='Código',
            ),
        ),
    ]
