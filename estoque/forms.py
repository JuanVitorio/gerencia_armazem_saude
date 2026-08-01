from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import Categoria, EventoFolga, Funcionario, LancamentoFolga, Movimentacao, PerfilUsuario, Produto, Unidade


class BaseFormMixin:
    """Aplica classes CSS a todos os campos e marca campos obrigatórios com asterisco."""

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
    Select que expõe o 'tipo' de cada categoria via data-tipo em cada <option>.
    O JS do produto_form.html usa esse atributo para mostrar/esconder campos.
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


class ProdutoForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Produto
        fields = [
            'nome', 'categoria', 'detalhes', 'descricao',
            'sku', 'lote', 'data_validade',
            'unidade_medida', 'quantidade',
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Observações adicionais (opcional)'}),
            'data_validade': forms.DateInput(attrs={'type': 'date'}),
            'categoria': CategoriaSelect(),
            'nome': forms.TextInput(attrs={'autofocus': True, 'placeholder': 'Ex: Amoxicilina 500mg'}),
            'detalhes': forms.TextInput(attrs={'placeholder': 'Ex: 500mg/5ml, cor azul, tamanho M...'}),
            'sku': forms.TextInput(attrs={'placeholder': 'Código interno (opcional)'}),
            'lote': forms.TextInput(attrs={'placeholder': 'Número do lote'}),
        }
        help_texts = {
            'detalhes': 'Cor, tamanho, modelo, concentração, etc.',
            'sku': 'Código interno ou de referência.',
        }


class MovimentacaoForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ['produto', 'tipo', 'quantidade', 'motivo']
        widgets = {
            'motivo': forms.TextInput(attrs={'placeholder': 'Ex: Recebimento de NF, uso em atendimento...'}),
        }

    def __init__(self, *args, unidade=None, **kwargs):
        super().__init__(*args, **kwargs)
        if unidade is not None:
            self.fields['produto'].queryset = Produto.objects.filter(
                unidade=unidade, ativo=True
            ).order_by('nome')
        else:
            self.fields['produto'].queryset = Produto.objects.filter(ativo=True).order_by('nome')

    def clean_quantidade(self):
        quantidade = self.cleaned_data.get('quantidade')
        if not quantidade or quantidade <= 0:
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
        widget=forms.TextInput(attrs={
            'placeholder': 'Nome, código, lote...',
            'class': 'form-control',
            'id': 'id_busca_produto',
        }),
    )
    categoria = forms.ModelChoiceField(
        label='Categoria', queryset=Categoria.objects.all(), required=False,
        empty_label='Todas as categorias',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    situacao = forms.ChoiceField(
        label='Situação', choices=SITUACAO_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )


class MovimentacaoFiltroForm(forms.Form):
    q = forms.CharField(
        label='Produto', required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Buscar produto...',
            'class': 'form-control',
        }),
    )
    tipo = forms.ChoiceField(
        label='Tipo',
        choices=[('', 'Entrada e Saída'), ('ENTRADA', 'Entrada'), ('SAIDA', 'Saída')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    data_inicio = forms.DateField(
        label='De', required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    data_fim = forms.DateField(
        label='Até', required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )


class PerfilUsuarioForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ['unidade']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unidade'].required = False
        self.fields['unidade'].empty_label = '— Administrador (acesso total) —'


class UsuarioForm(BaseFormMixin, forms.ModelForm):
    """Formulário para criação/edição de usuários pelo Administrador."""
    password1 = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False,
        help_text='Deixe em branco para manter a senha atual (ao editar).',
    )
    password2 = forms.CharField(
        label='Confirmar senha',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False,
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 or p2:
            if p1 != p2:
                raise forms.ValidationError('As senhas não coincidem.')
        return cleaned


class CustomAuthenticationForm(BaseFormMixin, AuthenticationForm):
    """Formulário de login com o mesmo estilo dos demais formulários."""


class FuncionarioForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Funcionario
        fields = ['nome', 'cargo', 'matricula', 'unidade', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={'autofocus': True, 'placeholder': 'Nome completo'}),
            'cargo': forms.TextInput(attrs={'placeholder': 'Ex: Auxiliar de enfermagem'}),
            'matricula': forms.TextInput(attrs={'placeholder': 'Número de matrícula (opcional)'}),
        }


class LancamentoFolgaForm(BaseFormMixin, forms.ModelForm):
    """Lançamento manual (crédito avulso ou débito de dia usado)."""

    class Meta:
        model = LancamentoFolga
        fields = ['funcionario', 'tipo', 'dias', 'data_referencia', 'motivo']
        widgets = {
            'data_referencia': forms.DateInput(attrs={'type': 'date'}),
            'dias': forms.NumberInput(attrs={'step': '1', 'min': '1', 'placeholder': 'Ex: 1'}),
            'motivo': forms.TextInput(attrs={'placeholder': 'Ex: Folga usada, ajuste manual...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['funcionario'].queryset = Funcionario.objects.filter(ativo=True).order_by('nome')

    def clean_dias(self):
        dias = self.cleaned_data.get('dias')
        if not dias or dias <= 0:
            raise forms.ValidationError('A quantidade de dias deve ser maior que zero.')
        return dias


class EventoFolgaForm(BaseFormMixin, forms.ModelForm):
    """
    Cadastro do evento (ex: "Dia de Vacinação"). Os funcionários
    participantes são selecionados à parte, num checklist pesquisável no
    template (evento_folga_form.html) — não são um campo deste form,
    porque a view cria um LancamentoFolga de crédito por participante.
    """

    class Meta:
        model = EventoFolga
        fields = ['nome', 'data', 'descricao', 'dias']
        widgets = {
            'nome': forms.TextInput(attrs={'autofocus': True, 'placeholder': 'Ex: Dia de Vacinação'}),
            'data': forms.DateInput(attrs={'type': 'date'}),
            'descricao': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Detalhes do evento (opcional)'}),
            'dias': forms.NumberInput(attrs={'step': '1', 'min': '1'}),
        }
        help_texts = {
            'dias': 'Dias de folga que cada funcionário selecionado abaixo vai receber.',
        }


class FuncionarioFiltroForm(forms.Form):
    q = forms.CharField(
        label='Buscar', required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Nome, cargo, matrícula...',
            'class': 'form-control',
        }),
    )
    unidade = forms.ModelChoiceField(
        label='Unidade', queryset=Unidade.objects.all(), required=False,
        empty_label='Todas as unidades',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
