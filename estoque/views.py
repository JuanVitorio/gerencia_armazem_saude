from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.forms import ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView,
    TemplateView, UpdateView, View,
)

from . import relatorios
from .forms import (
    EventoFolgaForm, FuncionarioFiltroForm, FuncionarioForm, LancamentoFolgaForm,
    MovimentacaoFiltroForm, MovimentacaoForm,
    PerfilUsuarioForm, ProdutoFiltroForm, ProdutoForm,
    UsuarioForm,
)
from .models import (
    Categoria, EventoFolga, Funcionario, LancamentoFolga, Movimentacao, PerfilUsuario, Produto, Unidade,
)


# ---------------------------------------------------------------------------
# Mixins de acesso
# ---------------------------------------------------------------------------

class AdminRequiredMixin(UserPassesTestMixin):
    """Permite acesso apenas a superusuários, staff ou usuários sem unidade vinculada."""

    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return True
        try:
            return user.perfil.is_admin
        except PerfilUsuario.DoesNotExist:
            return False


def get_unidade_do_usuario(user):
    """Retorna a Unidade do usuário logado ou None (admin vê tudo)."""
    if user.is_superuser or user.is_staff:
        return None
    try:
        return user.perfil.unidade
    except PerfilUsuario.DoesNotExist:
        return None


def filtrar_produtos_por_usuario(user, queryset=None):
    """Filtra o queryset de Produto pela unidade do usuário."""
    if queryset is None:
        queryset = Produto.objects.all()
    unidade = get_unidade_do_usuario(user)
    if unidade is not None:
        queryset = queryset.filter(unidade=unidade)
    return queryset


def filtrar_movimentacoes_por_usuario(user, queryset=None):
    """Filtra o queryset de Movimentacao pela unidade do usuário (via produto__unidade)."""
    if queryset is None:
        queryset = Movimentacao.objects.select_related(
            'produto', 'produto__categoria', 'produto__unidade', 'usuario',
        )
    unidade = get_unidade_do_usuario(user)
    if unidade is not None:
        queryset = queryset.filter(produto__unidade=unidade)
    return queryset


def aplicar_filtro_produtos(queryset, filtro_form):
    """
    Aplica os filtros de busca/categoria/situação de um ProdutoFiltroForm
    válido a um queryset de Produto. Compartilhado entre ProdutoListView e
    UnidadeDetailView (pesquisa de estoque dentro de uma unidade).
    """
    if not filtro_form.is_valid():
        return queryset
    termo = filtro_form.cleaned_data.get('q')
    categoria = filtro_form.cleaned_data.get('categoria')
    situacao = filtro_form.cleaned_data.get('situacao')
    if termo:
        queryset = queryset.filter(
            Q(nome__icontains=termo) | Q(sku__icontains=termo) |
            Q(lote__icontains=termo) | Q(detalhes__icontains=termo) |
            Q(categoria__nome__icontains=termo)
        )
    if categoria:
        queryset = queryset.filter(categoria=categoria)
    hoje = timezone.localdate()
    if situacao == 'BAIXO':
        # Mesma regra dinâmica/parametrizável do dashboard (ver
        # Produto.limite_estoque_baixo_calculado em models.py) — precisa ser
        # avaliada em Python porque o limite pode variar por produto/
        # categoria/percentual, então não dá pra fazer com um único
        # `.filter()` no banco. Mantido consistente de propósito: é para
        # onde o contador "Estoque Baixo" do dashboard linka.
        queryset = [p for p in queryset if p.estoque_baixo]
    elif situacao == 'VENCIDO':
        queryset = queryset.filter(data_validade__isnull=False, data_validade__lt=hoje)
    elif situacao == 'VENCENDO':
        queryset = queryset.filter(
            data_validade__isnull=False,
            data_validade__gte=hoje,
            data_validade__lte=hoje + timedelta(days=settings.DIAS_ALERTA_VENCIMENTO),
        )
    return queryset


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'estoque/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        limite_validade = hoje + timedelta(days=settings.DIAS_ALERTA_VENCIMENTO)

        produtos = filtrar_produtos_por_usuario(
            self.request.user,
            Produto.objects.filter(ativo=True).select_related('categoria', 'unidade'),
        )

        # --------------------------------------------------------------------
        # Estoque baixo — regra ATUALIZADA para ser dinâmica e parametrizável
        # por produto, percentual ou categoria (antes era um limite único e
        # global). A lógica de resolução do limite fica em
        # Produto.limite_estoque_baixo_calculado (models.py), bem comentada
        # ali para facilitar a validação de negócio; aqui só consumimos a
        # property `estoque_baixo`, que já aplica essa regra.
        #
        # Por depender de campos por produto/categoria (não dá pra resolver
        # com um único `.filter()` no banco de forma simples), o filtro é
        # feito em Python sobre o queryset já restrito à unidade do usuário
        # — no volume de produtos de um posto/secretaria isso é barato.
        # TODO (validação posterior): se o catálogo crescer muito, considerar
        # mover esse cálculo para o banco (ex: anotar limite via Case/When).
        # --------------------------------------------------------------------
        produtos_com_estoque_baixo = [p for p in produtos if p.estoque_baixo]
        produtos_com_estoque_baixo.sort(key=lambda p: p.quantidade)

        validade_alerta = produtos.filter(
            data_validade__isnull=False,
            data_validade__lte=limite_validade,
        ).order_by('data_validade')

        # Movimentações filtradas pela unidade do usuário
        movs_qs = Movimentacao.objects.select_related('produto', 'usuario')
        unidade = get_unidade_do_usuario(self.request.user)
        if unidade is not None:
            movs_qs = movs_qs.filter(produto__unidade=unidade)

        context.update({
            'total_produtos': produtos.count(),
            'total_estoque_baixo': len(produtos_com_estoque_baixo),
            'total_vencidos': produtos.filter(
                data_validade__isnull=False,
                data_validade__lt=hoje,
            ).count(),
            'produtos_estoque_baixo': produtos_com_estoque_baixo[:10],
            'produtos_validade': validade_alerta[:10],
            'ultimas_movimentacoes': movs_qs[:10],
            'unidade_atual': unidade,
        })
        return context


# ---------------------------------------------------------------------------
# Unidade
# ---------------------------------------------------------------------------

class UnidadeListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Unidade
    template_name = 'estoque/unidade_list.html'
    context_object_name = 'unidades'

    def get_queryset(self):
        return Unidade.objects.annotate(total_produtos=Count('produtos')).order_by('tipo', 'nome')


class UnidadeDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = Unidade
    template_name = 'estoque/unidade_detail.html'
    context_object_name = 'unidade'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['membros'] = self.object.membros.select_related('usuario').all()
        context['total_produtos'] = self.object.produtos.filter(ativo=True).count()
        context['funcionarios_unidade'] = self.object.funcionarios.filter(ativo=True).order_by('nome')

        # Estoque da unidade, pesquisável (mesmo ProdutoFiltroForm da tela de Produtos)
        # — é a tela que o admin usa pra checar rapidamente "tem vacina no Posto A?".
        produtos_qs = self.object.produtos.filter(ativo=True).select_related('categoria')
        self.filtro_form = ProdutoFiltroForm(self.request.GET or None)
        produtos_qs = aplicar_filtro_produtos(produtos_qs, self.filtro_form).order_by('nome')

        paginator = Paginator(produtos_qs, self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get('page'))

        context['filtro_form'] = self.filtro_form
        context['produtos'] = page_obj
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['is_paginated'] = page_obj.has_other_pages()
        return context


class UnidadeCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Unidade
    fields = ['nome', 'tipo', 'descricao', 'ativa']
    template_name = 'estoque/unidade_form.html'
    success_url = reverse_lazy('estoque:unidade_list')

    def form_valid(self, form):
        messages.success(self.request, 'Unidade cadastrada com sucesso.')
        return super().form_valid(form)


class UnidadeUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Unidade
    fields = ['nome', 'tipo', 'descricao', 'ativa']
    template_name = 'estoque/unidade_form.html'
    success_url = reverse_lazy('estoque:unidade_list')

    def form_valid(self, form):
        messages.success(self.request, 'Unidade atualizada com sucesso.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Produto
# ---------------------------------------------------------------------------

class ProdutoListView(LoginRequiredMixin, ListView):
    model = Produto
    template_name = 'estoque/produto_list.html'
    context_object_name = 'produtos'
    paginate_by = 30

    def get_queryset(self):
        qs = filtrar_produtos_por_usuario(
            self.request.user,
            Produto.objects.select_related('categoria', 'unidade'),
        )
        self.filtro_form = ProdutoFiltroForm(self.request.GET or None)
        return aplicar_filtro_produtos(qs, self.filtro_form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtro_form'] = self.filtro_form
        context['unidade_atual'] = get_unidade_do_usuario(self.request.user)
        return context


class ProdutoDetailView(LoginRequiredMixin, DetailView):
    model = Produto
    template_name = 'estoque/produto_detail.html'
    context_object_name = 'produto'

    def get_queryset(self):
        return filtrar_produtos_por_usuario(
            self.request.user, Produto.objects.select_related('categoria', 'unidade')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['movimentacoes'] = self.object.movimentacoes.select_related('usuario').all()[:30]
        return context


class ProdutoCreateView(LoginRequiredMixin, View):
    """
    Cadastro rápido: após salvar, permanece na tela com o formulário limpo
    e o foco no primeiro campo. Suporta JSON para resposta AJAX.
    """
    template_name = 'estoque/produto_form.html'

    def _get_unidade(self):
        return get_unidade_do_usuario(self.request.user)

    def get(self, request, *args, **kwargs):
        from django.shortcuts import render
        form = ProdutoForm()
        return render(request, self.template_name, {
            'form': form,
            'modo_rapido': True,
            'unidade_atual': self._get_unidade(),
        })

    def post(self, request, *args, **kwargs):
        from django.shortcuts import render
        form = ProdutoForm(request.POST)
        if form.is_valid():
            produto = form.save(commit=False)
            unidade = self._get_unidade()
            if unidade:
                produto.unidade = unidade
            produto.save()
            messages.success(request, f'✓ "{produto.nome}" cadastrado. Próximo produto:')
            # Redireciona para GET (PRG pattern) para limpar o form
            return redirect(reverse('estoque:produto_create'))
        return render(request, self.template_name, {
            'form': form,
            'modo_rapido': True,
            'unidade_atual': self._get_unidade(),
        })


class ProdutoUpdateView(LoginRequiredMixin, UpdateView):
    model = Produto
    form_class = ProdutoForm
    template_name = 'estoque/produto_form.html'

    def get_queryset(self):
        return filtrar_produtos_por_usuario(self.request.user)

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        messages.success(self.request, 'Produto atualizado com sucesso.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modo_rapido'] = False
        return context


class ProdutoDeleteView(LoginRequiredMixin, DeleteView):
    model = Produto
    template_name = 'estoque/confirm_delete.html'
    success_url = reverse_lazy('estoque:produto_list')

    def get_queryset(self):
        return filtrar_produtos_por_usuario(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Produto removido com sucesso.')
        return super().form_valid(form)


class MovimentacaoRapidaView(LoginRequiredMixin, View):
    """Entrada/saída de 1 clique direto da listagem de produtos."""

    def post(self, request, pk):
        qs = filtrar_produtos_por_usuario(request.user)
        produto = get_object_or_404(qs, pk=pk)
        tipo = request.POST.get('tipo')
        try:
            quantidade = int(request.POST.get('quantidade', 1))
        except (TypeError, ValueError):
            quantidade = 0

        if tipo not in (Movimentacao.ENTRADA, Movimentacao.SAIDA) or quantidade <= 0:
            messages.error(request, 'Informe uma quantidade válida.')
        else:
            motivo = request.POST.get('motivo', '').strip() or 'Ajuste rápido'
            mov = Movimentacao(
                produto=produto, tipo=tipo, quantidade=quantidade,
                motivo=motivo, usuario=request.user,
            )
            try:
                mov.save()
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages))
            else:
                acao = 'Entrada' if tipo == Movimentacao.ENTRADA else 'Saída'
                messages.success(
                    request,
                    f'{acao} de {quantidade} {produto.get_unidade_medida_display()} '
                    f'registrada para "{produto.nome}".',
                )

        next_url = request.POST.get('next') or reverse('estoque:produto_list')
        return redirect(next_url)


# ---------------------------------------------------------------------------
# Movimentação
# ---------------------------------------------------------------------------

class MovimentacaoListView(LoginRequiredMixin, ListView):
    model = Movimentacao
    template_name = 'estoque/movimentacao_list.html'
    context_object_name = 'movimentacoes'
    paginate_by = 40

    def get_queryset(self):
        qs = filtrar_movimentacoes_por_usuario(self.request.user)

        self.filtro_form = MovimentacaoFiltroForm(self.request.GET or None)
        if self.filtro_form.is_valid():
            termo = self.filtro_form.cleaned_data.get('q')
            tipo = self.filtro_form.cleaned_data.get('tipo')
            data_inicio = self.filtro_form.cleaned_data.get('data_inicio')
            data_fim = self.filtro_form.cleaned_data.get('data_fim')
            if termo:
                qs = qs.filter(produto__nome__icontains=termo)
            if tipo:
                qs = qs.filter(tipo=tipo)
            if data_inicio:
                qs = qs.filter(data__date__gte=data_inicio)
            if data_fim:
                qs = qs.filter(data__date__lte=data_fim)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtro_form'] = self.filtro_form
        return context


class MovimentacaoDetailView(LoginRequiredMixin, DetailView):
    model = Movimentacao
    template_name = 'estoque/movimentacao_detail.html'
    context_object_name = 'movimentacao'

    def get_queryset(self):
        return filtrar_movimentacoes_por_usuario(self.request.user)


class MovimentacaoDeleteView(LoginRequiredMixin, DeleteView):
    """
    Exclui um registro de movimentação e ESTORNA automaticamente o efeito
    dela no estoque do produto/unidade correspondente:

      - Movimentação de ENTRADA: ela tinha SOMADO `quantidade` ao estoque
        quando foi criada (Movimentacao.save()). Excluir precisa SUBTRAIR
        de volta. Se o estoque atual for menor que essa quantidade — ou
        seja, parte dela já foi consumida por saídas registradas depois —
        a exclusão é bloqueada, porque estornar deixaria o estoque negativo.

      - Movimentação de SAÍDA: ela tinha SUBTRAÍDO `quantidade` do estoque.
        Excluir precisa DEVOLVER essa quantidade. Sempre seguro (nunca
        deixa o estoque negativo), então não tem bloqueio nesse caso.

    O estorno e a exclusão do registro acontecem na mesma transação — ou os
    dois acontecem, ou nenhum (evita estoque e histórico ficarem
    dessincronizados se algo falhar no meio do caminho).
    """
    model = Movimentacao
    template_name = 'estoque/confirm_delete.html'
    success_url = reverse_lazy('estoque:movimentacao_list')

    def get_queryset(self):
        return filtrar_movimentacoes_por_usuario(self.request.user)

    def form_valid(self, form):
        movimentacao = self.object
        produto = movimentacao.produto

        if movimentacao.tipo == Movimentacao.ENTRADA and produto.quantidade < movimentacao.quantidade:
            messages.error(
                self.request,
                f'Não é possível excluir esta entrada: o estoque atual de "{produto.nome}" '
                f'({produto.quantidade}) é menor que a quantidade dela ({movimentacao.quantidade}) '
                f'— parte já foi usada em saídas registradas depois. Ajuste o estoque manualmente '
                f'antes de excluir, se necessário.',
            )
            return redirect('estoque:movimentacao_list')

        produto_nome = produto.nome
        tipo_label = movimentacao.get_tipo_display()
        quantidade = movimentacao.quantidade

        with transaction.atomic():
            if movimentacao.tipo == Movimentacao.ENTRADA:
                produto.quantidade -= quantidade
            else:
                produto.quantidade += quantidade
            produto.save(update_fields=['quantidade', 'atualizado_em'])
            response = super().form_valid(form)

        messages.success(
            self.request,
            f'{tipo_label} de {quantidade} × "{produto_nome}" excluída e estornada no estoque com sucesso.',
        )
        return response


class MovimentacaoCreateView(LoginRequiredMixin, CreateView):
    model = Movimentacao
    form_class = MovimentacaoForm
    template_name = 'estoque/movimentacao_form.html'
    success_url = reverse_lazy('estoque:movimentacao_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['unidade'] = get_unidade_do_usuario(self.request.user)
        return kwargs

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


# ---------------------------------------------------------------------------
# Gestão de Usuários (apenas Admin)
# ---------------------------------------------------------------------------

class UsuarioListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = User
    template_name = 'estoque/usuario_list.html'
    context_object_name = 'usuarios'

    def get_queryset(self):
        return User.objects.select_related('perfil', 'perfil__unidade').order_by('username')


class UsuarioCreateView(LoginRequiredMixin, AdminRequiredMixin, View):
    template_name = 'estoque/usuario_form.html'

    def get(self, request):
        from django.shortcuts import render
        return render(request, self.template_name, {
            'form_usuario': UsuarioForm(),
            'form_perfil': PerfilUsuarioForm(),
        })

    def post(self, request):
        from django.shortcuts import render
        form_usuario = UsuarioForm(request.POST)
        form_perfil = PerfilUsuarioForm(request.POST)
        if form_usuario.is_valid() and form_perfil.is_valid():
            usuario = form_usuario.save(commit=False)
            senha = form_usuario.cleaned_data.get('password1')
            if senha:
                usuario.set_password(senha)
            usuario.save()
            perfil = form_perfil.save(commit=False)
            perfil.usuario = usuario
            perfil.save()
            messages.success(request, f'Usuário "{usuario.username}" criado com sucesso.')
            return redirect(reverse('estoque:usuario_list'))
        return render(request, self.template_name, {
            'form_usuario': form_usuario,
            'form_perfil': form_perfil,
        })


class UsuarioUpdateView(LoginRequiredMixin, AdminRequiredMixin, View):
    template_name = 'estoque/usuario_form.html'

    def _get_user(self, pk):
        return get_object_or_404(User, pk=pk)

    def get(self, request, pk):
        from django.shortcuts import render
        usuario = self._get_user(pk)
        perfil, _ = PerfilUsuario.objects.get_or_create(usuario=usuario)
        return render(request, self.template_name, {
            'form_usuario': UsuarioForm(instance=usuario),
            'form_perfil': PerfilUsuarioForm(instance=perfil),
            'object': usuario,
        })

    def post(self, request, pk):
        from django.shortcuts import render
        usuario = self._get_user(pk)
        perfil, _ = PerfilUsuario.objects.get_or_create(usuario=usuario)
        form_usuario = UsuarioForm(request.POST, instance=usuario)
        form_perfil = PerfilUsuarioForm(request.POST, instance=perfil)
        if form_usuario.is_valid() and form_perfil.is_valid():
            usuario = form_usuario.save(commit=False)
            senha = form_usuario.cleaned_data.get('password1')
            if senha:
                usuario.set_password(senha)
            usuario.save()
            form_perfil.save()
            messages.success(request, f'Usuário "{usuario.username}" atualizado com sucesso.')
            return redirect(reverse('estoque:usuario_list'))
        return render(request, self.template_name, {
            'form_usuario': form_usuario,
            'form_perfil': form_perfil,
            'object': usuario,
        })


class UsuarioDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """
    Exclui uma conta de usuário do sistema. O PerfilUsuario relacionado é
    apagado junto (OneToOneField com on_delete=CASCADE); movimentações,
    lançamentos de folga e eventos que esse usuário registrou NÃO são
    apagados — o campo `usuario` deles vira NULL (on_delete=SET_NULL nos
    respectivos models), preservando o histórico ("Usuário removido").

    Duas travas de segurança:
      - Não deixa o usuário logado excluir a própria conta (evita se
        trancar fora do sistema sem querer).
      - Não deixa excluir contas de superusuário por aqui — essas são a
        conta "raiz" do Django e devem ser geridas pelo /admin/ ou shell.
    """
    model = User
    template_name = 'estoque/confirm_delete.html'
    success_url = reverse_lazy('estoque:usuario_list')

    def get_queryset(self):
        return User.objects.select_related('perfil')

    def form_valid(self, form):
        usuario = self.object

        if usuario.pk == self.request.user.pk:
            messages.error(self.request, 'Você não pode excluir a própria conta.')
            return redirect('estoque:usuario_list')

        if usuario.is_superuser:
            messages.error(
                self.request,
                'Contas de superusuário não podem ser excluídas por aqui — use o Django Admin.',
            )
            return redirect('estoque:usuario_list')

        username = usuario.username
        response = super().form_valid(form)
        messages.success(self.request, f'Usuário "{username}" excluído com sucesso.')
        return response


# ---------------------------------------------------------------------------
# Banco de Dias de Folga (apenas Admin/RH)
# ---------------------------------------------------------------------------

class FuncionarioListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Tela principal do banco de folgas: funcionários e seus saldos."""
    model = Funcionario
    template_name = 'estoque/funcionario_list.html'
    context_object_name = 'funcionarios'

    def get_queryset(self):
        qs = Funcionario.objects.select_related('unidade')
        self.filtro_form = FuncionarioFiltroForm(self.request.GET or None)
        if self.filtro_form.is_valid():
            termo = self.filtro_form.cleaned_data.get('q')
            unidade = self.filtro_form.cleaned_data.get('unidade')
            if termo:
                qs = qs.filter(
                    Q(nome__icontains=termo) | Q(cargo__icontains=termo) | Q(matricula__icontains=termo)
                )
            if unidade:
                qs = qs.filter(unidade=unidade)
        return qs.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtro_form'] = self.filtro_form
        return context


class FuncionarioDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = Funcionario
    template_name = 'estoque/funcionario_detail.html'
    context_object_name = 'funcionario'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lancamentos'] = self.object.lancamentos.select_related('usuario', 'evento').all()[:50]
        return context


class FuncionarioCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Funcionario
    form_class = FuncionarioForm
    template_name = 'estoque/funcionario_form.html'
    success_url = reverse_lazy('estoque:funcionario_list')

    def get_initial(self):
        initial = super().get_initial()
        unidade_id = self.request.GET.get('unidade')
        if unidade_id:
            initial['unidade'] = unidade_id
        return initial

    def form_valid(self, form):
        messages.success(self.request, f'Funcionário "{form.instance.nome}" cadastrado com sucesso.')
        return super().form_valid(form)


class FuncionarioUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Funcionario
    form_class = FuncionarioForm
    template_name = 'estoque/funcionario_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url()

    def form_valid(self, form):
        messages.success(self.request, 'Funcionário atualizado com sucesso.')
        return super().form_valid(form)


class FuncionarioDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """
    Exclui um funcionário e, junto, TODOS os lançamentos de folga dele
    (Funcionario -> LancamentoFolga é on_delete=CASCADE) — o template
    próprio (funcionario_confirm_delete.html) avisa quantos lançamentos e
    qual saldo serão perdidos antes de confirmar, já que aqui não dá pra
    reverter como no estoque.
    """
    model = Funcionario
    template_name = 'estoque/funcionario_confirm_delete.html'
    success_url = reverse_lazy('estoque:funcionario_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_lancamentos'] = self.object.lancamentos.count()
        return context

    def form_valid(self, form):
        nome = self.object.nome
        response = super().form_valid(form)
        messages.success(self.request, f'Funcionário "{nome}" e seus lançamentos de folga foram excluídos.')
        return response


class LancamentoFolgaCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Lançamento manual de crédito/débito de dia de folga — só o gestor/RH acessa."""
    model = LancamentoFolga
    form_class = LancamentoFolgaForm
    template_name = 'estoque/lancamento_folga_form.html'
    success_url = reverse_lazy('estoque:funcionario_list')

    def get_initial(self):
        initial = super().get_initial()
        funcionario_id = self.request.GET.get('funcionario')
        if funcionario_id:
            initial['funcionario'] = funcionario_id
        return initial

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        try:
            response = super().form_valid(form)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        acao = 'Crédito' if form.instance.tipo == LancamentoFolga.CREDITO else 'Débito'
        plural = 'dia' if form.instance.dias == 1 else 'dias'
        messages.success(
            self.request,
            f'{acao} de {form.instance.dias} {plural} registrado para "{form.instance.funcionario.nome}".',
        )
        return response

    def get_success_url(self):
        return self.object.funcionario.get_absolute_url()


class LancamentoFolgaDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = LancamentoFolga
    template_name = 'estoque/confirm_delete.html'

    def get_success_url(self):
        return reverse('estoque:funcionario_detail', args=[self.object.funcionario_id])

    def form_valid(self, form):
        messages.success(self.request, 'Lançamento removido com sucesso.')
        return super().form_valid(form)


class EventoFolgaListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Histórico de eventos que geraram folga (ex: Dia de Vacinação)."""
    model = EventoFolga
    template_name = 'estoque/evento_folga_list.html'
    context_object_name = 'eventos'

    def get_queryset(self):
        return EventoFolga.objects.annotate(qtd_participantes=Count('lancamentos')).order_by('-data', '-criado_em')


class EventoFolgaDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = EventoFolga
    template_name = 'estoque/evento_folga_detail.html'
    context_object_name = 'evento'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['participantes'] = self.object.lancamentos.select_related('funcionario').order_by('funcionario__nome')
        return context


class EventoFolgaCreateView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Registra o evento (ex: "Dia de Vacinação") e, para cada funcionário
    marcado no checklist do template, cria um LancamentoFolga de crédito
    apontando para este evento — é isso que dá "1 dia de folga" a cada
    participante de uma vez.
    """
    template_name = 'estoque/evento_folga_form.html'

    def get(self, request):
        return render(request, self.template_name, {
            'form': EventoFolgaForm(),
            'funcionarios': Funcionario.objects.filter(ativo=True).select_related('unidade').order_by('nome'),
        })

    def post(self, request):
        form = EventoFolgaForm(request.POST)
        funcionario_ids = request.POST.getlist('funcionarios')

        if not funcionario_ids:
            form.add_error(None, 'Selecione pelo menos um funcionário participante.')

        if form.is_valid() and funcionario_ids:
            funcionarios = Funcionario.objects.filter(pk__in=funcionario_ids, ativo=True)
            with transaction.atomic():
                evento = form.save(commit=False)
                evento.usuario = request.user
                evento.save()
                LancamentoFolga.objects.bulk_create([
                    LancamentoFolga(
                        funcionario=funcionario, tipo=LancamentoFolga.CREDITO, dias=evento.dias,
                        data_referencia=evento.data, motivo=f'Evento: {evento.nome}',
                        evento=evento, usuario=request.user,
                    )
                    for funcionario in funcionarios
                ])
            plural = 'dia' if evento.dias == 1 else 'dias'
            messages.success(
                request,
                f'Evento "{evento.nome}" registrado: {funcionarios.count()} funcionário(s) '
                f'receberam {evento.dias} {plural} de folga.',
            )
            return redirect(evento.get_absolute_url())

        return render(request, self.template_name, {
            'form': form,
            'funcionarios': Funcionario.objects.filter(ativo=True).select_related('unidade').order_by('nome'),
            'selecionados': {int(pk) for pk in funcionario_ids if pk.isdigit()},
        })


class EventoFolgaUpdateView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Edita um evento já registrado — inclusive adicionando ou removendo
    funcionários participantes — sem precisar excluir e recriar o evento.

    Regras ao salvar:
      - Campos do evento (nome/data/descrição/dias) são atualizados normalmente.
      - Funcionário que foi MARCADO agora e ainda não tinha lançamento
        deste evento → ganha um LancamentoFolga de crédito novo.
      - Funcionário que tinha lançamento deste evento e foi DESMARCADO →
        o lançamento é excluído. O saldo dele se ajusta sozinho, porque
        Funcionario.saldo_dias soma o histórico ao vivo — não precisa de
        nenhum "estorno" manual como no estoque.
      - Funcionário que CONTINUA marcado tem o lançamento sincronizado com
        os campos atuais do evento (dias/data), caso o admin tenha
        corrigido algum deles.
    """
    template_name = 'estoque/evento_folga_form.html'

    def get_object(self, pk):
        return get_object_or_404(EventoFolga, pk=pk)

    def _funcionarios_para_checklist(self, participantes_ids):
        # Sempre inclui quem já participa do evento, mesmo que tenha sido
        # desativado depois — senão ele "desaparece" do checklist e seria
        # removido do evento sem o admin ter escolhido isso.
        return Funcionario.objects.filter(
            Q(ativo=True) | Q(pk__in=participantes_ids)
        ).select_related('unidade').order_by('nome').distinct()

    def get(self, request, pk):
        evento = self.get_object(pk)
        participantes_ids = set(evento.lancamentos.values_list('funcionario_id', flat=True))
        return render(request, self.template_name, {
            'form': EventoFolgaForm(instance=evento),
            'funcionarios': self._funcionarios_para_checklist(participantes_ids),
            'selecionados': participantes_ids,
            'evento': evento,
        })

    def post(self, request, pk):
        evento = self.get_object(pk)
        form = EventoFolgaForm(request.POST, instance=evento)
        funcionario_ids = {int(v) for v in request.POST.getlist('funcionarios') if v.isdigit()}

        if not funcionario_ids:
            form.add_error(None, 'Selecione pelo menos um funcionário participante.')

        if form.is_valid() and funcionario_ids:
            with transaction.atomic():
                evento = form.save()

                ids_atuais = set(evento.lancamentos.values_list('funcionario_id', flat=True))
                remover_ids = ids_atuais - funcionario_ids
                adicionar_ids = funcionario_ids - ids_atuais
                manter_ids = ids_atuais & funcionario_ids

                if remover_ids:
                    LancamentoFolga.objects.filter(
                        evento=evento, funcionario_id__in=remover_ids,
                    ).delete()

                if adicionar_ids:
                    novos_funcionarios = Funcionario.objects.filter(pk__in=adicionar_ids)
                    LancamentoFolga.objects.bulk_create([
                        LancamentoFolga(
                            funcionario=funcionario, tipo=LancamentoFolga.CREDITO, dias=evento.dias,
                            data_referencia=evento.data, motivo=f'Evento: {evento.nome}',
                            evento=evento, usuario=request.user,
                        )
                        for funcionario in novos_funcionarios
                    ])

                if manter_ids:
                    LancamentoFolga.objects.filter(
                        evento=evento, funcionario_id__in=manter_ids,
                    ).update(dias=evento.dias, data_referencia=evento.data)

            messages.success(
                request,
                f'Evento "{evento.nome}" atualizado — {len(funcionario_ids)} participante(s), '
                f'{len(adicionar_ids)} adicionado(s), {len(remover_ids)} removido(s).',
            )
            return redirect(evento.get_absolute_url())

        participantes_ids = set(evento.lancamentos.values_list('funcionario_id', flat=True))
        return render(request, self.template_name, {
            'form': form,
            'funcionarios': self._funcionarios_para_checklist(participantes_ids | funcionario_ids),
            'selecionados': funcionario_ids,
            'evento': evento,
        })


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------

class RelatorioListView(LoginRequiredMixin, TemplateView):
    template_name = 'estoque/relatorio_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        context['hoje'] = hoje.isoformat()
        context['inicio_mes'] = hoje.replace(day=1).isoformat()
        context['dias_alerta_vencimento'] = settings.DIAS_ALERTA_VENCIMENTO
        return context


class RelatorioGerarView(LoginRequiredMixin, View):
    NOMES_ARQUIVO = {
        'estoque_atual': 'estoque_atual',
        'estoque_baixo': 'estoque_baixo',
        'validade': 'produtos_vencidos_e_proximos_do_vencimento',
        'movimentacoes': 'movimentacoes_do_periodo',
        'entradas': 'entradas_do_periodo',
        'saidas': 'saidas_do_periodo',
        'por_categoria': 'estoque_por_categoria',
        'saldo_folgas': 'saldo_de_dias_de_folga',
        'lancamentos_folgas': 'lancamentos_de_folga_do_periodo',
    }

    def get(self, request, tipo):
        hoje = timezone.localdate()
        data_inicio = self._parse_data(request.GET.get('data_inicio')) or hoje.replace(day=1)
        data_fim = self._parse_data(request.GET.get('data_fim')) or hoje
        dias_raw = request.GET.get('dias')
        dias = int(dias_raw) if dias_raw and dias_raw.isdigit() else None

        unidade = get_unidade_do_usuario(request.user)

        geradores = {
            'estoque_atual': lambda: relatorios.relatorio_estoque_atual(unidade),
            'estoque_baixo': lambda: relatorios.relatorio_estoque_baixo(unidade),
            'validade': lambda: relatorios.relatorio_validade(unidade, dias),
            'movimentacoes': lambda: relatorios.relatorio_movimentacoes(unidade, data_inicio, data_fim),
            'entradas': lambda: relatorios.relatorio_movimentacoes(unidade, data_inicio, data_fim, tipo=Movimentacao.ENTRADA),
            'saidas': lambda: relatorios.relatorio_movimentacoes(unidade, data_inicio, data_fim, tipo=Movimentacao.SAIDA),
            'por_categoria': lambda: relatorios.relatorio_por_categoria(unidade),
            'saldo_folgas': lambda: relatorios.relatorio_saldo_folgas(unidade),
            'lancamentos_folgas': lambda: relatorios.relatorio_lancamentos_folgas(unidade, data_inicio, data_fim),
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