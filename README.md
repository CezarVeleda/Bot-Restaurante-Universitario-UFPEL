# Cardápio RU (UFPel) → WhatsApp

Bot que busca o cardápio do dia do Restaurante Universitário da UFPel
(sistema Cobalto) e posta automaticamente num grupo do WhatsApp, todo dia
às 08:00, sem intervenção manual.

## Como funciona

1. **`ru_cardapio.py`** — busca o cardápio do dia no Cobalto e formata a
   mensagem (com emojis, categorizando arroz/feijão/proteína/salada/fruta).
   Busca os restaurantes **Unidade Centro** e **Anglo**.
   - Pra hoje, usa o endpoint do dashboard do Cobalto (o mesmo que o widget
     "Cardápio do Dia" da home usa). Se esse endpoint falhar de verdade
     (erro de rede ou resposta com `"error"`), cai pro endpoint antigo do
     portal público como segunda tentativa.
   - Pra uma data específica (não hoje), usa só o endpoint antigo do portal
     — que está instável/quebrado do lado da UFPel desde 25/10/2026.
2. **`main.py`** — chama o `ru_cardapio.py`, salva o resultado em
   `saida/cardapio_AAAA-MM-DD.txt` e imprime na tela. Não envia nada, só
   gera o texto.
3. **`enviar_whatsapp.py`** — abre o WhatsApp Web (via Chrome controlado por
   Selenium, com sessão salva em `perfil_chrome/`), acha o grupo certo, cola
   a mensagem e confirma o envio pelo ícone de status (✓ Enviada).
4. **`checar_e_notificar.py`** — lê o `log.txt` do dia e mostra uma
   notificação do Windows avisando se o envio automático deu certo ou não.

## Instalação

```
pip install -r requirements.txt
```

Na primeira vez que rodar `enviar_whatsapp.py`, uma janela do Chrome abre
pedindo pra escanear o QR Code do WhatsApp. Depois disso a sessão fica
salva em `perfil_chrome/` e não precisa escanear de novo.

## Uso

```
python main.py                        # só gera o cardápio de hoje (não envia)
python main.py 17/07/2026              # gera o cardápio de uma data específica

python enviar_whatsapp.py              # gera (se precisar) e envia pro grupo real
python enviar_whatsapp.py --manual     # só cola a mensagem, você aperta Enviar
python enviar_whatsapp.py --teste      # testa o fluxo inteiro no grupo "Só eu"
python enviar_whatsapp.py --destino "Nome do Grupo"   # testa em qualquer grupo/contato
python enviar_whatsapp.py --diagnostico   # envia normal mas não fecha o Chrome no final
python enviar_whatsapp.py --retry-automatico   # se falhar, agenda 1 nova tentativa em 5 min
```

## Automação (Task Scheduler + boot automático)

- Tarefa `CardapioRU` no Agendador de Tarefas do Windows roda
  `enviar_whatsapp.py --agendado` todo dia às 08:00.
- A máquina liga sozinha às 07:30 via RTC wake da BIOS, faz autologon numa
  conta dedicada (`Bots`), e só então a tarefa dispara. Detalhes de como
  isso é configurado (BIOS, dual-boot, RTC) estão em
  `C:\Shared\projeto_ru_boot_constraints.md` — **ler antes de mexer em
  qualquer coisa relacionada a boot/GRUB/dual-boot**, pra não quebrar o
  envio automático.
- `suspender_se_ocioso.ps1` suspende o PC depois do envio, pra não ficar
  ligado o dia todo à toa.

## Limitações conhecidas

- Buscar o cardápio de uma data **diferente de hoje** (`python main.py
  dd/mm/aaaa`) depende do endpoint antigo do portal do Cobalto, que está
  fora do ar desde 25/10/2026 (bug do lado da UFPel, não nosso). Enquanto
  não for consertado, essa busca volta vazia.
- O grupo de WhatsApp do bot só é usado pra postar a mensagem automática —
  não há suporte a comandos ou perguntas nele.

## Estrutura

```
main.py               ponto de entrada: gera o texto do cardápio
ru_cardapio.py         busca e formata o cardápio (lógica principal)
enviar_whatsapp.py     automação do WhatsApp Web via Selenium
checar_e_notificar.py  notificação de resultado do envio diário
suspender_se_ocioso.ps1  suspende o PC após o envio
tests/                 testes automatizados (pytest)
saida/                  cardápios gerados por dia (git-ignored)
perfil_chrome/          sessão do WhatsApp Web (git-ignored, nunca versionar)
log.txt                 log de execução (git-ignored)
```
