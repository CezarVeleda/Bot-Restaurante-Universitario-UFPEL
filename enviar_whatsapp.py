"""Abre o WhatsApp Web, localiza o grupo do RU, cola o cardápio do dia e envia.

Por padrão o envio é automático (cola e aperta Enter sozinho). Use --manual
para só colar a mensagem e deixar você conferir e apertar Enviar.

Na primeira execução, uma janela do Chrome vai abrir pedindo para escanear o
QR Code com o WhatsApp do celular. Depois disso a sessão fica salva na pasta
"perfil_chrome" e não precisa escanear de novo.

Uso:
    python enviar_whatsapp.py                # gera (se preciso) e envia o cardápio de hoje
    python enviar_whatsapp.py --manual       # só cola, você aperta Enviar
    python enviar_whatsapp.py 17/07/2026     # usa o cardápio de uma data específica
    python enviar_whatsapp.py --teste        # testa o fluxo inteiro no grupo "Só eu"
    python enviar_whatsapp.py --destino "Nome do Grupo"  # testa em qualquer grupo/contato
"""
from __future__ import annotations

import sys
import time
from datetime import date, datetime
from pathlib import Path

import pyperclip
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ru_cardapio import gerar_cardapio_do_dia

# Nome do grupo criado especificamente para o bot postar o cardápio do dia.
TERMO_BUSCA_GRUPO = "Cardápio RU UFPEL"
FILTRO_TITULO_GRUPO = "Cardápio RU UFPEL"

# Grupo próprio (só o usuário) usado como destino de teste com --teste, pra
# validar o fluxo de busca/colar/enviar sem incomodar o grupo real.
GRUPO_TESTE = "Só eu"

PASTA_PROJETO = Path(__file__).parent
PERFIL_CHROME = PASTA_PROJETO / "perfil_chrome"
SAIDA_DIR = PASTA_PROJETO / "saida"

CAIXA_PESQUISA = (
    By.CSS_SELECTOR,
    'input[aria-label="Pesquisar ou começar uma nova conversa"]',
)
CAIXA_MENSAGEM = (
    By.CSS_SELECTOR,
    'div[data-testid="conversation-compose-box-input"]',
)


def _obter_mensagem_do_dia(data_str: str | None) -> str:
    """Reaproveita o .txt já gerado por main.py se existir; senão busca e salva na hora."""
    data_arquivo = (
        datetime.strptime(data_str, "%d/%m/%Y").date() if data_str else date.today()
    )
    arquivo = SAIDA_DIR / f"cardapio_{data_arquivo.isoformat()}.txt"
    if arquivo.exists():
        return arquivo.read_text(encoding="utf-8")

    mensagem = gerar_cardapio_do_dia(data_str)
    SAIDA_DIR.mkdir(exist_ok=True)
    arquivo.write_text(mensagem, encoding="utf-8")
    return mensagem


def _abrir_whatsapp_web() -> webdriver.Chrome:
    opcoes = Options()
    opcoes.add_argument(f"--user-data-dir={PERFIL_CHROME}")
    # Sem isso, o Chrome fecha junto quando o script termina, mesmo sem
    # chamarmos driver.quit() — necessário pro modo --manual, onde o
    # navegador precisa continuar aberto depois que o script encerra.
    opcoes.add_experimental_option("detach", True)
    driver = webdriver.Chrome(options=opcoes)
    driver.get("https://web.whatsapp.com")
    return driver


def _aguardar_login(driver: webdriver.Chrome, timeout: int = 120) -> None:
    print("Aguardando WhatsApp Web carregar (escaneie o QR Code se for a primeira vez)...")
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located(CAIXA_PESQUISA))
    print("WhatsApp Web carregado.")


def _abrir_conversa(driver: webdriver.Chrome, termo_busca: str, filtro_titulo: str) -> None:
    caixa_pesquisa = driver.find_element(*CAIXA_PESQUISA)
    caixa_pesquisa.click()
    caixa_pesquisa.send_keys(termo_busca)
    time.sleep(2)

    # Título exato (não "contains") pra não arriscar clicar num contato ou
    # grupo diferente cujo nome só contenha esse texto como substring.
    resultado = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, f'//span[@title="{filtro_titulo}"]'))
    )
    resultado.click()
    time.sleep(1)
    caixa_pesquisa.send_keys(Keys.ESCAPE)


def _colar_mensagem(driver: webdriver.Chrome, mensagem: str) -> None:
    pyperclip.copy(mensagem)
    caixa_mensagem = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located(CAIXA_MENSAGEM)
    )
    caixa_mensagem.click()
    caixa_mensagem.send_keys(Keys.CONTROL, "v")
    time.sleep(1)


def preparar_no_grupo(
    termo_busca: str,
    filtro_titulo: str,
    mensagem: str,
    enviar_automaticamente: bool = True,
) -> None:
    driver = _abrir_whatsapp_web()
    _aguardar_login(driver)
    _abrir_conversa(driver, termo_busca, filtro_titulo)
    _colar_mensagem(driver, mensagem)

    if enviar_automaticamente:
        caixa_mensagem = driver.find_element(*CAIXA_MENSAGEM)
        caixa_mensagem.send_keys(Keys.ENTER)
        time.sleep(2)
        print(f"Mensagem enviada para o grupo '{termo_busca}'.")
        driver.quit()
    else:
        print(f"\nMensagem colada no grupo '{termo_busca}'.")
        print("O navegador vai continuar aberto: confira o texto e aperte Enviar")
        print("direto no WhatsApp Web, quando quiser. Pode fechar esta janela.")


def _pausar_para_fechar() -> None:
    """Pausa esperando Enter (clique duplo/terminal interativo). Sem terminal
    conectado (ex: rodando em background) input() levanta EOFError — nesse
    caso não há ninguém pra apertar Enter mesmo, então só ignoramos.
    """
    try:
        input("\nPressione Enter para fechar esta janela...")
    except EOFError:
        pass


def _extrair_valor_de_flag(args: list[str], nome_flag: str) -> tuple[str | None, list[str]]:
    """Remove `nome_flag valor` de args (se presente) e devolve (valor, args_restantes)."""
    if nome_flag not in args:
        return None, args
    idx = args.index(nome_flag)
    valor = args[idx + 1] if idx + 1 < len(args) else None
    restantes = args[:idx] + args[idx + 2 :]
    return valor, restantes


def main() -> None:
    if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    # --manual desliga o envio automático e volta ao modo "só colar, eu envio".
    # --agendado é usado pela tarefa do Task Scheduler: roda sem parar no final
    # esperando Enter, já que não tem ninguém pra apertar nada.
    enviar_automaticamente = "--manual" not in sys.argv
    rodando_agendado = "--agendado" in sys.argv
    args = [a for a in sys.argv[1:] if a not in ("--manual", "--agendado")]

    # --destino "Nome" aponta o bot pra qualquer grupo/contato específico;
    # --teste é um atalho pro grupo "Só eu", pra validar o fluxo sem mexer
    # no grupo real da turma.
    destino, args = _extrair_valor_de_flag(args, "--destino")
    if "--teste" in args:
        args.remove("--teste")
        destino = destino or GRUPO_TESTE

    termo_busca = destino or TERMO_BUSCA_GRUPO
    filtro_titulo = destino or FILTRO_TITULO_GRUPO
    data_arg = args[0] if args else None

    try:
        mensagem = _obter_mensagem_do_dia(data_arg)
        preparar_no_grupo(termo_busca, filtro_titulo, mensagem, enviar_automaticamente)
    except Exception as erro:
        print(f"\n[ERRO] {type(erro).__name__}: {erro}")
        if not rodando_agendado:
            _pausar_para_fechar()
        return

    # Se rodou com clique duplo, sem isso a janela fecha rápido demais pra ler.
    if not rodando_agendado and enviar_automaticamente:
        _pausar_para_fechar()


if __name__ == "__main__":
    main()
