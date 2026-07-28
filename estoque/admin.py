from django.contrib import admin

from .models import Categoria, Fornecedor, Movimentacao, Produto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'criado_em')
    list_filter = ('tipo',)
    search_fields = ('nome',)


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnpj_cpf', 'telefone', 'email', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'cnpj_cpf', 'email')


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = (
        'nome', 'sku', 'categoria', 'fornecedor', 'quantidade',
        'unidade_medida', 'data_validade', 'ativo',
    )
    list_filter = ('categoria', 'fornecedor', 'ativo')
    search_fields = ('nome', 'sku', 'codigo_barras', 'lote')
    autocomplete_fields = ('categoria', 'fornecedor')


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'tipo', 'quantidade', 'usuario', 'data')
    list_filter = ('tipo', 'data')
    search_fields = ('produto__nome', 'produto__sku')
    autocomplete_fields = ('produto',)
    readonly_fields = ('data',)