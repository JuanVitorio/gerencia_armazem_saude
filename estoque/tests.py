import io
import json
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .importacao import PREFIXO_METADADO
from .models import (
    Categoria, DivergenciaEstoque, ImportacaoRequisicao, Movimentacao, PerfilUsuario, Produto,
    RascunhoRequisicao, Unidade,
)
from .relatorios import (
    relatorio_estoque_atual, relatorio_estoque_baixo,
    relatorio_movimentacoes, relatorio_por_categoria, relatorio_validade,
)


class EstoqueModelTests(TestCase):

    def setUp(self):
        self.cat_med, _ = Categoria.objects.get_or_create(nome='Medicamentos', defaults={'tipo': Categoria.MEDICAMENTO})
        self.cat_limp, _ = Categoria.objects.get_or_create(nome='Produtos de Limpeza', defaults={'tipo': Categoria.MATERIAL_LIMPEZA})
        
        self.unidade1 = Unidade.objects.create(nome='UBS Centro', tipo=Unidade.POSTO_SAUDE)
        self.unidade2 = Unidade.objects.create(nome='Secretaria de Saúde', tipo=Unidade.SECRETARIA)

        self.prod1 = Produto.objects.create(
            nome='Paracetamol 500mg',
            categoria=self.cat_med,
            unidade=self.unidade1,
            quantidade=50,
            unidade_medida='CX',
        )

    def test_criacao_produto_e_unidade(self):
        self.assertEqual(self.prod1.nome, 'Paracetamol 500mg')
        self.assertEqual(self.prod1.unidade.nome, 'UBS Centro')
        self.assertFalse(self.prod1.estoque_baixo)

    def test_movimentacao_entrada_e_saida(self):
        user = User.objects.create_user(username='operador', password='123')
        
        # Entrada de 20
        mov_in = Movimentacao(produto=self.prod1, tipo=Movimentacao.ENTRADA, quantidade=20, usuario=user)
        mov_in.save()
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.quantidade, 70)

        # Saída de 30
        mov_out = Movimentacao(produto=self.prod1, tipo=Movimentacao.SAIDA, quantidade=30, usuario=user)
        mov_out.save()
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.quantidade, 40)

    def test_estoque_insuficiente(self):
        user = User.objects.create_user(username='operador2', password='123')
        mov_out = Movimentacao(produto=self.prod1, tipo=Movimentacao.SAIDA, quantidade=100, usuario=user)
        with self.assertRaises(ValidationError):
            mov_out.save()


class PerfilUsuarioTests(TestCase):

    def setUp(self):
        self.unidade = Unidade.objects.create(nome='Posto Rural', tipo=Unidade.POSTO_SAUDE)
        self.user_comum = User.objects.create_user(username='comum', password='123')
        PerfilUsuario.objects.create(usuario=self.user_comum, unidade=self.unidade)

        self.user_admin = User.objects.create_user(username='admin', password='123')
        PerfilUsuario.objects.create(usuario=self.user_admin, unidade=None)

    def test_perfil_is_admin(self):
        self.assertFalse(self.user_comum.perfil.is_admin)
        self.assertTrue(self.user_admin.perfil.is_admin)


class RelatoriosPDFTests(TestCase):

    def setUp(self):
        self.unidade = Unidade.objects.create(nome='UBS Teste', tipo=Unidade.POSTO_SAUDE)
        self.cat, _ = Categoria.objects.get_or_create(nome='Vacinas', defaults={'tipo': Categoria.VACINA})
        self.prod = Produto.objects.create(
            nome='Vacina Gripe', categoria=self.cat, unidade=self.unidade,
            quantidade=5, data_validade=timezone.localdate() + timedelta(days=10)
        )

    def test_geracao_relatorios_pdf(self):
        pdf1 = relatorio_estoque_atual(self.unidade)
        self.assertTrue(pdf1.getvalue().startswith(b'%PDF'))

        pdf2 = relatorio_estoque_baixo(self.unidade)
        self.assertTrue(pdf2.getvalue().startswith(b'%PDF'))

        pdf3 = relatorio_validade(self.unidade, dias=30)
        self.assertTrue(pdf3.getvalue().startswith(b'%PDF'))

        pdf4 = relatorio_por_categoria(self.unidade)
        self.assertTrue(pdf4.getvalue().startswith(b'%PDF'))


class ImportacaoRequisicaoTests(TestCase):
    """Fluxo completo: gerar o PDF da requisição → soltar em Produtos → confirmar."""

    def setUp(self):
        self.secretaria = Unidade.objects.create(nome='Secretaria de Saúde', tipo=Unidade.SECRETARIA)
        self.posto = Unidade.objects.create(nome='UBS Centro', tipo=Unidade.POSTO_SAUDE)
        self.outro_posto = Unidade.objects.create(nome='UBS Rural', tipo=Unidade.POSTO_SAUDE)
        self.cat, _ = Categoria.objects.get_or_create(nome='Medicamentos', defaults={'tipo': Categoria.MEDICAMENTO})

        self.dipirona = Produto.objects.create(
            nome='Dipirona', detalhes='500mg', categoria=self.cat, unidade=self.secretaria,
            quantidade=100, unidade_medida='CX',
        )
        self.luva = Produto.objects.create(
            nome='Luva', detalhes='M', unidade=self.secretaria, quantidade=5, unidade_medida='CX',
        )
        self.gaze = Produto.objects.create(
            nome='Gaze', unidade=self.secretaria, quantidade=50, unidade_medida='PC',
        )
        # A dipirona já existe no posto: deve ser somada, não duplicada.
        self.dipirona_posto = Produto.objects.create(
            nome='Dipirona', detalhes='500mg', unidade=self.posto, quantidade=3, unidade_medida='CX',
        )

        self.user = User.objects.create_user(username='posto', password='123')
        PerfilUsuario.objects.create(usuario=self.user, unidade=self.posto)
        self.client.force_login(self.user)

    def _gerar_pdf(self, itens, unidade=None):
        resposta = self.client.post(reverse('estoque:requisicao'), {
            'unidade': (unidade or self.posto).pk,
            'solicitante': 'Maria',
            'data_solicitacao': timezone.localdate().isoformat(),
            'titulo': 'Insumos',
            'itens_json': json.dumps(itens),
        })
        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        return resposta.content

    def _upload(self, pdf_bytes):
        return self.client.post(reverse('estoque:produto_importar_requisicao'), {
            'arquivo': SimpleUploadedFile('req.pdf', pdf_bytes, content_type='application/pdf'),
        })

    def _itens_padrao(self):
        return [
            {'produto_id': self.dipirona.pk, 'quantidade': 10, 'unidade_medida': 'CX'},
            {'produto_id': self.luva.pk, 'quantidade': 8, 'unidade_medida': 'CX'},   # sistema só tem 5
            {'produto_id': self.gaze.pk, 'quantidade': 20, 'unidade_medida': 'UN'},  # cadastrada em PC
        ]

    def _confirmar(self, token, **extra):
        dados = {
            'dados': token,
            'incluir_0': 'on', 'quantidade_0': '10', 'destino_0': str(self.dipirona_posto.pk),
            'incluir_1': 'on', 'quantidade_1': '8', 'destino_1': 'novo',
            'incluir_2': 'on', 'quantidade_2': '20', 'destino_2': 'novo',
        }
        dados.update(extra)
        return self.client.post(reverse('estoque:produto_importar_confirmar'), dados)

    def test_pdf_gerado_contem_dados_e_abre_confirmacao(self):
        from pypdf import PdfReader

        pdf = self._gerar_pdf(self._itens_padrao())
        self.assertTrue(str(PdfReader(io.BytesIO(pdf)).metadata['/Keywords']).startswith(PREFIXO_METADADO))

        resposta = self._upload(pdf)
        self.assertEqual(resposta.status_code, 200)
        linhas = resposta.context['linhas']
        self.assertEqual(len(linhas), 3)
        # Dipirona sugerida como o produto já existente; os outros como novos.
        self.assertEqual(linhas[0]['destino'], str(self.dipirona_posto.pk))
        self.assertEqual(linhas[1]['destino'], 'novo')
        # Nada é gravado antes da confirmação.
        self.assertFalse(ImportacaoRequisicao.objects.exists())

    def test_confirmacao_da_entrada_baixa_e_registra_divergencias(self):
        token = self._upload(self._gerar_pdf(self._itens_padrao())).context['token']
        resposta = self._confirmar(token, lote_1='L123', validade_1='2027-01-31')
        self.assertRedirects(resposta, reverse('estoque:produto_list'), fetch_redirect_response=False)

        # Posto: dipirona somada à existente; luva e gaze cadastradas.
        self.dipirona_posto.refresh_from_db()
        self.assertEqual(self.dipirona_posto.quantidade, 13)
        self.assertEqual(Produto.objects.filter(unidade=self.posto, nome='DIPIRONA').count(), 1)
        luva_posto = Produto.objects.get(unidade=self.posto, nome='LUVA')
        self.assertEqual((luva_posto.quantidade, luva_posto.lote, luva_posto.detalhes), (8, 'L123', 'M'))
        self.assertEqual(str(luva_posto.data_validade), '2027-01-31')
        gaze_posto = Produto.objects.get(unidade=self.posto, nome='GAZE')
        self.assertEqual((gaze_posto.quantidade, gaze_posto.unidade_medida), (20, 'UN'))

        # Secretaria: dipirona baixada normalmente; luva zerada (só tinha 5);
        # gaze intocada (unidade de medida diferente da cadastrada).
        for p in (self.dipirona, self.luva, self.gaze):
            p.refresh_from_db()
        self.assertEqual((self.dipirona.quantidade, self.luva.quantidade, self.gaze.quantidade), (90, 0, 50))

        div_luva = DivergenciaEstoque.objects.get(produto=self.luva)
        self.assertEqual(div_luva.tipo, DivergenciaEstoque.ESTOQUE_INSUFICIENTE)
        self.assertEqual(
            (div_luva.quantidade_sistema, div_luva.quantidade_baixada, div_luva.quantidade_faltante), (5, 5, 3),
        )
        self.assertEqual(
            DivergenciaEstoque.objects.get(produto=self.gaze).tipo, DivergenciaEstoque.UNIDADE_MEDIDA_DIFERENTE,
        )
        self.assertFalse(DivergenciaEstoque.objects.filter(produto=self.dipirona).exists())

        # Histórico: as entradas no posto ficam registradas como movimentações.
        self.assertEqual(
            Movimentacao.objects.filter(produto__unidade=self.posto, tipo=Movimentacao.ENTRADA).count(), 3,
        )

    def test_quantidade_editada_e_item_desmarcado(self):
        token = self._upload(self._gerar_pdf(self._itens_padrao())).context['token']
        self._confirmar(token, quantidade_0='4', incluir_1='', incluir_2='')
        self.dipirona_posto.refresh_from_db()
        self.dipirona.refresh_from_db()
        self.assertEqual(self.dipirona_posto.quantidade, 7)
        self.assertEqual(self.dipirona.quantidade, 96)
        self.assertFalse(Produto.objects.filter(unidade=self.posto, nome='LUVA').exists())
        self.assertFalse(DivergenciaEstoque.objects.exists())

    def test_quantidade_invalida_reexibe_confirmacao_sem_gravar(self):
        token = self._upload(self._gerar_pdf(self._itens_padrao())).context['token']
        resposta = self._confirmar(token, quantidade_0='0')
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context['linhas'][0]['erro'])
        self.assertFalse(ImportacaoRequisicao.objects.exists())
        self.dipirona.refresh_from_db()
        self.assertEqual(self.dipirona.quantidade, 100)

    def test_mesmo_pdf_nao_pode_ser_importado_duas_vezes(self):
        pdf = self._gerar_pdf(self._itens_padrao())
        token = self._upload(pdf).context['token']
        self._confirmar(token)
        # Novo upload do mesmo PDF e reenvio da mesma confirmação: ambos recusados.
        self.assertRedirects(self._upload(pdf), reverse('estoque:produto_list'), fetch_redirect_response=False)
        self._confirmar(token)
        self.dipirona_posto.refresh_from_db()
        self.assertEqual(self.dipirona_posto.quantidade, 13)
        self.assertEqual(ImportacaoRequisicao.objects.count(), 1)

    def test_pdf_sem_dados_ou_adulterado_e_recusado(self):
        resposta = self._upload(relatorio_estoque_atual(self.posto).getvalue())
        self.assertRedirects(resposta, reverse('estoque:produto_list'), fetch_redirect_response=False)

        token = self._upload(self._gerar_pdf(self._itens_padrao())).context['token']
        self._confirmar(token[:-3] + 'xyz')
        self.assertFalse(ImportacaoRequisicao.objects.exists())

    def test_posto_nao_importa_requisicao_de_outra_unidade(self):
        admin = User.objects.create_user(username='adm', password='123', is_staff=True)
        self.client.force_login(admin)
        pdf = self._gerar_pdf(self._itens_padrao(), unidade=self.outro_posto)

        self.client.force_login(self.user)
        resposta = self._upload(pdf)
        self.assertRedirects(resposta, reverse('estoque:produto_list'), fetch_redirect_response=False)
        self.assertFalse(ImportacaoRequisicao.objects.exists())

    def test_divergencias_visiveis_so_para_admin(self):
        self.assertEqual(self.client.get(reverse('estoque:divergencia_list')).status_code, 403)
        token = self._upload(self._gerar_pdf(self._itens_padrao())).context['token']
        self._confirmar(token)

        admin = User.objects.create_user(username='adm', password='123', is_staff=True)
        self.client.force_login(admin)
        resposta = self.client.get(reverse('estoque:divergencia_list'))
        self.assertEqual(len(resposta.context['divergencias']), 2)

        div = DivergenciaEstoque.objects.first()
        self.client.post(reverse('estoque:divergencia_resolver', args=[div.pk]))
        div.refresh_from_db()
        self.assertTrue(div.resolvida)
        self.assertEqual(div.resolvida_por, admin)


class RascunhoRequisicaoTests(TestCase):
    """Salvar a lista pela metade, voltar depois, editar e finalizar."""

    def setUp(self):
        self.secretaria = Unidade.objects.create(nome='Secretaria de Saúde', tipo=Unidade.SECRETARIA)
        self.posto = Unidade.objects.create(nome='UBS Centro', tipo=Unidade.POSTO_SAUDE)
        self.dipirona = Produto.objects.create(nome='Dipirona', unidade=self.secretaria, quantidade=100, unidade_medida='CX')
        self.gaze = Produto.objects.create(nome='Gaze', unidade=self.secretaria, quantidade=50, unidade_medida='PC')
        # Produto de outro estoque: não pode entrar na lista, nem em rascunho.
        self.do_posto = Produto.objects.create(nome='Luva', unidade=self.posto, quantidade=5)

        self.user = User.objects.create_user(username='posto', password='123')
        PerfilUsuario.objects.create(usuario=self.user, unidade=self.posto)
        self.client.force_login(self.user)
        self.url = reverse('estoque:requisicao')

    def _post(self, itens, **extra):
        dados = {
            'unidade': self.posto.pk, 'solicitante': 'Maria', 'titulo': 'Insumos',
            'data_solicitacao': '2026-10-05', 'itens_json': json.dumps(itens),
        }
        dados.update(extra)
        return self.client.post(self.url, dados)

    def test_salva_rascunho_incompleto_sem_gerar_pdf_nem_movimentar_estoque(self):
        resposta = self._post(
            [{'produto_id': self.dipirona.pk, 'quantidade': 3, 'unidade_medida': 'CX'},
             {'produto_id': self.do_posto.pk, 'quantidade': 1, 'unidade_medida': 'UN'}],
            acao='rascunho', solicitante='',
        )
        rascunho = RascunhoRequisicao.objects.get()
        self.assertRedirects(resposta, f'{self.url}?rascunho={rascunho.pk}')
        self.assertEqual(rascunho.itens, [{'produto_id': self.dipirona.pk, 'quantidade': 3, 'unidade_medida': 'CX'}])
        self.assertEqual((rascunho.titulo, rascunho.solicitante, rascunho.unidade), ('Insumos', '', self.posto))
        self.assertFalse(Movimentacao.objects.exists())
        self.dipirona.refresh_from_db()
        self.assertEqual(self.dipirona.quantidade, 100)

        # Lista vazia também pode ser salva.
        self._post([], acao='rascunho')
        self.assertEqual(RascunhoRequisicao.objects.count(), 2)

    def test_continuar_editar_e_finalizar_rascunho(self):
        self._post([{'produto_id': self.dipirona.pk, 'quantidade': 3, 'unidade_medida': 'CX'}], acao='rascunho')
        rascunho = RascunhoRequisicao.objects.get()

        # Voltando depois: a página reabre com o cabeçalho e os itens do rascunho.
        resposta = self.client.get(self.url, {'rascunho': rascunho.pk})
        form = resposta.context['form']
        self.assertEqual(form.initial['titulo'], 'Insumos')
        self.assertEqual(json.loads(form.initial['itens_json'])[0]['produto_id'], self.dipirona.pk)
        self.assertEqual(resposta.context['rascunho'], rascunho)

        # Alterando produtos/quantidades: atualiza o MESMO rascunho.
        self._post(
            [{'produto_id': self.dipirona.pk, 'quantidade': 5, 'unidade_medida': 'CX'},
             {'produto_id': self.gaze.pk, 'quantidade': 2, 'unidade_medida': 'PC'}],
            acao='rascunho', rascunho=rascunho.pk,
        )
        rascunho.refresh_from_db()
        self.assertEqual(RascunhoRequisicao.objects.count(), 1)
        self.assertEqual([i['quantidade'] for i in rascunho.itens], [5, 2])

        # Finalizando: gera o PDF e o rascunho deixa de existir.
        resposta = self._post(rascunho.itens, rascunho=rascunho.pk)
        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        self.assertFalse(RascunhoRequisicao.objects.exists())

    def test_gerar_pdf_com_erro_mantem_rascunho(self):
        self._post([{'produto_id': self.dipirona.pk, 'quantidade': 3, 'unidade_medida': 'CX'}], acao='rascunho')
        rascunho = RascunhoRequisicao.objects.get()
        resposta = self._post(rascunho.itens, rascunho=rascunho.pk, solicitante='')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['rascunho'], rascunho)
        self.assertTrue(RascunhoRequisicao.objects.exists())

    def test_rascunho_de_outro_usuario_nao_acessivel(self):
        outro = User.objects.create_user(username='outro', password='123')
        alheio = RascunhoRequisicao.objects.create(usuario=outro, titulo='Do outro')

        self.assertEqual(self.client.get(self.url, {'rascunho': alheio.pk}).status_code, 404)
        self.assertNotIn(alheio, self.client.get(self.url).context['rascunhos'])
        self.client.post(reverse('estoque:rascunho_requisicao_delete', args=[alheio.pk]))
        # Salvar apontando para o rascunho alheio cria um novo, sem tocar no dele.
        self._post([], acao='rascunho', rascunho=alheio.pk, titulo='Meu')
        alheio.refresh_from_db()
        self.assertEqual(alheio.titulo, 'Do outro')
        self.assertTrue(RascunhoRequisicao.objects.filter(usuario=self.user, titulo='Meu').exists())

    def test_excluir_rascunho(self):
        rascunho = RascunhoRequisicao.objects.create(usuario=self.user)
        resposta = self.client.post(reverse('estoque:rascunho_requisicao_delete', args=[rascunho.pk]))
        self.assertRedirects(resposta, self.url)
        self.assertFalse(RascunhoRequisicao.objects.exists())

