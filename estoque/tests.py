from datetime import timedelta
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Categoria, Movimentacao, PerfilUsuario, Produto, Unidade
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
