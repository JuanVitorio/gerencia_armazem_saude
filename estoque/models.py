from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


class Categoria(models.Model):
    """
    Categorias pré-cadastradas via migration de dados.
    O administrador pode gerenciá-las pelo Django Admin.
    O campo 'tipo' orienta quais campos condicionais aparecem no formulário de produto.
    """
    ALIMENTO = 'ALIMENTO'
    MEDICAMENTO = 'MEDICAMENTO'
    VACINA = 'VACINA'
    MATERIAL_ODONTOLOGICO = 'MATERIAL_ODONTOLOGICO'
    MATERIAL_LIMPEZA = 'MATERIAL_LIMPEZA'
    INSUMO = 'INSUMO'
    OUTRO = 'OUTRO'

    TIPO_CHOICES = [
        (ALIMENTO, 'Alimento'),
        (MEDICAMENTO, 'Medicamento'),
        (VACINA, 'Vacina'),
        (MATERIAL_ODONTOLOGICO, 'Material Odontológico'),
        (MATERIAL_LIMPEZA, 'Material de Limpeza'),
        (INSUMO, 'Insumo'),
        (OUTRO, 'Outro'),
    ]

    # Tipos que requerem campos de rastreabilidade (lote, validade)
    TIPOS_COM_RASTREABILIDADE = {MEDICAMENTO, VACINA}
    # Tipos que usam código/SKU
    TIPOS_COM_SKU = {MEDICAMENTO, MATERIAL_ODONTOLOGICO}

    nome = models.CharField('Nome', max_length=100, unique=True)
    tipo = models.CharField(
        'Tipo', max_length=30, choices=TIPO_CHOICES, default=OUTRO,
        help_text='Controla quais campos aparecem no cadastro de produtos desta categoria.',
    )
    descricao = models.TextField('Descrição', blank=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def requer_rastreabilidade(self):
        return self.tipo in self.TIPOS_COM_RASTREABILIDADE

    @property
    def usa_sku(self):
        return self.tipo in self.TIPOS_COM_SKU


class Unidade(models.Model):
    """
    Representa um posto de saúde ou secretaria.
    Cada unidade possui seu próprio estoque independente.
    """
    POSTO_SAUDE = 'POSTO_SAUDE'
    SECRETARIA = 'SECRETARIA'
    OUTRO = 'OUTRO'

    TIPO_CHOICES = [
        (POSTO_SAUDE, 'Posto de Saúde'),
        (SECRETARIA, 'Secretaria'),
        (OUTRO, 'Outro'),
    ]

    nome = models.CharField('Nome', max_length=150)
    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES, default=POSTO_SAUDE)
    descricao = models.TextField('Descrição', blank=True)
    ativa = models.BooleanField('Ativa', default=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Unidade'
        verbose_name_plural = 'Unidades'
        ordering = ['tipo', 'nome']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.nome}'

    def get_absolute_url(self):
        return reverse('estoque:unidade_detail', args=[self.pk])


class PerfilUsuario(models.Model):
    """
    Perfil estendido do usuário Django.
    - Se 'unidade' for None, o usuário é tratado como Administrador (acesso total).
    - Usuários comuns só enxergam os produtos da sua unidade.
    """
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name='Usuário',
    )
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='membros',
        verbose_name='Unidade',
        help_text='Deixe em branco para conceder acesso de Administrador (vê todas as unidades).',
    )

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'

    def __str__(self):
        return f'Perfil de {self.usuario.username}'

    @property
    def is_admin(self):
        """Administradores: superusuários ou perfis sem unidade vinculada."""
        return self.usuario.is_superuser or self.usuario.is_staff or self.unidade is None


class Produto(models.Model):
    UNIDADE_CHOICES = [
        ('UN', 'Unidade'),
        ('CX', 'Caixa'),
        ('PC', 'Pacote'),
        ('KG', 'Quilograma'),
        ('G', 'Grama'),
        ('L', 'Litro'),
        ('ML', 'Mililitro'),
        ('DS', 'Dose'),
        ('FR', 'Frasco'),
        ('AMP', 'Ampola'),
        ('PAR', 'Par'),
        ('RO', 'Rolo'),
        ('SC', 'Saco'),
    ]

    # Relacionamentos
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.CASCADE,
        related_name='produtos',
        verbose_name='Unidade',
        null=True,
        blank=True,
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='produtos',
        verbose_name='Categoria',
    )

    # Campos principais
    nome = models.CharField('Nome', max_length=150)
    detalhes = models.CharField(
        'Detalhes',
        max_length=255,
        blank=True,
        help_text='Cor, tamanho, modelo, concentração, etc. Ex: "500mg/5ml" ou "Tamanho M, azul".',
    )
    descricao = models.TextField('Descrição / Observações', blank=True)

    # Identificação (campos condicionais por categoria)
    sku = models.CharField(
        'Código', max_length=50, blank=True,
        help_text='Código interno ou de referência (opcional).',
    )
    lote = models.CharField(
        'Lote', max_length=50, blank=True,
        help_text='Número do lote (vacinas e medicamentos).',
    )
    data_validade = models.DateField(
        'Data de Validade', null=True, blank=True,
        help_text='Deixe em branco para itens sem prazo de validade.',
    )

    # Estoque
    unidade_medida = models.CharField(
        'Unidade de Medida', max_length=3, choices=UNIDADE_CHOICES, default='UN',
    )
    quantidade = models.PositiveIntegerField('Quantidade em Estoque', default=0)

    # Controle
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse('estoque:produto_detail', args=[self.pk])

    @property
    def estoque_baixo(self):
        return self.quantidade <= settings.LIMITE_ESTOQUE_BAIXO

    @property
    def dias_para_vencer(self):
        """Retorna quantos dias faltam para o vencimento (negativo = já venceu)."""
        if not self.data_validade:
            return None
        return (self.data_validade - timezone.localdate()).days

    @property
    def vencido(self):
        dias = self.dias_para_vencer
        return dias is not None and dias < 0

    @property
    def venc_proximo(self):
        dias = self.dias_para_vencer
        return dias is not None and 0 <= dias <= settings.DIAS_ALERTA_VENCIMENTO


class Movimentacao(models.Model):
    ENTRADA = 'ENTRADA'
    SAIDA = 'SAIDA'
    TIPO_CHOICES = [
        (ENTRADA, 'Entrada'),
        (SAIDA, 'Saída'),
    ]

    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name='movimentacoes',
        verbose_name='Produto',
    )
    tipo = models.CharField('Tipo', max_length=7, choices=TIPO_CHOICES)
    quantidade = models.PositiveIntegerField('Quantidade')
    motivo = models.CharField('Motivo / Observação', max_length=255, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Usuário',
    )
    data = models.DateTimeField('Data', auto_now_add=True)

    class Meta:
        verbose_name = 'Movimentação de Estoque'
        verbose_name_plural = 'Movimentações de Estoque'
        ordering = ['-data']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.quantidade} × {self.produto.nome}'

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


# ---------------------------------------------------------------------------
# Banco de Horas
# ---------------------------------------------------------------------------

class Funcionario(models.Model):
    """
    Cadastro de funcionário para o banco de horas. Não tem login no
    sistema — é só um registro administrativo, gerenciado pelo
    gestor/RH (mesma permissão de Unidade/Usuário, ver AdminRequiredMixin).
    """
    nome = models.CharField('Nome', max_length=150)
    cargo = models.CharField('Cargo / Função', max_length=100, blank=True)
    matricula = models.CharField('Matrícula', max_length=30, blank=True)
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='funcionarios', verbose_name='Unidade',
    )
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Funcionário'
        verbose_name_plural = 'Funcionários'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse('estoque:funcionario_detail', args=[self.pk])

    @property
    def saldo_horas(self):
        """Créditos (horas extras) menos débitos (horas compensadas/folgas)."""
        agregados = self.lancamentos.aggregate(
            creditos=models.Sum('horas', filter=models.Q(tipo=LancamentoBancoHoras.CREDITO)),
            debitos=models.Sum('horas', filter=models.Q(tipo=LancamentoBancoHoras.DEBITO)),
        )
        creditos = agregados['creditos'] or 0
        debitos = agregados['debitos'] or 0
        return creditos - debitos


class LancamentoBancoHoras(models.Model):
    """
    Cada lançamento é um crédito (horas extras trabalhadas) ou débito
    (horas compensadas/folga) para um funcionário. O saldo é sempre
    calculado a partir do histórico (Funcionario.saldo_horas), então
    corrigir ou excluir um lançamento sempre mantém o saldo consistente.
    """
    CREDITO = 'CREDITO'
    DEBITO = 'DEBITO'
    TIPO_CHOICES = [
        (CREDITO, 'Crédito (horas trabalhadas/extras)'),
        (DEBITO, 'Débito (horas compensadas/folga)'),
    ]

    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name='lancamentos', verbose_name='Funcionário',
    )
    tipo = models.CharField('Tipo', max_length=7, choices=TIPO_CHOICES)
    horas = models.DecimalField('Horas', max_digits=5, decimal_places=2)
    data_referencia = models.DateField('Data de referência', default=timezone.localdate)
    motivo = models.CharField('Motivo / Observação', max_length=255, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lancamentos_banco_horas', verbose_name='Registrado por',
    )
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Lançamento de Banco de Horas'
        verbose_name_plural = 'Lançamentos de Banco de Horas'
        ordering = ['-data_referencia', '-criado_em']

    def __str__(self):
        sinal = '+' if self.tipo == self.CREDITO else '-'
        return f'{sinal}{self.horas}h — {self.funcionario.nome} ({self.data_referencia:%d/%m/%Y})'

    def clean(self):
        if self.horas is not None and self.horas <= 0:
            raise ValidationError('A quantidade de horas deve ser maior que zero.')