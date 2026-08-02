import io
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

from .models import Funcionario, LancamentoFolga, Movimentacao, Produto


class NumberedCanvas:
    """Canvas customizado para incluir cabeçalho/rodapé e numeração de páginas (Página X de Y)."""

    def __init__(self, *args, **kwargs):
        self._saved_page_states = []

    def __call__(self, *args, **kwargs):
        from reportlab.pdfgen import canvas

        class PageNumCanvas(canvas.Canvas):

            def __init__(cb_self, *c_args, **c_kwargs):
                super().__init__(*c_args, **c_kwargs)
                cb_self.pages = []

            def showPage(cb_self):
                cb_self.pages.append(dict(cb_self.__dict__))
                cb_self._startPage()

            def save(cb_self):
                num_pages = len(cb_self.pages)
                for page in cb_self.pages:
                    cb_self.__dict__.update(page)
                    cb_self.draw_page_number(num_pages)
                    canvas.Canvas.showPage(cb_self)
                canvas.Canvas.save(cb_self)

            def draw_page_number(cb_self, page_count):
                cb_self.saveState()
                cb_self.setFont("Helvetica", 8)
                cb_self.setFillColor(colors.HexColor("#64748B"))

                # Linha de rodapé
                cb_self.setStrokeColor(colors.HexColor("#CBD5E1"))
                cb_self.setLineWidth(0.5)
                cb_self.line(1.5 * cm, 1.2 * cm, A4[0] - 1.5 * cm, 1.2 * cm)

                # Texto rodapé
                cb_self.drawString(
                    1.5 * cm, 0.8 * cm,
                    "Sistema de Gerência de Estoque — Armazém & Saúde"
                )
                page_text = f"Página {cb_self._pageNumber} de {page_count}"
                cb_self.drawRightString(A4[0] - 1.5 * cm, 0.8 * cm, page_text)
                cb_self.restoreState()

        return PageNumCanvas(*args, **kwargs)


def _criar_pdf_base(titulo, sub_titulo, tabela_dados, col_widths, resumo_texto=""):
    """Gera um PDF estruturado em memória usando ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
    )

    styles = getSampleStyleSheet()

    # Estilos customizados
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=8,
    )
    cell_head_style = ParagraphStyle(
        'CellHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1E293B'),
    )
    cell_body_style = ParagraphStyle(
        'CellBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#0F172A'),
    )
    cell_body_bold = ParagraphStyle(
        'CellBodyBold',
        parent=cell_body_style,
        fontName='Helvetica-Bold',
    )
    resumo_style = ParagraphStyle(
        'ResumoText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#0284C7'),
        spaceAfter=10,
    )

    elements = []

    # Cabeçalho
    elements.append(Paragraph(titulo, title_style))
    agora_str = timezone.localtime().strftime('%d/%m/%Y às %H:%M')
    full_sub = f"{sub_titulo} • Gerado em: {agora_str}"
    elements.append(Paragraph(full_sub, subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0284C7'), spaceAfter=10))

    if resumo_texto:
        elements.append(Paragraph(resumo_texto, resumo_style))

    # Converte texto da tabela em Paragraphs
    table_formatted = []
    for i, row in enumerate(tabela_dados):
        formatted_row = []
        for cell in row:
            st = cell_head_style if i == 0 else cell_body_style
            if isinstance(cell, str) and cell.startswith('**'):
                st = cell_body_bold
                cell = cell.replace('**', '')
            formatted_row.append(Paragraph(str(cell), st))
        table_formatted.append(formatted_row)

    # Estilo da tabela
    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ])

    t = Table(table_formatted, colWidths=col_widths, style=t_style)
    elements.append(t)

    doc.build(elements, canvasmaker=NumberedCanvas())
    buffer.seek(0)
    return buffer


def relatorio_estoque_atual(unidade=None):
    qs = Produto.objects.filter(ativo=True).select_related('categoria', 'unidade').order_by('categoria__nome', 'nome')
    if unidade:
        qs = qs.filter(unidade=unidade)

    sub = f"Unidade: {unidade.nome}" if unidade else "Todas as Unidades"

    header = ['Produto / Detalhes', 'Categoria', 'Qtd. Estoque', 'Validade', 'Lote / SKU']
    widths = [6.5 * cm, 3.5 * cm, 2.5 * cm, 2.5 * cm, 3.0 * cm]

    rows = [header]
    total_itens = 0
    for p in qs:
        detalhes_str = f"{p.nome}"
        if p.detalhes:
            detalhes_str += f"<br/><font color='#64748B'>{p.detalhes}</font>"
        
        cat_str = p.categoria.nome if p.categoria else "—"
        qtd_str = f"{p.quantidade} {p.get_unidade_medida_display()}"
        val_str = p.data_validade.strftime('%d/%m/%Y') if p.data_validade else "—"
        code_str = f"Lote: {p.lote}" if p.lote else (f"SKU: {p.sku}" if p.sku else "—")

        rows.append([detalhes_str, cat_str, qtd_str, val_str, code_str])
        total_itens += 1

    resumo = f"Total de produtos listados: <b>{total_itens}</b>"
    return _criar_pdf_base("Relatório de Estoque Atual", sub, rows, widths, resumo)


def relatorio_estoque_baixo(unidade=None):
    # Mesma regra dinâmica/parametrizável do dashboard (ver
    # Produto.limite_estoque_baixo_calculado em models.py) — cada produto
    # pode ter um limite diferente (por produto, percentual ou categoria),
    # então filtramos em Python em vez de um único `.filter()` no banco.
    qs = Produto.objects.filter(ativo=True).select_related('categoria', 'unidade').order_by('nome')
    if unidade:
        qs = qs.filter(unidade=unidade)
    produtos_baixo = sorted((p for p in qs if p.estoque_baixo), key=lambda p: p.quantidade)

    sub = f"Unidade: {unidade.nome}" if unidade else "Todas as Unidades"

    header = ['Produto', 'Categoria', 'Qtd. Atual', 'Limite Alerta', 'Status']
    widths = [7.0 * cm, 4.0 * cm, 2.5 * cm, 2.5 * cm, 2.0 * cm]

    rows = [header]
    for p in produtos_baixo:
        cat_str = p.categoria.nome if p.categoria else "—"
        qtd_str = f"<b>{p.quantidade}</b> {p.get_unidade_medida_display()}"
        rows.append([p.nome, cat_str, qtd_str, f"{p.limite_estoque_baixo_calculado} un.", "<font color='#DC2626'>CRÍTICO</font>"])

    resumo = f"Total de produtos em estoque baixo: <b>{len(produtos_baixo)}</b>"
    return _criar_pdf_base("Relatório de Produtos com Estoque Baixo", sub, rows, widths, resumo)


def relatorio_validade(unidade=None, dias=None):
    hoje = timezone.localdate()
    dias_antec = dias if dias is not None else settings.DIAS_ALERTA_VENCIMENTO
    limite = hoje + timedelta(days=dias_antec)

    qs = Produto.objects.filter(
        ativo=True, data_validade__isnull=False, data_validade__lte=limite
    ).select_related('categoria', 'unidade').order_by('data_validade')

    if unidade:
        qs = qs.filter(unidade=unidade)

    sub = f"Unidade: {unidade.nome} (Alerta de {dias_antec} dias)" if unidade else f"Todas as Unidades (Alerta de {dias_antec} dias)"

    header = ['Produto', 'Categoria', 'Lote', 'Data Validade', 'Situação']
    widths = [6.5 * cm, 3.5 * cm, 2.5 * cm, 2.5 * cm, 3.0 * cm]

    rows = [header]
    for p in qs:
        cat_str = p.categoria.nome if p.categoria else "—"
        lote_str = p.lote if p.lote else "—"
        val_str = p.data_validade.strftime('%d/%m/%Y')
        
        if p.vencido:
            sit = "<font color='#DC2626'><b>VENCIDO</b></font>"
        else:
            dias_f = p.dias_para_vencer
            sit = f"<font color='#D97706'>Vence em {dias_f} dia(s)</font>"

        rows.append([p.nome, cat_str, lote_str, val_str, sit])

    resumo = f"Total de produtos vencidos ou próximos do vencimento: <b>{len(rows)-1}</b>"
    return _criar_pdf_base("Relatório de Validade de Produtos", sub, rows, widths, resumo)


def relatorio_movimentacoes(unidade=None, data_inicio=None, data_fim=None, tipo=None):
    qs = Movimentacao.objects.select_related('produto', 'produto__categoria', 'usuario').order_by('-data')

    if unidade:
        qs = qs.filter(produto__unidade=unidade)
    if data_inicio:
        qs = qs.filter(data__date__gte=data_inicio)
    if data_fim:
        qs = qs.filter(data__date__lte=data_fim)
    if tipo:
        qs = qs.filter(tipo=tipo)

    titulo_tipo = "Movimentações"
    if tipo == Movimentacao.ENTRADA:
        titulo_tipo = "Entradas de Estoque"
    elif tipo == Movimentacao.SAIDA:
        titulo_tipo = "Saídas de Estoque"

    p_str = ""
    if data_inicio and data_fim:
        p_str = f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"
    
    sub = f"Unidade: {unidade.nome} • {p_str}" if unidade else f"Todas as Unidades • {p_str}"

    header = ['Data / Hora', 'Produto', 'Tipo', 'Qtd.', 'Motivo / Usuário']
    widths = [3.0 * cm, 6.0 * cm, 2.0 * cm, 2.0 * cm, 5.0 * cm]

    rows = [header]
    total_movs = 0
    total_qtd = 0

    for m in qs:
        dt_str = timezone.localtime(m.data).strftime('%d/%m/%Y %H:%M')
        prod_str = m.produto.nome
        tipo_str = "<font color='#16A34A'><b>ENTRADA</b></font>" if m.tipo == Movimentacao.ENTRADA else "<font color='#DC2626'><b>SAÍDA</b></font>"
        qtd_str = str(m.quantidade)
        usr_str = f"{m.motivo or '—'}<br/><font color='#64748B'>Por: {m.usuario or '—'}</font>"

        rows.append([dt_str, prod_str, tipo_str, qtd_str, usr_str])
        total_movs += 1
        total_qtd += m.quantidade

    resumo = f"Total de lançamentos: <b>{total_movs}</b> | Quantidade movimentada acumulada: <b>{total_qtd}</b>"
    return _criar_pdf_base(f"Relatório de {titulo_tipo}", sub, rows, widths, resumo)


def relatorio_por_categoria(unidade=None):
    qs = Produto.objects.filter(ativo=True).select_related('categoria', 'unidade')
    if unidade:
        qs = qs.filter(unidade=unidade)

    from collections import defaultdict
    cat_map = defaultdict(lambda: {'count': 0, 'total_qtd': 0})

    for p in qs:
        cat_nome = p.categoria.nome if p.categoria else "Sem Categoria"
        cat_map[cat_nome]['count'] += 1
        cat_map[cat_nome]['total_qtd'] += p.quantidade

    sub = f"Unidade: {unidade.nome}" if unidade else "Todas as Unidades"

    header = ['Categoria', 'Qtd. de Itens Diferentes', 'Quantidade Total em Estoque']
    widths = [8.0 * cm, 5.0 * cm, 5.0 * cm]

    rows = [header]
    for cat_nome, data in sorted(cat_map.items()):
        rows.append([cat_nome, str(data['count']), f"{data['total_qtd']} un."])

    resumo = f"Total de categorias ativas: <b>{len(cat_map)}</b>"
    return _criar_pdf_base("Relatório de Estoque por Categoria", sub, rows, widths, resumo)


def relatorio_saldo_folgas(unidade=None):
    qs = Funcionario.objects.filter(ativo=True).select_related('unidade').order_by('nome')
    if unidade:
        qs = qs.filter(unidade=unidade)

    sub = f"Unidade: {unidade.nome}" if unidade else "Todas as Unidades"

    header = ['Funcionário', 'Cargo', 'Unidade', 'Saldo Atual']
    widths = [6.5 * cm, 4.5 * cm, 4.0 * cm, 3.0 * cm]

    rows = [header]
    positivos = negativos = 0
    for f in qs:
        saldo = f.saldo_dias
        if saldo > 0:
            saldo_str = f"<font color='#16A34A'><b>+{saldo} dia(s)</b></font>"
            positivos += 1
        elif saldo < 0:
            saldo_str = f"<font color='#DC2626'><b>{saldo} dia(s)</b></font>"
            negativos += 1
        else:
            saldo_str = "0 dia"
        rows.append([f.nome, f.cargo or '—', f.unidade.nome if f.unidade else '—', saldo_str])

    resumo = (
        f"Funcionários listados: <b>{len(rows) - 1}</b> | "
        f"Com saldo positivo: <b>{positivos}</b> | Com saldo negativo: <b>{negativos}</b>"
    )
    return _criar_pdf_base("Relatório de Saldo de Dias de Folga", sub, rows, widths, resumo)


def relatorio_lancamentos_folgas(unidade=None, data_inicio=None, data_fim=None, tipo=None):
    qs = LancamentoFolga.objects.select_related('funcionario', 'funcionario__unidade', 'evento', 'usuario')
    qs = qs.order_by('-data_referencia', '-criado_em')

    if unidade:
        qs = qs.filter(funcionario__unidade=unidade)
    if data_inicio:
        qs = qs.filter(data_referencia__gte=data_inicio)
    if data_fim:
        qs = qs.filter(data_referencia__lte=data_fim)
    if tipo:
        qs = qs.filter(tipo=tipo)

    titulo_tipo = "Lançamentos de Folga"
    if tipo == LancamentoFolga.CREDITO:
        titulo_tipo = "Créditos de Folga"
    elif tipo == LancamentoFolga.DEBITO:
        titulo_tipo = "Débitos de Folga"

    p_str = ""
    if data_inicio and data_fim:
        p_str = f"Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}"

    sub = f"Unidade: {unidade.nome} • {p_str}" if unidade else f"Todas as Unidades • {p_str}"

    header = ['Data Ref.', 'Funcionário', 'Tipo', 'Dias', 'Motivo / Evento']
    widths = [3.0 * cm, 5.5 * cm, 2.5 * cm, 2.0 * cm, 5.0 * cm]

    rows = [header]
    total_creditos = total_debitos = 0
    for lanc in qs:
        dt_str = lanc.data_referencia.strftime('%d/%m/%Y')
        func_str = lanc.funcionario.nome
        if lanc.tipo == LancamentoFolga.CREDITO:
            tipo_str = "<font color='#16A34A'><b>CRÉDITO</b></font>"
            total_creditos += lanc.dias
        else:
            tipo_str = "<font color='#DC2626'><b>DÉBITO</b></font>"
            total_debitos += lanc.dias
        motivo_str = lanc.motivo or '—'
        if lanc.evento:
            motivo_str += f"<br/><font color='#64748B'>Evento: {lanc.evento.nome}</font>"

        rows.append([dt_str, func_str, tipo_str, str(lanc.dias), motivo_str])

    resumo = (
        f"Total de lançamentos: <b>{len(rows) - 1}</b> | "
        f"Dias creditados: <b>{total_creditos}</b> | Dias debitados: <b>{total_debitos}</b>"
    )
    return _criar_pdf_base(f"Relatório de {titulo_tipo}", sub, rows, widths, resumo)