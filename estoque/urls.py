from django.urls import path

from . import views

app_name = 'estoque'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),

    # Unidades (admin only)
    path('unidades/', views.UnidadeListView.as_view(), name='unidade_list'),
    path('unidades/nova/', views.UnidadeCreateView.as_view(), name='unidade_create'),
    path('unidades/<int:pk>/', views.UnidadeDetailView.as_view(), name='unidade_detail'),
    path('unidades/<int:pk>/editar/', views.UnidadeUpdateView.as_view(), name='unidade_update'),

    # Produtos
    path('produtos/', views.ProdutoListView.as_view(), name='produto_list'),
    path('produtos/novo/', views.ProdutoCreateView.as_view(), name='produto_create'),
    path('produtos/<int:pk>/', views.ProdutoDetailView.as_view(), name='produto_detail'),
    path('produtos/<int:pk>/editar/', views.ProdutoUpdateView.as_view(), name='produto_update'),
    path('produtos/<int:pk>/excluir/', views.ProdutoDeleteView.as_view(), name='produto_delete'),
    path('produtos/<int:pk>/movimentacao-rapida/', views.MovimentacaoRapidaView.as_view(), name='movimentacao_rapida'),

    # Movimentações
    path('movimentacoes/', views.MovimentacaoListView.as_view(), name='movimentacao_list'),
    path('movimentacoes/nova/', views.MovimentacaoCreateView.as_view(), name='movimentacao_create'),
    path('movimentacoes/<int:pk>/', views.MovimentacaoDetailView.as_view(), name='movimentacao_detail'),
    path('movimentacoes/<int:pk>/excluir/', views.MovimentacaoDeleteView.as_view(), name='movimentacao_delete'),

    # Usuários (admin only)
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_list'),
    path('usuarios/novo/', views.UsuarioCreateView.as_view(), name='usuario_create'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_update'),
    path('usuarios/<int:pk>/excluir/', views.UsuarioDeleteView.as_view(), name='usuario_delete'),

    # Banco de Horas (admin/RH only)
    path('banco-de-horas/', views.FuncionarioListView.as_view(), name='funcionario_list'),
    path('banco-de-horas/novo/', views.FuncionarioCreateView.as_view(), name='funcionario_create'),
    path('banco-de-horas/lancamento/novo/', views.LancamentoFolgaCreateView.as_view(), name='lancamento_create'),
    path('banco-de-horas/lancamento/<int:pk>/excluir/', views.LancamentoFolgaDeleteView.as_view(), name='lancamento_delete'),
    path('banco-de-horas/eventos/', views.EventoFolgaListView.as_view(), name='evento_folga_list'),
    path('banco-de-horas/eventos/novo/', views.EventoFolgaCreateView.as_view(), name='evento_folga_create'),
    path('banco-de-horas/eventos/<int:pk>/', views.EventoFolgaDetailView.as_view(), name='evento_folga_detail'),
    path('banco-de-horas/eventos/<int:pk>/editar/', views.EventoFolgaUpdateView.as_view(), name='evento_folga_update'),
    path('banco-de-horas/<int:pk>/', views.FuncionarioDetailView.as_view(), name='funcionario_detail'),
    path('banco-de-horas/<int:pk>/editar/', views.FuncionarioUpdateView.as_view(), name='funcionario_update'),
    path('banco-de-horas/<int:pk>/excluir/', views.FuncionarioDeleteView.as_view(), name='funcionario_delete'),

    # Relatórios
    path('relatorios/', views.RelatorioListView.as_view(), name='relatorio_list'),
    path('relatorios/gerar/<str:tipo>/', views.RelatorioGerarView.as_view(), name='relatorio_gerar'),
]