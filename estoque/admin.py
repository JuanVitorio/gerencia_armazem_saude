from django.contrib import admin, messages

from .models import Categoria, EventoFolga, Funcionario, LancamentoFolga, Movimentacao, PerfilUsuario, Produto, Unidade


class SemUnidadeFilter(admin.SimpleListFilter):
    """
    Filtro para achar de uma vez os produtos que ficaram com unidade=None
    (cadastrados por um Administrador antes do formulário ganhar o campo
    Unidade) — esses produtos não aparecem em nenhuma pesquisa por
    estoque, incluindo a da Requisição.
    """
    title = 'possui unidade'
    parameter_name = 'possui_unidade'

    def lookups(self, request, model_admin):
        return (
            ('nao', 'Sem unidade (não aparece em nenhuma pesquisa)'),
            ('sim', 'Com unidade'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'nao':
            return queryset.filter(unidade__isnull=True)
        if self.value() == 'sim':
            return queryset.filter(unidade__isnull=False)
        return queryset


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
    list_filter = ('categoria', 'unidade', SemUnidadeFilter, 'ativo')
    search_fields = ('nome', 'sku', 'lote', 'detalhes')
    autocomplete_fields = ('categoria', 'unidade')
    actions = ['atribuir_ao_estoque_central']
    # Com todos os produtos numa página só, "Selecionar todos os N produtos"
    # (link que aparece após marcar o checkbox do cabeçalho) já pega todos
    # de uma vez, sem precisar passar de página.
    list_per_page = 200
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

    @admin.action(description='Atribuir ao estoque central (Secretaria) os produtos selecionados')
    def atribuir_ao_estoque_central(self, request, queryset):
        centrais = Unidade.objects.filter(tipo=Unidade.SECRETARIA, ativa=True)
        total_centrais = centrais.count()
        if total_centrais != 1:
            self.message_user(
                request,
                f'Encontrei {total_centrais} unidade(s) do tipo Secretaria ativa(s) — a atribuição em massa '
                'só funciona quando existe exatamente uma. Ajuste em Unidades (deixe só a Secretaria correta '
                'como ativa) e tente de novo, ou escolha a unidade manualmente em cada produto.',
                level=messages.ERROR,
            )
            return
        central = centrais.first()
        atualizados = queryset.update(unidade=central)
        self.message_user(
            request,
            f'{atualizados} produto(s) atribuído(s) a "{central}".',
            level=messages.SUCCESS,
        )


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