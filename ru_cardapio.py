"""Busca e formata o cardápio público do Restaurante Universitário (RU) da UFPel.

Fonte dos dados: endpoint JSON público do sistema Cobalto (sem necessidade de login):
https://cobalto.ufpel.edu.br/portal/cardapios/cardapioPublico/listaCardapios
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime

import requests

# Remove avisos de traço/alergênico do tipo "(pode conter ovos)" antes de procurar
# palavras de proteína na composição — são disclaimers, não o ingrediente principal.
_RE_POSSIVEL_TRACO = re.compile(r"\(pode conter[^)]*\)", re.IGNORECASE)

BASE_URL = "https://cobalto.ufpel.edu.br/portal/cardapios/cardapioPublico/listaCardapios"

# IDs de restaurante usados pelo Cobalto (campo cmbRestaurante do filtro do site).
RESTAURANTES = {
    "Unidade Centro": 6,
    "Anglo": 8,
}

REFEICOES = ["ALMOÇO", "JANTA"]

# O Cobalto não marca qual item é "a proteína" — só devolve uma lista plana de
# itens por refeição. Por isso categorizamos pelo nome do prato.
PALAVRAS_ARROZ = ["ARROZ"]
PALAVRAS_FEIJAO = ["FEIJÃO", "FEIJAO", "FEIJOADA"]
PALAVRAS_SALADA = ["SALADA"]
PALAVRAS_FRUTA = ["FRUTA", "SOBREMESA"]
PALAVRAS_PROTEINA = [
    "CARNE", "FRANGO", "PEIXE", "SUÍNO", "SUINO", "SUÍNA", "SUINA",
    "BOVIN", "OVO", "ALMÔNDEGA", "ALMONDEGA", "LOMBO", "COXA",
    "SOBRECOXA", "FILÉ", "FILE", "HAMBÚRGUER", "HAMBURGUER",
    "LINGUIÇA", "LINGUICA", "PERNIL", "TILÁPIA", "TILAPIA",
    "PATINHO", "ACÉM", "ACEM", "CUPIM", "PICANHA", "XADREZ",
    "ESTROGONOFE", "STROGONOFF", "QUIBE", "KIBE", "TOFU",
    "PROTEÍNA DE SOJA", "PROTEINA DE SOJA", "GRÃO DE BICO",
    "GRAO DE BICO", "LENTILHA", "MOELA", "PANQUECA", "TORRESMO",
    "COSTELA",
]

EMOJI_CATEGORIA = {
    "arroz": "🍚",
    "feijao": "🫘",
    "proteina": "🍖",
    "salada": "🥗",
    "fruta": "🍎",
    "guarnicao": "🥘",
}


def categorizar(nome: str, descricao: str = "") -> str:
    """Classifica um prato (arroz, feijão, proteína, salada, fruta ou guarnição).

    Arroz/feijão/salada/fruta são identificados pelo nome do prato. Proteína é
    identificada pelo nome OU pela composição (campo "descricao"), porque nomes
    como "Guisado com Batata" só revelam que tem carne na composição
    ("Carne moída, batata, ..."), não no nome do prato.
    """
    nome_upper = nome.upper()
    if any(p in nome_upper for p in PALAVRAS_ARROZ):
        return "arroz"
    if any(p in nome_upper for p in PALAVRAS_FEIJAO):
        return "feijao"
    if any(p in nome_upper for p in PALAVRAS_SALADA):
        return "salada"
    if any(p in nome_upper for p in PALAVRAS_FRUTA):
        return "fruta"
    descricao_limpa = _RE_POSSIVEL_TRACO.sub("", descricao)
    texto_busca = f"{nome_upper} {descricao_limpa.upper()}"
    if any(p in texto_busca for p in PALAVRAS_PROTEINA):
        return "proteina"
    return "guarnicao"


def buscar_cardapio(restaurante_id: int, data_str: str) -> list[dict]:
    """Busca os itens do cardápio de um restaurante numa data (formato dd/mm/aaaa)."""
    params = {
        "txtData": data_str,
        "cmbRestaurante": restaurante_id,
        "page": 1,
        "rows": 100,
        "sidx": "id",
        "sord": "asc",
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(BASE_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json().get("rows", [])


def agrupar_por_refeicao(itens: list[dict]) -> dict[str, list[dict]]:
    grupos: dict[str, list[dict]] = {r: [] for r in REFEICOES}
    for item in itens:
        refeicao = item.get("refeicao", "").upper()
        if refeicao in grupos:
            grupos[refeicao].append(item)
    return grupos


def formatar_refeicao(nome_refeicao: str, itens: list[dict]) -> str:
    if not itens:
        return f"_Sem {nome_refeicao.lower()} cadastrada para esta data._"

    linhas = []
    for item in itens:
        categoria = categorizar(item["nome"], item.get("descricao", ""))
        emoji = EMOJI_CATEGORIA[categoria]
        nome = item["nome"].strip().title()
        if categoria == "proteina":
            linhas.append(f"{emoji} *{nome}*")
        else:
            linhas.append(f"{emoji} {nome}")
    return "\n".join(linhas)


def formatar_mensagem(data_str: str, dados_por_restaurante: dict[str, list[dict]]) -> str:
    data_fmt = datetime.strptime(data_str, "%d/%m/%Y")
    dias_semana = [
        "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
        "Sexta-feira", "Sábado", "Domingo",
    ]
    cabecalho = f"🍽️ *Cardápio RU - {dias_semana[data_fmt.weekday()]}, {data_str}*"

    blocos = [cabecalho]
    for nome_restaurante, itens in dados_por_restaurante.items():
        grupos = agrupar_por_refeicao(itens)
        blocos.append(f"\n📍 *{nome_restaurante}*")
        blocos.append(f"\n🍛 *Almoço*\n{formatar_refeicao('ALMOÇO', grupos['ALMOÇO'])}")
        blocos.append(f"\n🌙 *Janta*\n{formatar_refeicao('JANTA', grupos['JANTA'])}")

    blocos.append("\n_⚠️ Cardápio sujeito a alterações._")
    blocos.append("_Bot por: Cézar Veleda_")
    return "\n".join(blocos)


def gerar_cardapio_do_dia(data_str: str | None = None) -> str:
    """Busca o cardápio de todos os restaurantes configurados e devolve a mensagem pronta."""
    if data_str is None:
        data_str = date.today().strftime("%d/%m/%Y")

    dados_por_restaurante: dict[str, list[dict]] = {}
    for nome_restaurante, restaurante_id in RESTAURANTES.items():
        try:
            dados_por_restaurante[nome_restaurante] = buscar_cardapio(restaurante_id, data_str)
        except requests.RequestException as erro:
            dados_por_restaurante[nome_restaurante] = []
            print(f"[aviso] Falha ao buscar cardápio de {nome_restaurante}: {erro}", file=sys.stderr)

    return formatar_mensagem(data_str, dados_por_restaurante)


if __name__ == "__main__":
    data_arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(gerar_cardapio_do_dia(data_arg))
