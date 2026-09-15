// Feedback visual durante o envio: desabilita o botão enquanto o PDF é analisado.
document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector(".form-upload");
  if (!form) return;
  form.addEventListener("submit", function () {
    const botao = form.querySelector("button");
    botao.disabled = true;
    botao.textContent = "Analisando...";
  });
});
