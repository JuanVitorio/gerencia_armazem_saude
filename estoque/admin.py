from django.contrib import admin

from .models import Categoria, Funcionario, LancamentoBancoHoras, Movimentacao, PerfilUsuario, Produto, Unidade


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


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cargo', 'matricula', 'unidade', 'ativo', 'saldo_horas')
    list_filter = ('unidade', 'ativo')
    search_fields = ('nome', 'cargo', 'matricula')
    autocomplete_fields = ('unidade',)


@admin.register(LancamentoBancoHoras)
class LancamentoBancoHorasAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'tipo', 'horas', 'data_referencia', 'usuario', 'criado_em')
    list_filter = ('tipo', 'data_referencia')
    search_fields = ('funcionario__nome', 'motivo')
    autocomplete_fields = ('funcionario',)
    readonly_fields = ('criado_em',)