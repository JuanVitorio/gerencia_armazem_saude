from django.contrib import admin

from .models import Categoria, EventoFolga, Funcionario, LancamentoFolga, Movimentacao, PerfilUsuario, Produto, Unidade


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'limite_estoque_baixo', 'criado_em')
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
    list_display = (
        'nome', 'unidade', 'categoria', 'quantidade', 'unidade_medida',
        'limite_estoque_baixo_calculado', 'data_validade', 'ativo',
    )
    list_filter = ('categoria', 'unidade', 'ativo')
    search_fields = ('nome', 'sku', 'lote', 'detalhes')
    autocomplete_fields = ('categoria', 'unidade')
    fieldsets = (
        (None, {
            'fields': (
                'unidade', 'categoria', 'nome', 'detalhes', 'descricao',
                'sku', 'lote', 'data_validade', 'unidade_medida', 'quantidade', 'ativo',
            ),
        }),
        ('Regra de estoque baixo (parametrizável — pendente de validação)', {
            'classes': ('collapse',),
            'fields': ('limite_estoque_baixo', 'estoque_maximo', 'percentual_alerta_estoque'),
            'description': (
                'Deixe tudo em branco para usar o limite padrão do sistema ou o limite '
                'da categoria. Veja Produto.limite_estoque_baixo_calculado em models.py '
                'para a ordem de prioridade entre esses campos.'
            ),
        }),
    )

    @admin.display(description='Limite Baixo (calculado)')
    def limite_estoque_baixo_calculado(self, obj):
        return obj.limite_estoque_baixo_calculado


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('produto', 'tipo', 'quantidade', 'usuario', 'data')
    list_filter = ('tipo', 'data')
    search_fields = ('produto__nome', 'produto__sku')
    autocomplete_fields = ('produto',)
    readonly_fields = ('data',)


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cargo', 'matricula', 'unidade', 'ativo', 'saldo_dias')
    list_filter = ('unidade', 'ativo')
    search_fields = ('nome', 'cargo', 'matricula')
    autocomplete_fields = ('unidade',)


@admin.register(EventoFolga)
class EventoFolgaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data', 'dias', 'total_participantes', 'usuario', 'criado_em')
    list_filter = ('data',)
    search_fields = ('nome', 'descricao')
    readonly_fields = ('criado_em',)


@admin.register(LancamentoFolga)
class LancamentoFolgaAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'tipo', 'dias', 'data_referencia', 'evento', 'usuario', 'criado_em')
    list_filter = ('tipo', 'data_referencia')
    search_fields = ('funcionario__nome', 'motivo')
    autocomplete_fields = ('funcionario', 'evento')
    readonly_fields = ('criado_em',)