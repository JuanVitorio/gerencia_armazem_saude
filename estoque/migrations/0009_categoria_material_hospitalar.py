from django.db import migrations


def adicionar_materiais_hospitalares(apps, schema_editor):
    Categoria = apps.get_model('estoque', 'Categoria')
    Categoria.objects.get_or_create(
        nome='Materiais Hospitalares',
        defaults={'tipo': 'MATERIAL_HOSPITALAR'},
    )


def remover_materiais_hospitalares(apps, schema_editor):
    Categoria = apps.get_model('estoque', 'Categoria')
    Categoria.objects.filter(nome='Materiais Hospitalares').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0008_unidade_codigo'),
    ]

    operations = [
        migrations.RunPython(adicionar_materiais_hospitalares, remover_materiais_hospitalares),
    ]
