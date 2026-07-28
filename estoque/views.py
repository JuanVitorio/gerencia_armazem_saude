from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.forms import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView, View,
)

from . import relatorios
from .forms import (
    CategoriaForm, FornecedorForm, MovimentacaoForm, ProdutoFiltroForm, ProdutoForm,
)
from .models import Categoria, Fornecedor, Movimentacao, Produto


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Tela inicial enxuta: só o que precisa de atenção imediata no dia a
    dia do posto/secretaria (estoque baixo, validade e movimentações
    recentes) — sem cartões ou números que não ajudam a agir.
    """
    template_name = 'estoque/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        limite_validade = hoje + timedelta(days=settings.DIAS_ALERTA_VENCIMENTO)

        produtos = Produto.objects.filter(ativo=True).select_related('categoria')

        context['produtos_estoque_baixo'] = produtos.filter(
            quantidade__lte=settings.LIMITE_ESTOQUE_BAIXO
        ).order_by('quantidade')
        context['produtos_validade'] = produtos.filter(
            data_validade__isnull=False, data_validade__lte=limite_validade
        ).order_by('data_validade')
        context['ultimas_movimentacoes'] = Movimentacao.objects.select_related('produto')[:8]
        return context


# ---------- Categoria ----------

class CategoriaListView(LoginRequiredMixin, ListView):
    model = Categoria
    template_name = 'estoque/categoria_list.html'
    context_object_name = 'categorias'
    paginate_by = 20


class CategoriaDetailView(LoginRequiredMixin, DetailView):
    model = Categoria
    template_name = 'estoque/categoria_detail.html'
    context_object_name = 'categoria'


class CategoriaCreateView(LoginRequiredMixin, CreateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = 'estoque/categoria_form.html'
    success_url = reverse_lazy('estoque:categoria_list')

    def form_valid(self, form):
        messages.success(self.request, 'Categoria cadastrada com sucesso.')
        return super().form_valid(form)


class CategoriaUpdateView(LoginRequiredMixin, UpdateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = 'estoque/categoria_form.html'
    success_url = reverse_lazy('estoque:categoria_list')

    def form_valid(self, form):
        messages.success(self.request, 'Categoria atualizada com sucesso.')
        return super().form_valid(form)


class CategoriaDeleteView(LoginRequiredMixin, DeleteView):
    model = Categoria
    template_name = 'estoque/confirm_delete.html'
    success_url = reverse_lazy('estoque:categoria_list')

    def form_valid(self, form):
        messages.success(self.request, 'Categoria removida com sucesso.')
        return super().form_valid(form)


# ---------- Fornecedor ----------

class FornecedorListView(LoginRequiredMixin, ListView):
    model = Fornecedor
    template_name = 'estoque/fornecedor_list.html'
    context_object_name = 'fornecedores'
    paginate_by = 20


class FornecedorDetailView(LoginRequiredMixin, DetailView):
    model = Fornecedor
    template_name = 'estoque/fornecedor_detail.html'
    context_object_name = 'fornecedor'


class FornecedorCreateView(LoginRequiredMixin, CreateView):
    model = Fornecedor
    form_class = FornecedorForm
    template_name = 'estoque/fornecedor_form.html'
    success_url = reverse_lazy('estoque:fornecedor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Fornecedor cadastrado com sucesso.')
        return super().form_valid(form)


class FornecedorUpdateView(LoginRequiredMixin, UpdateView):
    model = Fornecedor
    form_class = FornecedorForm
    template_name = 'estoque/fornecedor_form.html'
    success_url = reverse_lazy('estoque:fornecedor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Fornecedor atualizado com sucesso.')
        return super().form_valid(form)


class FornecedorDeleteView(LoginRequiredMixin, DeleteView):
    model = Fornecedor
    template_name = 'estoque/confirm_delete.html'
    success_url = reverse_lazy('estoque:fornecedor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Fornecedor removido com sucesso.')
        return super().form_valid(form)


# ---------- Produto ----------

class ProdutoListView(LoginRequiredMixin, ListView):
    model = Produto
    template_name = 'estoque/produto_list.html'
    context_object_name = 'produtos'
    paginate_by = 20

    def get_queryset(self):
        queryset = Produto.objects.select_related('categoria', 'fornecedor')
        self.filtro_form = ProdutoFiltroForm(self.request.GET or None)
        if self.filtro_form.is_valid():
            termo = self.filtro_form.cleaned_data.get('q')
            categoria = self.filtro_form.cleaned_data.get('categoria')
            situacao = self.filtro_form.cleaned_data.get('situacao')
            if termo:
                queryset = queryset.filter(
                    Q(nome__icontains=termo) | Q(sku__icontains=termo) |
                    Q(codigo_barras__icontains=termo) | Q(categoria__nome__icontains=termo) |
                    Q(lote__icontains=termo)
                )
            if categoria:
                queryset = queryset.filter(categoria=categoria)
            if situacao == 'BAIXO':
                queryset = queryset.filter(quantidade__lte=settings.LIMITE_ESTOQUE_BAIXO)
            elif situacao == 'VENCIDO':
                queryset = queryset.filter(
                    data_validade__isnull=False, data_validade__lt=timezone.localdate()
                )
            elif situacao == 'VENCENDO':
                hoje = timezone.localdate()
                queryset = queryset.filter(
                    data_validade__isnull=False, data_validade__gte=hoje,
                    data_validade__lte=hoje + timedelta(days=settings.DIAS_ALERTA_VENCIMENTO)
                )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtro_form'] = self.filtro_form
        return context


class ProdutoDetailView(LoginRequiredMixin, DetailView):
    model = Produto
    template_name = 'estoque/produto_detail.html'
    context_object_name = 'produto'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['movimentacoes'] = self.object.movimentacoes.all()[:20]
        return context


class ProdutoCreateView(LoginRequiredMixin, CreateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'estoque/produto_form.html'
    success_url = reverse_lazy('estoque:produto_list')

    def form_valid(self, form):
        messages.success(self.request, 'Produto cadastrado com sucesso.')
        return super().form_valid(form)


class ProdutoUpdateView(LoginRequiredMixin, UpdateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'estoque/produto_form.html'
    success_url = reverse_lazy('estoque:produto_list')

    def form_valid(self, form):
        messages.success(self.request, 'Produto atualizado com sucesso.')
        return super().form_valid(form)


class ProdutoDeleteView(LoginRequiredMixin, DeleteView):
    model = Produto
    template_name = 'estoque/confirm_delete.html'
    success_url = reverse_lazy('estoque:produto_list')

    def form_valid(self, form):
        messages.success(self.request, 'Produto removido com sucesso.')
        return super().form_valid(form)


class MovimentacaoRapidaView(LoginRequiredMixin, View):
    """Ação de 1 clique para dar entrada/saída de estoque direto da listagem."""

    def post(self, request, pk):
        produto = get_object_or_404(Produto, pk=pk)
        tipo = request.POST.get('tipo')
        try:
            quantidade = int(request.POST.get('quantidade', 1))
        except (TypeError, ValueError):
            quantidade = 0

        if tipo not in (Movimentacao.ENTRADA, Movimentacao.SAIDA) or quantidade <= 0:
            messages.error(request, 'Informe uma quantidade válida.')
        else:
            movimentacao = Movimentacao(
                produto=produto, tipo=tipo, quantidade=quantidade,
                motivo='Ajuste rápido', usuario=request.user,
            )
            try:
                movimentacao.save()
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages))
            else:
                acao = 'Entrada' if tipo == Movimentacao.ENTRADA else 'Saída'
                messages.success(request, f'{acao} de {quantidade} un. registrada para "{produto.nome}".')

        next_url = request.POST.get('next') or reverse('estoque:produto_list')
        return redirect(next_url)


# ---------- Movimentação ----------

class MovimentacaoListView(LoginRequiredMixin, ListView):
    model = Movimentacao
    template_name = 'estoque/movimentacao_list.html'
    context_object_name = 'movimentacoes'
    paginate_by = 30

    def get_queryset(self):
        return Movimentacao.objects.select_related('produto', 'usuario')


class MovimentacaoCreateView(LoginRequiredMixin, CreateView):
    model = Movimentacao
    form_class = MovimentacaoForm
    template_name = 'estoque/movimentacao_form.html'
    success_url = reverse_lazy('estoque:movimentacao_list')

    def get_initial(self):
        initial = super().get_initial()
        produto_id = self.request.GET.get('produto')
        if produto_id:
            initial['produto'] = produto_id
        return initial

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        try:
            response = super().form_valid(form)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, 'Movimentação registrada com sucesso.')
        return response


# ---------- Relatórios ----------

class RelatorioListView(LoginRequiredMixin, TemplateView):
    """Página com os relatórios em PDF disponíveis para download/impressão."""
    template_name = 'estoque/relatorio_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        context['hoje'] = hoje.isoformat()
        context['inicio_mes'] = hoje.replace(day=1).isoformat()
        context['dias_alerta_vencimento'] = settings.DIAS_ALERTA_VENCIMENTO
        return context


class RelatorioGerarView(LoginRequiredMixin, View):
    """Gera o PDF do relatório solicitado e devolve para visualização/download."""

    NOMES_ARQUIVO = {
        'estoque_atual': 'estoque_atual',
        'estoque_baixo': 'estoque_baixo',
        'validade': 'produtos_vencidos_e_proximos_do_vencimento',
        'movimentacoes': 'movimentacoes_do_periodo',
        'entradas': 'entradas_do_periodo',
        'saidas': 'saidas_do_periodo',
        'gastos': 'gastos_do_periodo',
        'por_categoria': 'estoque_por_categoria',
    }

    def get(self, request, tipo):
        hoje = timezone.localdate()
        data_inicio = self._parse_data(request.GET.get('data_inicio')) or hoje.replace(day=1)
        data_fim = self._parse_data(request.GET.get('data_fim')) or hoje
        dias_raw = request.GET.get('dias')
        dias = int(dias_raw) if dias_raw and dias_raw.isdigit() else None

        geradores = {
            'estoque_atual': lambda: relatorios.relatorio_estoque_atual(),
            'estoque_baixo': lambda: relatorios.relatorio_estoque_baixo(),
            'validade': lambda: relatorios.relatorio_validade(dias),
            'movimentacoes': lambda: relatorios.relatorio_movimentacoes(data_inicio, data_fim),
            'entradas': lambda: relatorios.relatorio_movimentacoes(data_inicio, data_fim, tipo=Movimentacao.ENTRADA),
            'saidas': lambda: relatorios.relatorio_movimentacoes(data_inicio, data_fim, tipo=Movimentacao.SAIDA),
            'gastos': lambda: relatorios.relatorio_gastos(data_inicio, data_fim),
            'por_categoria': lambda: relatorios.relatorio_por_categoria(),
        }

        gerar = geradores.get(tipo)
        if gerar is None:
            raise Http404('Relatório não encontrado.')

        buffer = gerar()
        nome_arquivo = self.NOMES_ARQUIVO.get(tipo, tipo)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{nome_arquivo}.pdf"'
        return response

    @staticmethod
    def _parse_data(valor):
        if not valor:
            return None
        try:
            return datetime.strptime(valor, '%Y-%m-%d').date()
        except ValueError:
            return None