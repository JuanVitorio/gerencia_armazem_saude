"""
Importação do PDF de Requisição de Materiais para o estoque de uma unidade.

Fluxo:
  1. RequisicaoView gera o PDF e embute nele (metadado "Keywords") os dados
     da lista — produtos do estoque central, quantidades e unidades de
     medida — assinados com a SECRET_KEY (django.core.signing). O documento
     impresso não muda nada.
  2. O funcionário do posto solta o PDF na tela de Produtos; `ler_dados_pdf`
     extrai e valida a assinatura (um PDF editado ou de outro sistema é
     recusado).
  3. `montar_itens_confirmacao` monta a tela de confirmação, sugerindo para
     cada item o produto equivalente já existente no posto (mesmo nome +
     detalhes) ou o cadastro de um produto novo.
  4. `aplicar_importacao` grava tudo numa transação só: Entrada no posto,
     Saída no estoque central e — quando o sistema da Secretaria tem menos
     do que foi entregue — uma DivergenciaEstoque, sem bloquear o usuário.
"""
import uuid
from datetime import date

from django.core import signing
from django.db import IntegrityError, transaction

from .models import DivergenciaEstoque, ImportacaoRequisicao, Movimentacao, Produto, Unidade

# Prefixo do metadado no PDF — identifica PDFs gerados por este sistema.
PREFIXO_METADADO = 'estoque-requisicao:'
SALT = 'estoque.requisicao.importacao'
VERSAO = 1
TAMANHO_MAXIMO_PDF = 5 * 1024 * 1024  # 5 MB — um PDF de requisição tem poucos KB

DESTINO_NOVO = 'novo'


class ImportacaoErro(Exception):
    """Erro com mensagem amigável, pronta para exibir ao usuário."""


# ---------------------------------------------------------------------------
# Geração (usado por RequisicaoView ao gerar o PDF)
# ---------------------------------------------------------------------------

def gerar_dados_pdf(unidade, solicitante, data_solicitacao, titulo, itens):
    """
    Serializa e assina os dados da requisição para embutir no PDF.
    `itens` segue o formato de RequisicaoView: [{'produto', 'quantidade', 'unidade_medida'}].
    """
    dados = {
        'v': VERSAO,
        'codigo': str(uuid.uuid4()),
        'unidade': unidade.pk if unidade else None,
        'titulo': titulo or '',
        'solicitante': solicitante or '',
        'data': data_solicitacao.isoformat() if data_solicitacao else None,
        'itens': [
            {'p': item['produto'].pk, 'q': item['quantidade'], 'u': item['unidade_medida']}
            for item in itens
        ],
    }
    return PREFIXO_METADADO + signing.dumps(dados, salt=SALT, compress=True)


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def validar_token(token):
    """Valida a assinatura do token (sem o prefixo) e devolve os dados."""
    try:
        dados = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        raise ImportacaoErro(
            'Os dados deste PDF não conferem — ele pode ter sido editado depois de gerado. '
            'Gere a requisição novamente pelo sistema.'
        )
    if not isinstance(dados, dict) or dados.get('v') != VERSAO or not dados.get('itens'):
        raise ImportacaoErro('Formato de requisição não reconhecido.')
    return dados


def ler_dados_pdf(arquivo):
    """
    Extrai os dados embutidos num PDF de requisição enviado pelo usuário.
    Devolve (token, dados) — o token volta no formulário de confirmação para
    que os dados sejam revalidados no POST final.
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if arquivo.size > TAMANHO_MAXIMO_PDF:
        raise ImportacaoErro('Arquivo muito grande. Envie o PDF da requisição gerado pelo sistema.')

    try:
        leitor = PdfReader(arquivo)
        metadados = leitor.metadata or {}
    except (PdfReadError, ValueError, TypeError, KeyError):
        raise ImportacaoErro('Não foi possível ler o arquivo. Verifique se é um PDF válido.')

    palavras_chave = str(metadados.get('/Keywords') or '')
    if not palavras_chave.startswith(PREFIXO_METADADO):
        raise ImportacaoErro(
            'Este PDF não contém os dados de importação. Só é possível importar requisições '
            'geradas pelo sistema a partir desta versão — gere a requisição novamente.'
        )

    token = palavras_chave[len(PREFIXO_METADADO):]
    return token, validar_token(token)


def unidade_destino(dados, usuario_unidade):
    """
    Unidade que vai receber os itens: a unidade solicitante gravada no PDF.
    Um usuário de posto só pode importar requisições da própria unidade;
    administradores (usuario_unidade=None) podem importar para qualquer uma.
    """
    unidade = Unidade.objects.filter(pk=dados.get('unidade'), ativa=True).first()
    if unidade is None:
        raise ImportacaoErro('A unidade solicitante desta requisição não existe mais ou está inativa.')
    if usuario_unidade is not None and unidade.pk != usuario_unidade.pk:
        raise ImportacaoErro(
            f'Esta requisição foi feita para "{unidade.nome}". '
            f'Você só pode importar requisições da sua unidade ({usuario_unidade.nome}).'
        )
    if unidade.tipo == Unidade.SECRETARIA:
        raise ImportacaoErro('Requisições não podem ser importadas para o estoque central (Secretaria).')
    return unidade


def verificar_nao_importada(dados):
    importacao = ImportacaoRequisicao.objects.filter(codigo=dados['codigo']).select_related('usuario').first()
    if importacao is not None:
        if importacao.usuario:
            quem = importacao.usuario.get_full_name() or importacao.usuario.username
        else:
            quem = 'outro usuário'
        raise ImportacaoErro(
            f'Esta requisição já foi importada em {importacao.criado_em:%d/%m/%Y às %H:%M} por {quem}.'
        )


def data_solicitacao(dados):
    try:
        return date.fromisoformat(dados['data']) if dados.get('data') else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Tela de confirmação
# ---------------------------------------------------------------------------

def montar_itens_confirmacao(dados, unidade):
    """
    Uma linha por item do PDF, com o produto do estoque central e as opções
    de destino no posto: produtos com o mesmo nome (o de mesmos detalhes vem
    pré-selecionado) ou "cadastrar como novo".
    """
    itens_pdf = dados['itens']
    centrais = Produto.objects.select_related('categoria', 'unidade').in_bulk([i['p'] for i in itens_pdf])
    nomes = {p.nome for p in centrais.values()}
    do_posto = {}
    for p in Produto.objects.filter(unidade=unidade, ativo=True, nome__in=nomes).order_by('detalhes'):
        do_posto.setdefault(p.nome, []).append(p)

    labels_medida = dict(Produto.UNIDADE_CHOICES)
    linhas = []
    for indice, item in enumerate(itens_pdf):
        central = centrais.get(item['p'])
        candidatos = do_posto.get(central.nome, []) if central else []
        sugerido = next((c for c in candidatos if c.detalhes == central.detalhes), None)
        linhas.append({
            'indice': indice,
            'central': central,  # None = produto excluído da Secretaria depois de gerar o PDF
            'quantidade': item['q'],
            'unidade_medida': item['u'],
            'unidade_medida_label': labels_medida.get(item['u'], item['u']),
            'candidatos': candidatos,
            'destino': str(sugerido.pk) if sugerido else DESTINO_NOVO,
            'incluir': central is not None,
            'lote': '',
            'validade': '',
            'erro': '',
        })
    return linhas


def ler_escolhas(linhas, post):
    """
    Aplica as escolhas do formulário de confirmação sobre as linhas (para
    reexibir a tela com o que o usuário digitou, caso haja erro). Devolve a
    quantidade de erros encontrados.
    """
    erros = 0
    for linha in linhas:
        i = linha['indice']
        linha['incluir'] = linha['central'] is not None and post.get(f'incluir_{i}') == 'on'
        linha['destino'] = post.get(f'destino_{i}', DESTINO_NOVO)
        linha['lote'] = post.get(f'lote_{i}', '').strip()
        linha['validade'] = post.get(f'validade_{i}', '').strip()
        linha['erro'] = ''
        if not linha['incluir']:
            continue

        try:
            linha['quantidade'] = int(post.get(f'quantidade_{i}', ''))
            if linha['quantidade'] <= 0:
                raise ValueError
        except ValueError:
            linha['erro'] = 'Informe a quantidade recebida (maior que zero).'
        else:
            ids_validos = {str(c.pk) for c in linha['candidatos']}
            if linha['destino'] != DESTINO_NOVO and linha['destino'] not in ids_validos:
                linha['erro'] = 'Produto de destino inválido.'
            elif linha['validade']:
                try:
                    date.fromisoformat(linha['validade'])
                except ValueError:
                    linha['erro'] = 'Data de validade inválida.'
        if linha['erro']:
            erros += 1
    return erros


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------

def aplicar_importacao(dados, unidade, linhas, usuario):
    """
    Grava a importação numa transação única. Para cada linha incluída:
      - Entrada no produto do posto (existente ou recém-cadastrado);
      - Saída no produto da Secretaria, limitada ao que o sistema tem;
      - DivergenciaEstoque quando o entregue passa do que o sistema tinha,
        ou quando a unidade de medida difere da cadastrada na Secretaria
        (ex: requisitado em Unidade, cadastrado em Caixa) e por isso a
        baixa não pode ser feita automaticamente.
    Devolve um resumo para a mensagem de sucesso.
    """
    resumo = {'importacao': None, 'novos': 0, 'atualizados': 0, 'divergencias': 0}
    incluidas = [l for l in linhas if l['incluir']]
    if not incluidas:
        raise ImportacaoErro('Selecione ao menos um item para importar.')

    try:
        with transaction.atomic():
            importacao = ImportacaoRequisicao.objects.create(
                codigo=dados['codigo'],
                unidade=unidade,
                titulo=dados.get('titulo', '')[:100],
                solicitante=dados.get('solicitante', '')[:150],
                data_solicitacao=data_solicitacao(dados),
                usuario=usuario,
            )
            resumo['importacao'] = importacao
            referencia = f'Requisição "{importacao.titulo or "Requisição de Materiais"}"'
            if importacao.data_solicitacao:
                referencia += f' de {importacao.data_solicitacao:%d/%m/%Y}'

            for linha in incluidas:
                central = Produto.objects.select_for_update().get(pk=linha['central'].pk)
                quantidade = linha['quantidade']

                # --- Entrada no posto ---
                if linha['destino'] == DESTINO_NOVO:
                    destino = Produto.objects.create(
                        unidade=unidade,
                        categoria=central.categoria,
                        nome=central.nome,
                        detalhes=central.detalhes,
                        sku=central.sku,
                        unidade_medida=linha['unidade_medida'],
                        lote=linha['lote'],
                        data_validade=date.fromisoformat(linha['validade']) if linha['validade'] else None,
                        quantidade=0,
                    )
                    resumo['novos'] += 1
                else:
                    destino = Produto.objects.select_for_update().get(pk=linha['destino'], unidade=unidade)
                    resumo['atualizados'] += 1
                Movimentacao(
                    produto=destino, tipo=Movimentacao.ENTRADA, quantidade=quantidade,
                    motivo=f'{referencia} — recebido de {central.unidade.nome}'[:255],
                    usuario=usuario,
                ).save()

                # --- Baixa no estoque central ---
                if linha['unidade_medida'] != central.unidade_medida:
                    DivergenciaEstoque.objects.create(
                        tipo=DivergenciaEstoque.UNIDADE_MEDIDA_DIFERENTE, produto=central,
                        importacao=importacao, quantidade_entregue=quantidade,
                        unidade_medida_entregue=linha['unidade_medida'],
                        quantidade_sistema=central.quantidade, quantidade_baixada=0,
                    )
                    resumo['divergencias'] += 1
                    continue

                disponivel = central.quantidade
                baixa = min(quantidade, disponivel)
                if baixa > 0:
                    Movimentacao(
                        produto=central, tipo=Movimentacao.SAIDA, quantidade=baixa,
                        motivo=f'{referencia} — entregue para {unidade.nome}'[:255],
                        usuario=usuario,
                    ).save()
                if baixa < quantidade:
                    DivergenciaEstoque.objects.create(
                        tipo=DivergenciaEstoque.ESTOQUE_INSUFICIENTE, produto=central,
                        importacao=importacao, quantidade_entregue=quantidade,
                        unidade_medida_entregue=linha['unidade_medida'],
                        quantidade_sistema=disponivel, quantidade_baixada=baixa,
                    )
                    resumo['divergencias'] += 1
    except IntegrityError:
        # Duas pessoas confirmando o mesmo PDF ao mesmo tempo: o código único
        # da ImportacaoRequisicao barra a segunda.
        raise ImportacaoErro('Esta requisição acabou de ser importada por outro usuário.')

    return resumo
