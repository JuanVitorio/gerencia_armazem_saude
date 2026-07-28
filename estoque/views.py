from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q, Sum
from django.forms import ValidationError
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView, View,
)
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    CategoriaForm, FornecedorForm, MovimentacaoForm, ProdutoFiltroForm, ProdutoForm,
)
from .models import Categoria, Fornecedor, Movimentacao, Produto


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'estoque/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        produtos = Produto.objects.filter(ativo=True)
        context['total_produtos'] = produtos.count()
        context['total_itens'] = produtos.aggregate(total=Sum('quantidade'))['total'] or 0
        context['valor_total_estoque'] = sum(p.valor_total_estoque for p in produtos)
        context['produtos_estoque_baixo'] = produtos.filter(
            quantidade__lte=F('quantidade_minima')
        ).order_by('quantidade')
        context['ultimas_movimentacoes'] = Movimentacao.objects.select_related('produto')[:10]
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
            apenas_estoque_baixo = self.filtro_form.cleaned_data.get('apenas_estoque_baixo')
            if termo:
                queryset = queryset.filter(
                    Q(nome__icontains=termo) | Q(sku__icontains=termo) | Q(codigo_barras__icontains=termo)
                )
            if categoria:
                queryset = queryset.filter(categoria=categoria)
            if apenas_estoque_baixo:
                queryset = queryset.filter(quantidade__lte=F('quantidade_minima'))
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
