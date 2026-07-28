from django import forms

from .models import Categoria, Fornecedor, Movimentacao, Produto


class BaseFormMixin:
    """Aplica classes do Bootstrap a todos os campos automaticamente."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} {css}'.strip()


class CategoriaForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nome', 'descricao']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }


class FornecedorForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = ['nome', 'cnpj_cpf', 'telefone', 'email', 'endereco', 'ativo']


class ProdutoForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Produto
        fields = [
            'nome', 'descricao', 'sku', 'codigo_barras', 'categoria', 'fornecedor',
            'preco_custo', 'preco_venda', 'quantidade_minima', 'ativo',
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'sku': 'Código único de identificação do produto.',
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
    q = forms.CharField(label='Buscar', required=False)
    categoria = forms.ModelChoiceField(label='Categoria', queryset=Categoria.objects.all(), required=False)
    apenas_estoque_baixo = forms.BooleanField(label='Apenas estoque baixo', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'
            field.widget.attrs['class'] = css
