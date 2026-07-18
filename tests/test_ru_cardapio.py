from unittest.mock import patch

import requests as requests_lib

from ru_cardapio import (
    agrupar_por_refeicao,
    categorizar,
    formatar_mensagem,
    formatar_refeicao,
    gerar_cardapio_do_dia,
)


def test_categorizar_arroz():
    assert categorizar("Arroz Branco") == "arroz"


def test_categorizar_feijao():
    assert categorizar("Feijão Carioca") == "feijao"


def test_categorizar_proteina_pelo_nome():
    assert categorizar("Frango Grelhado") == "proteina"


def test_categorizar_proteina_pela_composicao():
    # "Guisado com Batata" só revela carne na composição, não no nome do prato.
    assert categorizar("Guisado com Batata", "Carne moída, batata, cebola") == "proteina"


def test_categorizar_ignora_disclaimer_de_traco():
    # "(pode conter ovos)" no disclaimer não pode fazer "OVO" bater como
    # falso positivo de proteína — a composição real não tem carne nenhuma.
    nome = "Purê de Batata"
    descricao = "Purê de batata, manteiga, leite (pode conter ovos)"
    assert categorizar(nome, descricao) == "guarnicao"


def test_categorizar_guarnicao_padrao():
    assert categorizar("Purê de Batata") == "guarnicao"


def test_formatar_refeicao_sem_itens():
    resultado = formatar_refeicao("ALMOÇO", [])
    assert "Sem almoço cadastrada" in resultado


def test_formatar_refeicao_item_sem_nome_e_ignorado():
    itens = [{"descricao": "sem nome"}, {"nome": "Arroz Branco"}]
    resultado = formatar_refeicao("ALMOÇO", itens)
    assert "Arroz Branco" in resultado
    assert resultado.count("\n") == 0


def test_formatar_refeicao_todos_itens_sem_nome_cai_no_aviso_padrao():
    itens = [{"descricao": "sem nome"}]
    resultado = formatar_refeicao("ALMOÇO", itens)
    assert "Sem almoço cadastrada" in resultado


def test_agrupar_por_refeicao():
    itens = [
        {"nome": "Arroz", "refeicao": "almoço"},
        {"nome": "Peixe", "refeicao": "JANTA"},
    ]
    grupos = agrupar_por_refeicao(itens)
    assert len(grupos["ALMOÇO"]) == 1
    assert len(grupos["JANTA"]) == 1


def test_formatar_mensagem_inclui_cabecalho_e_restaurantes():
    dados = {"Unidade Centro": [{"nome": "Arroz", "refeicao": "ALMOÇO"}]}
    mensagem = formatar_mensagem("17/07/2026", dados)
    assert "Sexta-feira" in mensagem
    assert "Unidade Centro" in mensagem
    assert "Arroz" in mensagem


@patch("ru_cardapio.buscar_cardapio")
def test_gerar_cardapio_do_dia_usa_api_mockada(mock_buscar):
    mock_buscar.return_value = [{"nome": "Arroz", "refeicao": "ALMOÇO"}]
    mensagem = gerar_cardapio_do_dia("17/07/2026")
    assert "Arroz" in mensagem
    assert mock_buscar.call_count == 2  # um por restaurante configurado (Centro + Anglo)


@patch("ru_cardapio.buscar_cardapio")
def test_gerar_cardapio_do_dia_continua_se_uma_api_falhar(mock_buscar):
    def efeito(restaurante_id, data_str):
        if restaurante_id == 6:
            raise requests_lib.RequestException("fora do ar")
        return [{"nome": "Peixe", "refeicao": "JANTA"}]

    mock_buscar.side_effect = efeito
    mensagem = gerar_cardapio_do_dia("17/07/2026")
    assert "Peixe" in mensagem
