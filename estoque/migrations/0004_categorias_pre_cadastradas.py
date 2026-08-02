from django.db import migrations


CATEGORIAS = [
    ('Medicamentos', 'MEDICAMENTO'),
    ('Vacinas', 'VACINA'),
    ('Materiais Odontológicos', 'MATERIAL_ODONTOLOGICO'),
    ('Produtos de Limpeza', 'MATERIAL_LIMPEZA'),
    ('Alimentos', 'ALIMENTO'),
    ('Materiais de Cozinha', 'ALIMENTO'),
    ('Insumos', 'INSUMO'),
    ('Outros', 'OUTRO'),
]


def criar_categorias(apps, schema_editor):
    Categoria = apps.get_model('estoque', 'Categoria')
    for nome, tipo in CATEGORIAS:
        Categoria.objects.get_or_create(nome=nome, defaults={'tipo': tipo})


def remover_categorias(apps, schema_editor):
    Categoria = apps.get_model('estoque', 'Categoria')
    nomes = [c[0] for c in CATEGORIAS]
    Categoria.objects.filter(nome__in=nomes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0003_reestruturacao_unidade_perfil'),
    ]

    operations = [
        migrations.RunPython(criar_categorias, remover_categorias),
    ]
