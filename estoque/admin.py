from django.contrib import admin

from .models import Categoria, Movimentacao, PerfilUsuario, Produto, Unidade


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'criado_em')
    list_filter = ('tipo',)
    search_fields = ('nome',)


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'ativa', 'criado_em')
    list_filter = ('tipo', 'ativa')
    search_fields = ('nome',)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'unidade')
    list_filter = ('unidade',)
    search_fields = ('usuario__username', 'unidade__nome')
    autocomplete_fields = ('usuario',)


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'unidade', 'categoria', 'quantidade', 'unidade_medida', 'data_validade', 'ativo')
    list_filter = ('categoria', 'unidade', 'ativo')
    search_fields = ('nome', 'sku', 'lote', 'detalhes')
    autocomplete_fields = ('categoria', 'unidade')


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'tipo', 'quantidade', 'usuario', 'data')
    list_filter = ('tipo', 'data')
    search_fields = ('produto__nome', 'produto__sku')
    autocomplete_fields = ('produto',)
    readonly_fields = ('data',)