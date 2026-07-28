from django.urls import path

from . import views

app_name = 'estoque'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),

    # Categorias
    path('categorias/', views.CategoriaListView.as_view(), name='categoria_list'),
    path('categorias/nova/', views.CategoriaCreateView.as_view(), name='categoria_create'),
    path('categorias/<int:pk>/', views.CategoriaDetailView.as_view(), name='categoria_detail'),
    path('categorias/<int:pk>/editar/', views.CategoriaUpdateView.as_view(), name='categoria_update'),
    path('categorias/<int:pk>/excluir/', views.CategoriaDeleteView.as_view(), name='categoria_delete'),

    # Fornecedores
    path('fornecedores/', views.FornecedorListView.as_view(), name='fornecedor_list'),
    path('fornecedores/novo/', views.FornecedorCreateView.as_view(), name='fornecedor_create'),
    path('fornecedores/<int:pk>/', views.FornecedorDetailView.as_view(), name='fornecedor_detail'),
    path('fornecedores/<int:pk>/editar/', views.FornecedorUpdateView.as_view(), name='fornecedor_update'),
    path('fornecedores/<int:pk>/excluir/', views.FornecedorDeleteView.as_view(), name='fornecedor_delete'),

    # Produtos
    path('produtos/', views.ProdutoListView.as_view(), name='produto_list'),
    path('produtos/novo/', views.ProdutoCreateView.as_view(), name='produto_create'),
    path('produtos/<int:pk>/', views.ProdutoDetailView.as_view(), name='produto_detail'),
    path('produtos/<int:pk>/editar/', views.ProdutoUpdateView.as_view(), name='produto_update'),
    path('produtos/<int:pk>/excluir/', views.ProdutoDeleteView.as_view(), name='produto_delete'),

    # Movimentações
    path('movimentacoes/', views.MovimentacaoListView.as_view(), name='movimentacao_list'),
    path('movimentacoes/nova/', views.MovimentacaoCreateView.as_view(), name='movimentacao_create'),
]
