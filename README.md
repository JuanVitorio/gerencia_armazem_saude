# Sistema de Gerência de Estoque (Django)

Projeto completo de gerência de estoque com cadastro de categorias, fornecedores,
produtos e registro de movimentações (entradas/saídas), com atualização automática
da quantidade em estoque e dashboard com alertas de estoque baixo.

## Estrutura

```
estoque_project/
├── manage.py
├── requirements.txt
├── core/                  # configurações do projeto
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── templates/
│   └── registration/login.html
└── estoque/                # app principal
    ├── models.py            # Categoria, Fornecedor, Produto, Movimentacao
    ├── forms.py
    ├── views.py             # dashboard + CRUD (class-based views)
    ├── urls.py
    ├── admin.py
    └── templates/estoque/
```

## Como rodar

```bash
# 1. crie e ative um ambiente virtual
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. instale as dependências
pip install -r requirements.txt

# 3. gere e aplique as migrações
python manage.py makemigrations
python manage.py migrate

# 4. crie um super usuário para acessar o sistema e o admin
python manage.py createsuperuser

# 5. rode o servidor
python manage.py runserver
```

Acesse:
- `http://127.0.0.1:8000/` — sistema (login necessário)
- `http://127.0.0.1:8000/admin/` — painel administrativo do Django

## Funcionalidades

- **Categorias**: CRUD completo.
- **Fornecedores**: CRUD completo, com dados de contato.
- **Produtos**: CRUD completo, com SKU, código de barras, categoria, fornecedor,
  preço de custo/venda, estoque atual e estoque mínimo. Lista com busca e filtro
  por categoria / estoque baixo.
- **Movimentações**: registro de entrada e saída de estoque. Ao salvar, a
  quantidade do produto é atualizada automaticamente (dentro de uma transação),
  e uma saída maior que o estoque disponível é bloqueada por validação.
- **Dashboard**: total de produtos, total de itens, valor total em estoque
  (a custo), lista de produtos com estoque baixo e últimas movimentações.
- **Autenticação**: login obrigatório para todas as telas (`LoginRequiredMixin`).

## Próximos passos sugeridos

- Trocar SQLite por PostgreSQL em produção (ajustar `DATABASES` em `core/settings.py`).
- Adicionar relatórios em PDF/Excel (ex: `openpyxl`, `weasyprint`).
- Criar permissões por grupo de usuário (ex: apenas gerentes podem excluir).
- Adicionar testes automatizados (`estoque/tests.py`).
