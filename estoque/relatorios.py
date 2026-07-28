import io


def _pdf_temporario(titulo):
    """Retorna um buffer simples até você implementar o ReportLab/WeasyPrint."""
    buffer = io.BytesIO()
    buffer.write(f"PDF do relatório '{titulo}' em desenvolvimento.".encode('utf-8'))
    buffer.seek(0)
    return buffer


def relatorio_estoque_atual():
    return _pdf_temporario("Estoque Atual")


def relatorio_estoque_baixo():
    return _pdf_temporario("Estoque Baixo")


def relatorio_validade(dias=None):
    return _pdf_temporario("Validade")


def relatorio_movimentacoes(data_inicio, data_fim, tipo=None):
    return _pdf_temporario("Movimentações")


def relatorio_gastos(data_inicio, data_fim):
    return _pdf_temporario("Gastos")


def relatorio_por_categoria():
    return _pdf_temporario("Por Categoria")