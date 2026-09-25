// JS do Painel do Auditor: contador regressivo de prazo, menu mobile,
// confirmações destrutivas, envio de formulário sem recarregar a página
// (mantém a posição de rolagem), toasts de feedback e o e-mail de
// notificação/escalonamento de NC montado e aberto no mesmo clique.
//
// Praticamente tudo usa delegação de evento (um listener em `document`),
// porque o conteúdo de #conteudo-principal é trocado via AJAX depois de
// qualquer ação (ver `submeterAjax`) — um listener preso a um elemento
// específico sumiria junto com ele; delegado, continua funcionando no
// conteúdo novo sem precisar religar nada.

// ===================== Contador regressivo de prazo =====================
function formatarRestante(ms) {
  const totalSegundos = Math.max(0, Math.floor(ms / 1000));
  const dias = Math.floor(totalSegundos / 86400);
  const horas = Math.floor((totalSegundos % 86400) / 3600);
  const minutos = Math.floor((totalSegundos % 3600) / 60);
  const segundos = totalSegundos % 60;
  if (dias > 0) return `${dias}d ${horas}h ${minutos}m`;
  if (horas > 0) return `${horas}h ${minutos}m ${segundos}s`;
  return `${minutos}m ${segundos}s`;
}

function atualizarContadores() {
  document.querySelectorAll("[data-prazo]").forEach((elemento) => {
    const prazo = new Date(elemento.dataset.prazo).getTime();
    const diferenca = prazo - Date.now();
    const doze_horas_ms = 12 * 60 * 60 * 1000;

    elemento.classList.remove("countdown-ok", "countdown-alerta", "countdown-vencido");
    if (diferenca <= 0) {
      elemento.textContent = "Prazo vencido";
      elemento.classList.add("countdown-vencido");
    } else if (diferenca <= doze_horas_ms) {
      elemento.textContent = `Vence em ${formatarRestante(diferenca)}`;
      elemento.classList.add("countdown-alerta");
    } else {
      elemento.textContent = `Vence em ${formatarRestante(diferenca)}`;
      elemento.classList.add("countdown-ok");
    }

    // Quando o prazo de uma NC vence, revela o botão de escalonamento dela
    // sozinho, sem precisar recarregar a página.
    const alvoId = elemento.dataset.escalonarAlvo;
    if (alvoId) {
      const botaoEscalonar = document.getElementById(alvoId);
      if (botaoEscalonar) botaoEscalonar.classList.toggle("oculto", diferenca > 0);
    }
  });
}
atualizarContadores();
setInterval(atualizarContadores, 1000);

// ===================== Toasts (mensagens flutuantes) =====================
// Some sozinho depois de um tempo, sem bloquear o usuário nem empurrar a
// página — fica fixo no canto (ver .flash-pilha em style.css).
function armarToasts(escopo) {
  (escopo || document).querySelectorAll(".flash:not([data-armado])").forEach((flash) => {
    flash.setAttribute("data-armado", "true");
    setTimeout(() => {
      flash.classList.add("flash-saindo");
      setTimeout(() => flash.remove(), 200);
    }, 5000);
  });
}
armarToasts();

// Cria e exibe um toast programaticamente (sem precisar de um flash do servidor).
// Útil para feedbacks gerados 100% no cliente (ex.: popup bloqueado).
function _mostrarToast(mensagem, categoria = "ok") {
  let pilha = document.querySelector(".flash-pilha");
  if (!pilha) {
    pilha = document.createElement("div");
    pilha.className = "flash-pilha";
    pilha.setAttribute("role", "status");
    pilha.setAttribute("aria-live", "polite");
    document.body.appendChild(pilha);
  }
  const flash = document.createElement("div");
  flash.className = `flash flash-${categoria}`;
  flash.setAttribute("data-armado", "true");
  flash.innerHTML = `<span>${mensagem}</span><button type="button" class="flash-fechar" aria-label="Fechar aviso">×</button>`;
  pilha.appendChild(flash);
  armarToasts(pilha);
}

// ===================== E-mail de correção/escalonamento no cliente =====================
// Monta e abre o link "Redigir" do Gmail no mesmo clique que salva o prazo —
// em vez de "definir prazo" -> recarregar -> procurar o link -> clicar de
// novo. Precisa ser síncrono (antes de qualquer await) pro navegador não
// bloquear como pop-up.
function montarLinkGmail(destinatarios, assunto, corpo) {
  const parametros = new URLSearchParams({ to: destinatarios.join(", "), su: assunto, body: corpo });
  return `https://mail.google.com/mail/?view=cm&fs=1&${parametros.toString()}`;
}

function dadosDaNc(form) {
  const card = form.closest("[data-nc-titulo]");
  if (!card) return null;
  let participantes = [];
  try {
    participantes = JSON.parse(card.dataset.participantes || "[]");
  } catch (erro) {
    participantes = [];
  }
  return {
    titulo: card.dataset.ncTitulo,
    descricao: card.dataset.ncDescricao,
    evidencia: card.dataset.ncEvidencia,
    impacto: card.dataset.ncImpacto,
    acao: card.dataset.ncAcao,
    prazoLimite: card.dataset.ncPrazoLimite,
    notificadoEm: card.dataset.ncNotificadoEm,
    projetoNome: card.dataset.projetoNome,
    responsavelEmail: card.dataset.responsavelEmail,
    participantes, // [{ nome, email }, ...]
  };
}

function _escapeHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto == null ? "" : String(texto);
  return div.innerHTML;
}

function abrirModalEmailEquipe(botao) {
  const card = botao.closest("[data-nc-titulo]");
  if (!card) return;
  const dados = dadosDaNc(botao);
  if (!dados || !dados.participantes.length) return;

  const reabertura = botao.dataset.emailModo === "reabertura";
  const checkboxesHtml = dados.participantes.map((p, indice) => `
    <label class="chk-destinatario">
      <input type="checkbox" class="modal-destinatario" value="${_escapeHtml(p.email)}" checked>
      ${_escapeHtml(p.nome)} <span class="chk-destinatario-email">(${_escapeHtml(p.email)})</span>
    </label>
  `).join("");

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.innerHTML = `
    <div class="modal-caixa modal-caixa--largo">
      <p class="modal-titulo">${reabertura ? "Nova solicitação de correção" : "Enviar e-mail à equipe"}</p>
      <label class="modal-label">Enviar para</label>
      <div class="modal-destinatarios">${checkboxesHtml}</div>
      <p class="modal-erro-destinatarios oculto">Selecione ao menos um integrante.</p>
      <p class="modal-mensagem">Para qual data você quer que ocorra a nova atualização?</p>
      <label class="modal-label" for="modal-data">Data e horário da nova atualização</label>
      <input id="modal-data" class="modal-campo" type="datetime-local" required>
      ${reabertura ? `
        <label class="modal-label" for="modal-orientacao">Orientação do superior</label>
        <textarea id="modal-orientacao" class="modal-campo" rows="3" placeholder="O que o superior orientou a equipe a fazer?"></textarea>
      ` : ""}
      <div class="modal-acoes">
        <button type="button" class="btn-secundario" data-modal-cancelar>Cancelar</button>
        <button type="button" class="btn btn-email" data-modal-confirmar>✉ Enviar e-mail</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const fechar = () => {
    overlay.classList.add("modal-saindo");
    setTimeout(() => overlay.remove(), 150);
  };
  overlay.querySelector("[data-modal-cancelar]").addEventListener("click", fechar);
  overlay.addEventListener("click", (evento) => {
    if (evento.target === overlay) fechar();
  });
  overlay.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") fechar();
  });
  overlay.querySelector("#modal-data").focus();

  overlay.querySelector("[data-modal-confirmar]").addEventListener("click", async () => {
    const selecionados = Array.from(overlay.querySelectorAll(".modal-destinatario:checked")).map((el) => el.value);
    if (!selecionados.length) {
      overlay.querySelector(".modal-erro-destinatarios").classList.remove("oculto");
      return;
    }
    const dataEscolhida = overlay.querySelector("#modal-data").value;
    if (!dataEscolhida) return;
    const prazo = dataEscolhida.replace("T", " ") + ":00";
    const orientacao = overlay.querySelector("#modal-orientacao")?.value.trim() || "";
    const linhas = [
      "Olá,", "",
      reabertura
        ? `Após o escalonamento da não conformidade do projeto "${dados.projetoNome}", foi solicitada uma nova correção pela equipe.`
        : `A auditoria de qualidade do projeto "${dados.projetoNome}" identificou a seguinte não conformidade que precisa ser corrigida:`,
      "", "Não conformidade:", `Título: ${dados.titulo}`, `Descrição: ${dados.descricao}`,
    ];
    if (dados.evidencia) linhas.push(`Evidência: ${dados.evidencia}`);
    if (dados.impacto) linhas.push(`Impacto: ${dados.impacto}`);
    if (dados.acao) linhas.push(`Ação corretiva esperada: ${dados.acao}`);
    if (reabertura && orientacao) linhas.push("", `Orientação do superior: ${orientacao}`);
    linhas.push(
      "", `Novo prazo limite para envio da correção: ${prazo}`,
      "O não cumprimento deste prazo poderá gerar novo escalonamento ao responsável.",
      "", "Atenciosamente,", "Auditoria de Qualidade",
    );
    const assunto = `[Auditoria de Qualidade] ${reabertura ? "Nova solicitação de correção" : "Não Conformidade encontrada"} - ${dados.projetoNome} - ${dados.titulo}`;
    const janela = window.open("about:blank", "_blank");
    if (!janela) {
      fechar();
      _mostrarToast("Permita popups para abrir o e-mail no Gmail.", "erro");
      return;
    }
    const corpo = new URLSearchParams({ prazo_customizado: dataEscolhida });
    selecionados.forEach((email) => corpo.append("participante_email", email));
    try {
      const resposta = await fetch(botao.dataset.notificarUrl, { method: "POST", body: corpo });
      if (!resposta.ok) throw new Error("Falha ao salvar o novo prazo");
      janela.location.href = montarLinkGmail(selecionados, assunto, linhas.join("\n"));
      fechar();
      window.location.reload();
    } catch (erro) {
      janela.close();
      fechar();
      _mostrarToast("Não foi possível salvar o novo prazo. Tente novamente.", "erro");
    }
  });
}

// Espelha services/gmail_link.py:texto_escalonamento_nc. Só existe um
// caminho até aqui (botão só aparece com o prazo já vencido), então o motivo
// é sempre o mesmo.
function abrirEmailEscalonamento(form) {
  const dados = dadosDaNc(form);
  if (!dados) return;

  const linhas = [
    "Olá,", "",
    "Houve um atraso na correção de uma não conformidade identificada pela auditoria "
      + `de qualidade do projeto "${dados.projetoNome}". O prazo definido para a correção `
      + "venceu sem que a versão corrigida fosse entregue, e por isso estou escalonando "
      + "esta pendência para o seu acompanhamento.",
    "",
    "Correção solicitada:",
    `Título: ${dados.titulo}`,
    `Descrição: ${dados.descricao}`,
  ];
  if (dados.notificadoEm) linhas.push(`Notificada ao grupo em: ${dados.notificadoEm}`);
  if (dados.prazoLimite) linhas.push(`Prazo definido: ${dados.prazoLimite}`);
  if (dados.impacto) linhas.push(`Impacto: ${dados.impacto}`);
  if (dados.acao) linhas.push(`Ação corretiva esperada: ${dados.acao}`);
  linhas.push(
    "",
    "Peço uma avaliação sobre o que pode ser feito para corrigir esta pendência, "
      + "e o seu parecer final sobre o caso.",
    "", "Atenciosamente,", "Auditoria de Qualidade",
  );

  const assunto = `[Auditoria de Qualidade] Escalonamento - ${dados.projetoNome} - ${dados.titulo}`;
  const janela = window.open(montarLinkGmail([dados.responsavelEmail], assunto, linhas.join("\n")), "_blank", "noopener");
  if (!janela) {
    _mostrarToast(
      "O rascunho de e-mail não pôde ser aberto automaticamente (popup bloqueado). " +
      "Permita popups para este site e clique no link de e-mail que aparecerá na NC.",
      "erro"
    );
  }
}

// ===================== Modal de criação de checklist =====================
// Cada item vira um critério avaliado pela IA (código + categoria + descrição,
// igual à estrutura de auditoria/criterios.py) — renderizado como um
// cartãozinho numerado em vez de três campos soltos, pra ficar claro o que é
// cada coisa.
function _novoItemChecklistHtml(numero) {
  return `
    <div class="checklist-item-card">
      <div class="checklist-item-cabecalho">
        <span class="checklist-item-numero">${numero}</span>
        <button type="button" class="btn-remover-linha" aria-label="Remover este item" title="Remover">×</button>
      </div>
      <div class="checklist-item-campos">
        <div>
          <label class="modal-label">Código</label>
          <input type="text" name="item_codigo" class="modal-campo" placeholder="Opcional, ex.: C1">
        </div>
        <div>
          <label class="modal-label">Categoria</label>
          <input type="text" name="item_categoria" class="modal-campo" placeholder="Opcional, ex.: Introdução">
        </div>
        <div>
          <label class="modal-label">Descrição do critério</label>
          <textarea name="item_descricao" class="modal-campo" rows="2" placeholder="O que este item verifica no documento?"></textarea>
        </div>
      </div>
    </div>`;
}

function _renumerarItensChecklist(lista) {
  lista.querySelectorAll(".checklist-item-card").forEach((cartao, indice) => {
    cartao.querySelector(".checklist-item-numero").textContent = indice + 1;
  });
}

function abrirModalNovoChecklist(botao) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.innerHTML = `
    <div class="modal-caixa modal-caixa--largo modal-caixa--checklist">
      <p class="modal-titulo">Criar checklist</p>
      <form id="form-novo-checklist" action="${botao.dataset.criarUrl}" method="post" data-ajax="true">
        <label class="modal-label" for="modal-checklist-nome">Nome do checklist</label>
        <input id="modal-checklist-nome" class="modal-campo" type="text" name="nome"
               placeholder="Ex.: Checklist interno de código" required autofocus>

        <label class="modal-label">Itens do checklist</label>
        <p class="modal-mensagem" style="margin:0 0 10px;font-size:.82rem;">
          Código e categoria são opcionais; a descrição é o que a IA vai avaliar em cada documento.
        </p>
        <div id="modal-checklist-itens">${_novoItemChecklistHtml(1)}</div>
        <button type="button" class="btn-secundario" id="modal-add-item-checklist">+ Adicionar item</button>

        <div class="modal-acoes">
          <button type="button" class="btn-secundario" data-modal-cancelar>Cancelar</button>
          <button type="submit" class="btn" data-loading-text="Criando…">Criar checklist</button>
        </div>
      </form>
    </div>`;
  document.body.appendChild(overlay);

  const form = overlay.querySelector("#form-novo-checklist");
  const lista = overlay.querySelector("#modal-checklist-itens");

  const fechar = () => {
    overlay.classList.add("modal-saindo");
    setTimeout(() => overlay.remove(), 150);
  };
  overlay.querySelector("[data-modal-cancelar]").addEventListener("click", fechar);
  overlay.addEventListener("click", (evento) => {
    if (evento.target === overlay) fechar();
  });
  overlay.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") fechar();
  });
  overlay.querySelector("#modal-checklist-nome").focus();

  overlay.querySelector("#modal-add-item-checklist").addEventListener("click", () => {
    lista.insertAdjacentHTML("beforeend", _novoItemChecklistHtml(lista.children.length + 1));
  });

  lista.addEventListener("click", (evento) => {
    const botaoRemover = evento.target.closest(".btn-remover-linha");
    if (!botaoRemover) return;
    const cartoes = lista.querySelectorAll(".checklist-item-card");
    if (cartoes.length <= 1) {
      botaoRemover.closest(".checklist-item-card").querySelectorAll("input, textarea").forEach((campo) => (campo.value = ""));
      return;
    }
    botaoRemover.closest(".checklist-item-card").remove();
    _renumerarItensChecklist(lista);
  });

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const temDescricao = Array.from(form.querySelectorAll('[name="item_descricao"]')).some((campo) => campo.value.trim());
    if (!temDescricao) {
      _mostrarToast("Adicione ao menos um item com descrição para criar o checklist.", "erro");
      return;
    }
    _aplicarLoadingBotao(form);
    await submeterAjax(form);
    fechar();
  });
}

// ===================== Envio sem recarregar a página =====================
// Troca só o conteúdo principal pelo HTML que o servidor devolveria de
// qualquer forma (o Flask continua processando normalmente e redirecionando
// pra mesma página) — sem isso, cada ação simples (marcar como resolvida,
// salvar edição, etc.) jogava o usuário de volta pro topo da página.
async function submeterAjax(form) {
  const scrollY = window.scrollY;
  try {
    const resposta = await fetch(form.action, { method: "POST", body: new FormData(form) });
    const html = await resposta.text();
    const novoDoc = new DOMParser().parseFromString(html, "text/html");
    const novoConteudo = novoDoc.getElementById("conteudo-principal");
    const conteudoAtual = document.getElementById("conteudo-principal");
    if (!novoConteudo || !conteudoAtual) {
      window.location.reload();
      return;
    }
    conteudoAtual.innerHTML = novoConteudo.innerHTML;
    document.title = novoDoc.title;
    armarToasts(conteudoAtual);
    window.scrollTo({ top: scrollY });
  } catch (erro) {
    // Sem rede ou algo assim: cai pro comportamento padrão (navega mesmo).
    form.submit();
  }
}

// Feedback de carregamento: desabilita o botão e mostra texto de progresso,
// evitando duplo clique em ações demoradas.
function _aplicarLoadingBotao(form) {
  const botao = form.querySelector("button[type=submit], button:not([type])");
  if (botao && !botao.disabled) {
    botao.dataset.textoOriginal = botao.textContent;
    botao.textContent = botao.dataset.loadingText || "Enviando…";
    botao.disabled = true;
    botao.setAttribute("aria-busy", "true");
  }
}

// ===================== Modal de confirmação customizado =====================
// Substitui window.confirm() — bloqueante, sem estilo, inconsistente com o design.
// Retorna uma Promise que resolve true (confirmado) ou false (cancelado).
function confirmarAcao(mensagem, { tituloBotaoConfirmar = "Confirmar", perigo = true } = {}) {
  return new Promise((resolver) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Confirmação");

    const classeConfirmar = perigo ? "btn btn-perigo" : "btn";
    overlay.innerHTML = `
      <div class="modal-caixa">
        <p class="modal-titulo">Confirmação necessária</p>
        <p class="modal-mensagem">${mensagem}</p>
        <div class="modal-acoes">
          <button type="button" class="btn-secundario" id="modal-cancelar">Cancelar</button>
          <button type="button" class="${classeConfirmar}" id="modal-confirmar">${tituloBotaoConfirmar}</button>
        </div>
      </div>`;

    document.body.appendChild(overlay);

    const btnConfirmar = overlay.querySelector("#modal-confirmar");
    const btnCancelar = overlay.querySelector("#modal-cancelar");

    // Foco inicial no botão seguro (Cancelar) para evitar confirmações acidentais.
    btnCancelar.focus();

    function fechar(resultado) {
      overlay.classList.add("modal-saindo");
      setTimeout(() => { overlay.remove(); resolver(resultado); }, 150);
    }

    btnConfirmar.addEventListener("click", () => fechar(true));
    btnCancelar.addEventListener("click", () => fechar(false));

    // Fechar com Escape.
    overlay.addEventListener("keydown", (e) => { if (e.key === "Escape") fechar(false); });

    // Clicar fora da caixa cancela.
    overlay.addEventListener("click", (e) => { if (e.target === overlay) fechar(false); });
  });
}

document.addEventListener("submit", async (evento) => {
  const form = evento.target;
  if (!(form instanceof HTMLFormElement)) return;

  if (form.dataset.confirmar) {
    evento.preventDefault();
    const confirmado = await confirmarAcao(form.dataset.confirmar);
    if (!confirmado) return;

    // Re-submete: se tem data-ajax, vai pelo fetch; senão, navegação normal.
    if (form.dataset.ajax) {
      if (form.classList.contains("form-escalonar-nc")) {
        abrirEmailEscalonamento(form);
      }
      _aplicarLoadingBotao(form);
      submeterAjax(form);
    } else {
      form.submit();
    }
    return;
  }

  if (form.classList.contains("form-escalonar-nc")) {
    abrirEmailEscalonamento(form);
  }

  _aplicarLoadingBotao(form);

  if (form.dataset.ajax) {
    evento.preventDefault();
    submeterAjax(form);
  }
});

// ===================== Cliques delegados (participantes, toasts, menu) =====================
document.addEventListener("click", (evento) => {
  const botaoEmail = evento.target.closest(".btn-abrir-email");
  if (botaoEmail) {
    evento.preventDefault();
    abrirModalEmailEquipe(botaoEmail);
    return;
  }

  const fecharFlash = evento.target.closest(".flash-fechar");
  if (fecharFlash) {
    fecharFlash.closest(".flash")?.remove();
    return;
  }

  const botaoAdd = evento.target.closest("#add-participante");
  if (botaoAdd) {
    const lista = document.getElementById("lista-participantes");
    if (!lista) return;
    const linha = document.createElement("div");
    linha.className = "linha-participante";
    linha.innerHTML =
      '<input type="text" name="participante_nome" placeholder="Nome do integrante">' +
      '<input type="email" name="participante_email" placeholder="E-mail do integrante">' +
      '<button type="button" class="btn-remover-linha" aria-label="Remover esta linha" title="Remover">×</button>';
    lista.appendChild(linha);
    return;
  }

  const botaoAbrirChecklist = evento.target.closest(".btn-abrir-checklist-modal");
  if (botaoAbrirChecklist) {
    abrirModalNovoChecklist(botaoAbrirChecklist);
    return;
  }

  const botaoRemover = evento.target.closest(".btn-remover-linha");
  if (botaoRemover) {
    const linhaAtual = botaoRemover.closest(".linha-participante");
    const lista = linhaAtual?.parentElement;
    if (!lista) return;
    const linhas = lista.querySelectorAll(":scope > .linha-participante");
    if (linhas.length <= 1) {
      linhaAtual.querySelectorAll("input").forEach((campo) => (campo.value = ""));
      return;
    }
    linhaAtual.remove();
  }
});

// Menu de navegação colapsável em telas estreitas (elemento único, fora de
// #conteudo-principal — não precisa de delegação).
const menuToggle = document.getElementById("menu-toggle");
const topoNav = document.getElementById("topo-nav");
if (menuToggle && topoNav) {
  menuToggle.addEventListener("click", () => {
    const aberto = topoNav.classList.toggle("aberto");
    menuToggle.setAttribute("aria-expanded", aberto ? "true" : "false");
  });
}
