# Aplicação Flask: recebe o PDF e liga ao motor de auditoria.
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

load_dotenv()

from auditoria import CRITERIOS, NOME, auditar

app = Flask(__name__)
app.config["SECRET_KEY"] = "auditoria-qualidade-academico"

# Limite de 16 MB por upload.
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


# Formulário de envio e o checklist aplicado, para consulta.
@app.route("/")
def index():
    return render_template("index.html", nome=NOME, criterios=CRITERIOS)


# Recebe o PDF, executa a auditoria e mostra o resultado.
@app.route("/auditar", methods=["POST"])
def auditar_documento():
    arquivo = request.files.get("documento")
    if not arquivo or not (arquivo.filename or "").lower().endswith(".pdf"):
        flash("Selecione um arquivo no formato PDF.", "erro")
        return redirect(url_for("index"))

    try:
        resultado = auditar(arquivo.stream, arquivo.filename)
    except Exception as erro:
        flash(f"Não foi possível concluir a auditoria: {erro}", "erro")
        return redirect(url_for("index"))

    return render_template("resultado.html", resultado=resultado)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
