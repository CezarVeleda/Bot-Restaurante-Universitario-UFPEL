"""Lê o log.txt do dia e mostra uma notificação nativa do Windows (balão) com
o resultado do envio automático do cardápio. Pensado pra rodar como uma
tarefa agendada alguns minutos depois da CardapioRU (08:00), pra avisar o
usuário sem depender de ninguém abrir o Claude Code pra checar.
"""
import os
import subprocess
from datetime import date
from pathlib import Path

LOG_FILE = Path(__file__).parent / "log.txt"
GRUPO = "Cardápio RU UFPEL"


def _linhas_de_hoje() -> list[str]:
    if not LOG_FILE.exists():
        return []
    hoje = date.today().isoformat()
    linhas = LOG_FILE.read_text(encoding="utf-8").splitlines()
    return [linha for linha in linhas if linha.startswith(f"[{hoje}")]


def _avaliar(linhas: list[str]) -> tuple[bool, str]:
    if not linhas:
        return False, "Nenhuma linha de log encontrada pra hoje — a tarefa CardapioRU rodou?"

    sucesso_idx = None
    for i, linha in enumerate(linhas):
        if "enviada com sucesso" in linha and GRUPO in linha:
            sucesso_idx = i

    if sucesso_idx is None:
        erro = next((linha for linha in linhas if "[ERRO]" in linha), None)
        return False, erro or "Sem confirmação de sucesso no log de hoje."

    erro_depois = next(
        (linha for linha in linhas[sucesso_idx + 1 :] if "[ERRO]" in linha), None
    )
    if erro_depois:
        return False, erro_depois

    return True, linhas[sucesso_idx]


def _notificar(titulo: str, mensagem: str) -> None:
    env = os.environ.copy()
    env["RU_TITULO"] = titulo[:60]
    env["RU_MSG"] = mensagem[:200]

    script_ps = (
        "Add-Type -AssemblyName System.Windows.Forms\n"
        "$n = New-Object System.Windows.Forms.NotifyIcon\n"
        "$n.Icon = [System.Drawing.SystemIcons]::Information\n"
        "$n.Visible = $true\n"
        "$n.ShowBalloonTip(15000, $env:RU_TITULO, $env:RU_MSG, "
        "[System.Windows.Forms.ToolTipIcon]::Info)\n"
        "Start-Sleep -Seconds 16\n"
        "$n.Dispose()\n"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script_ps],
        env=env,
        check=False,
    )


def main() -> None:
    ok, detalhe = _avaliar(_linhas_de_hoje())
    if ok:
        _notificar("Cardápio RU: enviado", detalhe)
    else:
        _notificar("Cardápio RU: FALHOU", detalhe)


if __name__ == "__main__":
    main()
