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
from selenium.common.exceptions import TimeoutException
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

# A caixa de mensagem esvaziar é só a UI local do WhatsApp Web reagindo de
# forma otimista ao Enter — não prova que a mensagem chegou ao servidor.
# Confirmado em 2026-07-26: fechar o Chrome poucos segundos depois (como o
# código fazia antes) matava a conexão antes do envio real terminar,
# resultando em "erro ao enviar mensagem" mesmo com o script logando
# sucesso. Confirmação real é o ícone de status da mensagem (aria-label do
# span dentro de [data-testid="msg-meta"]): basta chegar em " Enviada " (✓,
# confirma que o servidor recebeu — é o suficiente pra descartar o "erro ao
# enviar"). "Entregue"/"Lida" ficam na lista só como cobertura defensiva
# (ex: se "Enviada" passar rápido demais e só flagrarmos o estado
# seguinte) — o código NÃO espera a mensagem ser lida antes de retornar, o
# que seria péssimo em grupo (lá o check azul só vem quando todo mundo lê,
# pode nunca acontecer).
STATUS_CONFIRMADOS = ("Enviada", "Entregue", "Lida")
STATUS_ERRO = ("erro", "falha", "não enviada", "nao enviada")
AGUARDO_STATUS_SEGUNDOS = 20

PASTA_PROJETO = Path(__file__).parent
PERFIL_CHROME = PASTA_PROJETO / "perfil_chrome"
SAIDA_DIR = PASTA_PROJETO / "saida"
LOG_FILE = PASTA_PROJETO / "log.txt"


def _log(mensagem: str) -> None:
    """Grava em log.txt com timestamp — a tarefa agendada roda sem console
    visível, então print() sozinho não deixa rastro nenhum se algo falhar.
    """
    linha = f"[{datetime.now().isoformat(timespec='seconds')}] {mensagem}"
    print(linha)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")


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


def _fechar_popup_novidades(driver: webdriver.Chrome) -> None:
    """Fecha modais que o WhatsApp Web às vezes mostra ao carregar (ex: "Veja
    os novos recursos" depois de uma atualização), que ficam sobrepostos à
    caixa de pesquisa e causam ElementClickInterceptedException (visto em
    2026-08-16, log.txt 08:00:17).
    """
    dialogs = driver.find_elements(By.CSS_SELECTOR, 'div[role="dialog"][aria-modal="true"]')
    if not dialogs:
        return
    for dialog in dialogs:
        fechado = False
        for seletor in ('[aria-label="Fechar"]', '[aria-label="Close"]', "button"):
            try:
                dialog.find_element(By.CSS_SELECTOR, seletor).click()
                fechado = True
                break
            except Exception:
                continue
        if not fechado:
            try:
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except Exception:
                pass
    time.sleep(1)


def _abrir_conversa(driver: webdriver.Chrome, termo_busca: str, filtro_titulo: str) -> None:
    _fechar_popup_novidades(driver)
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


def _caixa_mensagem_vazia(driver: webdriver.Chrome) -> bool:
    return driver.find_element(*CAIXA_MENSAGEM).text.strip() == ""


def _status_ultima_mensagem(driver: webdriver.Chrome) -> str | None:
    """Lê o aria-label do ícone de status (✓ Enviada / ✓✓ Entregue / Lida) da
    última mensagem na conversa aberta. None se ainda não houver nenhuma
    mensagem visível (ex: logo após o Enter).
    """
    return driver.execute_script(
        """
        const rows = document.querySelectorAll('div[role="row"]');
        if (!rows.length) return null;
        const status = rows[rows.length - 1]
            .querySelector('[data-testid="msg-meta"] span[aria-label]');
        return status ? status.getAttribute('aria-label') : null;
        """
    )


def _enviar_e_confirmar(driver: webdriver.Chrome, tentativas: int = 2) -> None:
    """Aperta Enter e confirma a entrega de verdade pelo ícone de status da
    mensagem, não só a caixa de texto esvaziar.

    Dois problemas descobertos em 2026-07-26, nessa ordem: (1) um Enter logo
    após colar conteúdo com emoji/quebras de linha às vezes é ignorado pela
    caixa — resolvido esperando ela esvaziar; (2) a caixa esvaziar é só
    reação otimista da UI local, não prova que a mensagem chegou ao
    servidor — fechar o Chrome logo depois disso resultava em "erro ao
    enviar mensagem" no WhatsApp mesmo com o script logando sucesso.
    Resolvido esperando o ícone de status confirmar (" Enviada "/" Entregue
    "/" Lida ") antes de retornar.
    """
    for tentativa in range(1, tentativas + 1):
        driver.find_element(*CAIXA_MENSAGEM).send_keys(Keys.ENTER)
        try:
            WebDriverWait(driver, 10).until(lambda d: _caixa_mensagem_vazia(d))
        except TimeoutException:
            if tentativa == tentativas:
                raise RuntimeError(
                    "Caixa de mensagem continua com texto após Enter "
                    f"({tentativa} tentativa(s)) — o envio não foi confirmado."
                )
            continue

        def _status_resolvido(d: webdriver.Chrome) -> bool:
            status = _status_ultima_mensagem(d)
            if not status:
                return False
            status_lower = status.lower()
            return any(p.lower() in status_lower for p in STATUS_CONFIRMADOS) or any(
                p in status_lower for p in STATUS_ERRO
            )

        try:
            WebDriverWait(driver, AGUARDO_STATUS_SEGUNDOS).until(_status_resolvido)
        except TimeoutException:
            pass

        status = _status_ultima_mensagem(driver)
        if status and any(p in status for p in STATUS_CONFIRMADOS):
            return
        if tentativa == tentativas:
            raise RuntimeError(
                "Mensagem não confirmada como entregue pelo WhatsApp "
                f"(status do ícone: {status!r})."
            )


def preparar_no_grupo(
    termo_busca: str,
    filtro_titulo: str,
    mensagem: str,
    enviar_automaticamente: bool = True,
    fechar_apos_enviar: bool = True,
) -> None:
    driver = _abrir_whatsapp_web()
    _aguardar_login(driver)
    _abrir_conversa(driver, termo_busca, filtro_titulo)
    _colar_mensagem(driver, mensagem)

    if enviar_automaticamente:
        _enviar_e_confirmar(driver)
        _log(f"Mensagem enviada com sucesso para o grupo '{termo_busca}'.")
        if fechar_apos_enviar:
            driver.quit()
        else:
            print("Chrome fica aberto de propósito — confira a mensagem no grupo.")
    else:
        _log(f"Mensagem colada (modo manual) no grupo '{termo_busca}', aguardando confirmação do usuário.")
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
    # --diagnostico manda enviar normalmente mas não fecha o Chrome no final
    # (nem em caso de sucesso nem de erro), pra investigar visualmente algo
    # que deu errado no WhatsApp Web (ex: ícone de falha ao lado da mensagem).
    enviar_automaticamente = "--manual" not in sys.argv
    rodando_agendado = "--agendado" in sys.argv
    fechar_apos_enviar = "--diagnostico" not in sys.argv
    args = [
        a
        for a in sys.argv[1:]
        if a not in ("--manual", "--agendado", "--diagnostico")
    ]

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

    _log(f"Iniciando envio (destino='{termo_busca}', agendado={rodando_agendado})...")
    try:
        mensagem = _obter_mensagem_do_dia(data_arg)
        preparar_no_grupo(
            termo_busca,
            filtro_titulo,
            mensagem,
            enviar_automaticamente,
            fechar_apos_enviar,
        )
    except Exception as erro:
        _log(f"[ERRO] {type(erro).__name__}: {erro}")
        if not rodando_agendado:
            _pausar_para_fechar()
        sys.exit(1)

    # Se rodou com clique duplo, sem isso a janela fecha rápido demais pra ler.
    if not rodando_agendado and enviar_automaticamente:
        _pausar_para_fechar()


if __name__ == "__main__":
    main()
