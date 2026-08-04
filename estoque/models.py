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

    # --------------------------------------------------------------------
    # Regra dinâmica de estoque baixo (parametrizável) — ver comentário
    # completo em Produto.estoque_baixo / Produto.limite_estoque_baixo_calculado.
    # Pendente de validação de negócio antes de virar o padrão do sistema.
    # --------------------------------------------------------------------
    limite_estoque_baixo = models.PositiveIntegerField(
        'Limite de Estoque Baixo (categoria)', null=True, blank=True,
        help_text=(
            'Quantidade abaixo da qual produtos desta categoria entram no alerta '
            'de estoque baixo. Deixe em branco para usar o limite padrão do sistema. '
            'Um produto pode sobrescrever esse valor individualmente.'
        ),
    )

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
    codigo = models.CharField(
        'Código', max_length=20, unique=True, null=True, blank=True,
        help_text='Código curto de identificação da unidade (ex: PS-01, SEC-CENTRAL). Opcional.',
    )
    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES, default=POSTO_SAUDE)
    descricao = models.TextField('Descrição', blank=True)
    ativa = models.BooleanField('Ativa', default=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Unidade'
        verbose_name_plural = 'Unidades'
        ordering = ['tipo', 'nome']

    def __str__(self):
        # O código (quando preenchido) aparece automaticamente em todo
        # lugar que usa str(unidade) — selects de formulário, badges, etc.
        if self.codigo:
            return f'[{self.codigo}] {self.get_tipo_display()} — {self.nome}'
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

    # --------------------------------------------------------------------
    # Regra dinâmica de estoque baixo (parametrizável) — ver comentário
    # completo em Produto.limite_estoque_baixo_calculado, mais abaixo.
    # Pendente de validação de negócio antes de virar o padrão do sistema.
    # --------------------------------------------------------------------
    limite_estoque_baixo = models.PositiveIntegerField(
        'Limite de Estoque Baixo (produto)', null=True, blank=True,
        help_text=(
            'Sobrescreve o limite da categoria/sistema só para este produto. '
            'Tem prioridade sobre tudo. Deixe em branco para não sobrescrever.'
        ),
    )
    estoque_maximo = models.PositiveIntegerField(
        'Estoque Máximo / Ideal', null=True, blank=True,
        help_text='Capacidade ideal deste produto — usada como referência do alerta por percentual, abaixo.',
    )
    percentual_alerta_estoque = models.PositiveSmallIntegerField(
        '% Mínimo do Estoque Máximo', null=True, blank=True,
        help_text=(
            'Alerta quando a quantidade atual cair abaixo desse percentual do '
            '"Estoque Máximo / Ideal". Só funciona se os dois campos estiverem preenchidos. '
            'Ex: Estoque Máximo = 100 e 20% → alerta abaixo de 20 unidades.'
        ),
    )

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
    def limite_estoque_baixo_calculado(self):
        """
        Regra DINÂMICA e parametrizável de estoque baixo — implementada a
        pedido para substituir o limite único e global que existia antes
        (settings.LIMITE_ESTOQUE_BAIXO). Código comentado/documentado em
        detalhe abaixo para validação de negócio antes de virar padrão.

        Ordem de prioridade (do mais específico para o mais genérico):

          1) LIMITE POR PRODUTO — Produto.limite_estoque_baixo, se preenchido.
             É o override mais específico possível: serve para um item que
             realmente precisa de uma regra diferente de tudo o mais
             (ex: uma vacina que só pode ficar com 2 doses de folga).

          2) LIMITE POR PERCENTUAL — se Produto.percentual_alerta_estoque E
             Produto.estoque_maximo estiverem preenchidos, calcula
             `estoque_maximo * percentual / 100` (arredondado para baixo).
             Útil pra produtos com capacidade/estoque ideal conhecido, onde
             o alerta faz mais sentido em proporção do que em número fixo
             (ex: alertar quando cair abaixo de 20% da capacidade do posto).

          3) LIMITE POR CATEGORIA — Categoria.limite_estoque_baixo, se a
             categoria do produto tiver um valor definido. Permite alertar
             "Medicamentos" com um limite e "Material de Limpeza" com outro,
             sem precisar configurar produto por produto.

          4) LIMITE GLOBAL (fallback) — settings.LIMITE_ESTOQUE_BAIXO, o
             comportamento padrão atual do sistema, usado quando nenhuma das
             regras acima está configurada.

        # TODO (validação posterior): confirmar com o time se a ordem de
        # prioridade acima é a esperada, e se o arredondamento do cálculo
        # por percentual deve ser para baixo (atual), para cima, ou para o
        # inteiro mais próximo.
        """
        if self.limite_estoque_baixo is not None:
            return self.limite_estoque_baixo

        if self.percentual_alerta_estoque is not None and self.estoque_maximo:
            return int(self.estoque_maximo * self.percentual_alerta_estoque / 100)

        if self.categoria_id and self.categoria.limite_estoque_baixo is not None:
            return self.categoria.limite_estoque_baixo

        return settings.LIMITE_ESTOQUE_BAIXO

    @property
    def estoque_baixo(self):
        # Antes: comparava direto com settings.LIMITE_ESTOQUE_BAIXO (limite
        # único e global). Agora delega para limite_estoque_baixo_calculado,
        # que é dinâmico e parametrizável por produto, percentual ou
        # categoria (ver docstring acima) — com o limite global como
        # fallback, então o comportamento antigo continua funcionando pra
        # quem não configurar nada de novo.
        return self.quantidade <= self.limite_estoque_baixo_calculado

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

    @property
    def dias_vencido(self):
        """Há quantos dias o produto está vencido (None se não estiver vencido)."""
        if self.vencido:
            return abs(self.dias_para_vencer)
        return None


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
# Banco de Dias de Folga
# ---------------------------------------------------------------------------

class Funcionario(models.Model):
    """
    Cadastro de funcionário para o banco de dias de folga. Não tem login
    no sistema — é só um registro administrativo, gerenciado pelo
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
    def saldo_dias(self):
        """Créditos (dias concedidos) menos débitos (dias de folga usados)."""
        agregados = self.lancamentos.aggregate(
            creditos=models.Sum('dias', filter=models.Q(tipo=LancamentoFolga.CREDITO)),
            debitos=models.Sum('dias', filter=models.Q(tipo=LancamentoFolga.DEBITO)),
        )
        creditos = agregados['creditos'] or 0
        debitos = agregados['debitos'] or 0
        return creditos - debitos


class EventoFolga(models.Model):
    """
    Um evento em que funcionários trabalharam num dia que normalmente não
    trabalhariam (ex: "Dia de Vacinação") e por isso ganham dias de folga.
    Ao salvar os participantes (na view), é criado um LancamentoFolga de
    crédito para cada um, todos apontando para este evento.
    """
    nome = models.CharField('Nome do evento', max_length=150, help_text='Ex: Dia de Vacinação, Mutirão de Saúde...')
    data = models.DateField('Data do evento', default=timezone.localdate)
    descricao = models.TextField('Descrição', blank=True)
    dias = models.PositiveSmallIntegerField(
        'Dias de folga por participante', default=1,
        help_text='Quantos dias de folga cada funcionário participante recebe.'
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos_folga_criados', verbose_name='Registrado por',
    )
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Evento de Folga'
        verbose_name_plural = 'Eventos de Folga'
        ordering = ['-data', '-criado_em']

    def __str__(self):
        return f'{self.nome} ({self.data:%d/%m/%Y})'

    def get_absolute_url(self):
        return reverse('estoque:evento_folga_detail', args=[self.pk])

    @property
    def total_participantes(self):
        return self.lancamentos.count()


class LancamentoFolga(models.Model):
    """
    Cada lançamento é um crédito (dias de folga concedidos, geralmente via
    um EventoFolga) ou débito (dias de folga usados/tirados) para um
    funcionário. O saldo é sempre calculado a partir do histórico
    (Funcionario.saldo_dias), então corrigir ou excluir um lançamento
    sempre mantém o saldo consistente.
    """
    CREDITO = 'CREDITO'
    DEBITO = 'DEBITO'
    TIPO_CHOICES = [
        (CREDITO, 'Crédito (dia de folga concedido)'),
        (DEBITO, 'Débito (dia de folga usado)'),
    ]

    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, related_name='lancamentos', verbose_name='Funcionário',
    )
    tipo = models.CharField('Tipo', max_length=7, choices=TIPO_CHOICES)
    dias = models.PositiveSmallIntegerField('Dias de folga')
    data_referencia = models.DateField('Data de referência', default=timezone.localdate)
    motivo = models.CharField('Motivo / Observação', max_length=255, blank=True)
    evento = models.ForeignKey(
        EventoFolga, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lancamentos', verbose_name='Evento de origem',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lancamentos_banco_horas', verbose_name='Registrado por',
    )
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Lançamento de Folga'
        verbose_name_plural = 'Lançamentos de Folga'
        ordering = ['-data_referencia', '-criado_em']

    def __str__(self):
        sinal = '+' if self.tipo == self.CREDITO else '-'
        plural = 'dia' if self.dias == 1 else 'dias'
        return f'{sinal}{self.dias} {plural} — {self.funcionario.nome} ({self.data_referencia:%d/%m/%Y})'

    def clean(self):
        if self.dias is not None and self.dias <= 0:
            raise ValidationError('A quantidade de dias deve ser maior que zero.')