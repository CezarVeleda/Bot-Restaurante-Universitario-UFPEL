"""Ponto de entrada do bot: gera o cardápio do dia e salva num arquivo de texto
pronto para ser colado no grupo do WhatsApp da faculdade.

Uso:
    python main.py                 # cardápio de hoje
    python main.py 17/07/2026      # cardápio de uma data específica
"""
import sys
from datetime import date
from pathlib import Path

from ru_cardapio import gerar_cardapio_do_dia

SAIDA_DIR = Path(__file__).parent / "saida"


def main() -> None:
    # O console do Windows costuma usar cp1252, que não suporta os emojis da mensagem.
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    data_arg = sys.argv[1] if len(sys.argv) > 1 else None
    mensagem = gerar_cardapio_do_dia(data_arg)

    SAIDA_DIR.mkdir(exist_ok=True)
    arquivo_saida = SAIDA_DIR / f"cardapio_{date.today().isoformat()}.txt"
    arquivo_saida.write_text(mensagem, encoding="utf-8")

    print(mensagem)
    print(f"\n[Salvo em: {arquivo_saida}]")


if __name__ == "__main__":
    main()
