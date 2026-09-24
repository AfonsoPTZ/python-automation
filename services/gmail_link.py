# Monta um link "Redigir e-mail" do Gmail já preenchido (destinatário, assunto
# e corpo em texto simples), para o auditor só revisar e clicar em Enviar.
# Evita depender de configurar SMTP/senha de app: quem manda é o próprio
# auditor, pela conta dele, com um clique.
#
# O e-mail é sempre por não conformidade (1 NC = 1 e-mail), não um resumo de
# todas as NCs da auditoria: um corpo com várias NCs concatenadas facilmente
# passa do limite de tamanho de URL que o Gmail aceita e o link volta
# "Bad Request" no navegador.
from urllib.parse import urlencode

_COMPOSE_URL = "https://mail.google.com/mail/?view=cm&fs=1"


def montar_link_gmail(destinatarios, assunto, corpo_texto):
    parametros = {
        "to": ", ".join(destinatarios),
        "su": assunto,
        "body": corpo_texto,
    }
    return f"{_COMPOSE_URL}&{urlencode(parametros)}"


# Texto simples (pronto, sem IA) do e-mail de notificação de uma única NC ao grupo.
def texto_notificacao_nc(projeto, nc, prazo_limite):
    linhas = [
        "Olá,",
        "",
        f'A auditoria de qualidade do projeto "{projeto["nome"]}" identificou a '
        "seguinte não conformidade que precisa ser corrigida:",
        "",
        "Não conformidade:",
        *([f"Item do checklist: {nc['item_checklist']}"] if nc["item_checklist"] else []),
        f"Título: {nc['titulo']}",
        f"Descrição: {nc['descricao_erro']}",
    ]
    if nc["evidencia"]:
        linhas.append(f"Evidência: {nc['evidencia']}")
    if nc["impacto"]:
        linhas.append(f"Impacto: {nc['impacto']}")
    if nc["acao_corretiva"]:
        linhas.append(f"Ação corretiva esperada: {nc['acao_corretiva']}")
    linhas.append(f"Prazo limite para envio da correção: {prazo_limite}")

    linhas += [
        "",
        "O não cumprimento do prazo acarretará o escalonamento ao responsável "
        f'({projeto["responsavel_superior_email"]}).',
        "",
        "Atenciosamente,",
        "Auditoria de Qualidade",
    ]
    return "\n".join(linhas)


# Texto simples (pronto, sem IA) do e-mail de escalonamento de uma única NC ao
# superior/orientador. Só existe um jeito de chegar aqui: o prazo de correção
# já venceu (o botão de escalonar só aparece depois disso, manual ou
# automático via services/scheduler.py) — por isso o motivo é sempre esse.
def texto_escalonamento_nc(projeto, nc):
    linhas = [
        "Olá,",
        "",
        "Houve um atraso na correção de uma não conformidade identificada pela "
        f'auditoria de qualidade do projeto "{projeto["nome"]}". O prazo definido '
        "para a correção venceu sem que a versão corrigida fosse entregue, e por "
        "isso estou escalonando esta pendência para o seu acompanhamento.",
        "",
        "Correção solicitada:",
        *([f"Item do checklist: {nc['item_checklist']}"] if nc["item_checklist"] else []),
        f"Título: {nc['titulo']}",
        f"Descrição: {nc['descricao_erro']}",
    ]
    if nc["notificado_em"]:
        linhas.append(f"Notificada ao grupo em: {nc['notificado_em']}")
    if nc["prazo_limite"]:
        linhas.append(f"Prazo definido: {nc['prazo_limite']}")
    if nc["impacto"]:
        linhas.append(f"Impacto: {nc['impacto']}")
    if nc["acao_corretiva"]:
        linhas.append(f"Ação corretiva esperada: {nc['acao_corretiva']}")

    linhas += [
        "",
        "Peço uma avaliação sobre o que pode ser feito para corrigir esta "
        "pendência, e o seu parecer final sobre o caso.",
        "",
        "Atenciosamente,",
        "Auditoria de Qualidade",
    ]
    return "\n".join(linhas)
