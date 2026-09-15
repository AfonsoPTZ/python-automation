# Aplicação web (Flask) da automação de auditoria de qualidade.
#
# Expõe as rotas HTTP e liga o formulário de envio ao motor de auditoria
# (pacote auditoria).
#
# Fluxo da aplicação: o usuário envia um PDF -> o motor executa o checklist
# padrão da disciplina -> a página de resultado mostra as Não Conformidades
# encontradas. Nada é gravado em disco ou em banco.
from flask import Flask, flash, redirect, render_template, request, url_for

from auditoria import CRITERIOS, NOME, auditar

app = Flask(__name__)
app.config["SECRET_KEY"] = "auditoria-qualidade-academico"

# Limite de 16 MB por upload.
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


# Página inicial: formulário de envio e o checklist aplicado, para consulta.
@app.route("/")
def index():
    return render_template("index.html", nome=NOME, criterios=CRITERIOS)


# Recebe o PDF enviado, executa a auditoria e mostra o resultado. O arquivo
# é lido direto do upload, em memória, sem ser salvo no servidor.
@app.route("/auditar", methods=["POST"])
def auditar_documento():
    arquivo = request.files.get("documento")
    if not arquivo or not (arquivo.filename or "").lower().endswith(".pdf"):
        flash("Selecione um arquivo no formato PDF.", "erro")
        return redirect(url_for("index"))

    try:
        resultado = auditar(arquivo.stream, arquivo.filename)
    except Exception as erro:
        flash(f"Não foi possível ler o PDF: {erro}", "erro")
        return redirect(url_for("index"))

    return render_template("resultado.html", resultado=resultado)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
