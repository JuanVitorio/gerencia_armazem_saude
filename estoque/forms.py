from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import Categoria, Fornecedor, Movimentacao, Produto


class BaseFormMixin:
    """
    Aplica classes do Bootstrap a todos os campos automaticamente e marca
    com um asterisco (*) o rótulo de todo campo obrigatório.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} {css}'.strip()
            if field.required and field.label:
                field.label = mark_safe(f'{escape(field.label)} <span class="text-danger">*</span>')


class CategoriaSelect(forms.Select):
    """
    Select de categoria que expõe o "tipo" de cada categoria via
    data-tipo em cada <option>. É isso que o JavaScript do formulário de
    produto (produto_form.html) usa para mostrar/esconder campos
    conforme a categoria escolhida, sem precisar de requisições extras.
    """

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            try:
                categoria = Categoria.objects.get(pk=value)
            except (Categoria.DoesNotExist, ValueError, TypeError):
                categoria = None
            if categoria:
                option['attrs']['data-tipo'] = categoria.tipo
        return option


class CategoriaForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nome', 'tipo', 'descricao']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'tipo': 'Controla quais campos aparecem no cadastro de produtos desta categoria.',
        }


class FornecedorForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = ['nome', 'cnpj_cpf', 'telefone', 'email', 'endereco', 'ativo']


class ProdutoForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Produto
        fields = [
            'nome', 'descricao', 'categoria', 'fornecedor',
            'sku', 'codigo_barras', 'lote',
            'unidade_medida', 'data_validade',
            'preco_custo', 'quantidade', 'ativo',
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'data_validade': forms.DateInput(attrs={'type': 'date'}),
            'categoria': CategoriaSelect(),
        }
        help_texts = {
            'sku': 'Nem todo item precisa de código (ex: alimentos a granel).',
        }


class MovimentacaoForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ['produto', 'tipo', 'quantidade', 'motivo']

    def clean_quantidade(self):
        quantidade = self.cleaned_data['quantidade']
        if quantidade <= 0:
            raise forms.ValidationError('A quantidade deve ser maior que zero.')
        return quantidade


class ProdutoFiltroForm(forms.Form):
    SITUACAO_CHOICES = [
        ('', 'Todas as situações'),
        ('BAIXO', 'Estoque baixo'),
        ('VENCIDO', 'Vencidos'),
        ('VENCENDO', 'Vencendo em breve'),
    ]

    q = forms.CharField(
        label='Buscar', required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Nome, código, código de barras, lote...'})
    )
    categoria = forms.ModelChoiceField(label='Categoria', queryset=Categoria.objects.all(), required=False)
    situacao = forms.ChoiceField(label='Situação', choices=SITUACAO_CHOICES, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'
            field.widget.attrs['class'] = css


class CustomAuthenticationForm(BaseFormMixin, AuthenticationForm):
    """Formulário de login com o mesmo estilo (Bootstrap + asterisco) dos demais."""
