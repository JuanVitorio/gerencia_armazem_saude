from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse


class Categoria(models.Model):
    nome = models.CharField('Nome', max_length=100, unique=True)
    descricao = models.TextField('Descrição', blank=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse('estoque:categoria_detail', args=[self.pk])


class Fornecedor(models.Model):
    nome = models.CharField('Nome / Razão social', max_length=150)
    cnpj_cpf = models.CharField('CNPJ/CPF', max_length=20, blank=True)
    telefone = models.CharField('Telefone', max_length=20, blank=True)
    email = models.EmailField('E-mail', blank=True)
    endereco = models.CharField('Endereço', max_length=255, blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Fornecedor'
        verbose_name_plural = 'Fornecedores'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse('estoque:fornecedor_detail', args=[self.pk])


class Produto(models.Model):
    nome = models.CharField('Nome', max_length=150)
    descricao = models.TextField('Descrição', blank=True)
    sku = models.CharField('SKU / Código', max_length=50, unique=True)
    codigo_barras = models.CharField('Código de barras', max_length=50, blank=True)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='produtos', verbose_name='Categoria'
    )
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='produtos', verbose_name='Fornecedor'
    )
    preco_custo = models.DecimalField('Preço de custo', max_digits=10, decimal_places=2, default=0)
    preco_venda = models.DecimalField('Preço de venda', max_digits=10, decimal_places=2, default=0)
    quantidade = models.PositiveIntegerField('Quantidade em estoque', default=0)
    quantidade_minima = models.PositiveIntegerField('Estoque mínimo', default=5)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.sku})'

    def get_absolute_url(self):
        return reverse('estoque:produto_detail', args=[self.pk])

    @property
    def estoque_baixo(self):
        return self.quantidade <= self.quantidade_minima

    @property
    def valor_total_estoque(self):
        return self.quantidade * self.preco_custo


class Movimentacao(models.Model):
    ENTRADA = 'ENTRADA'
    SAIDA = 'SAIDA'
    TIPO_CHOICES = [
        (ENTRADA, 'Entrada'),
        (SAIDA, 'Saída'),
    ]

    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name='movimentacoes', verbose_name='Produto'
    )
    tipo = models.CharField('Tipo', max_length=7, choices=TIPO_CHOICES)
    quantidade = models.PositiveIntegerField('Quantidade')
    motivo = models.CharField('Motivo', max_length=255, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Usuário responsável'
    )
    data = models.DateTimeField('Data', auto_now_add=True)

    class Meta:
        verbose_name = 'Movimentação de estoque'
        verbose_name_plural = 'Movimentações de estoque'
        ordering = ['-data']

    def __str__(self):
        return f'{self.get_tipo_display()} de {self.quantidade} - {self.produto.nome}'

    def clean(self):
        if self.tipo == self.SAIDA and self.produto_id:
            if self.quantidade > self.produto.quantidade:
                raise ValidationError(
                    f'Estoque insuficiente. Disponível: {self.produto.quantidade}.'
                )

    def save(self, *args, **kwargs):
        """Atualiza a quantidade do produto ao registrar a movimentação."""
        is_new = self._state.adding
        with transaction.atomic():
            if is_new:
                self.full_clean()
                if self.tipo == self.ENTRADA:
                    self.produto.quantidade += self.quantidade
                else:
                    self.produto.quantidade -= self.quantidade
                self.produto.save(update_fields=['quantidade', 'atualizado_em'])
            super().save(*args, **kwargs)
