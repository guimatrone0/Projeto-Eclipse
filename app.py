from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client
from collections import Counter
from dotenv import load_dotenv
import json
import os

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///feedbacks.db'
db = SQLAlchemy(app)

account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
client = Client(account_sid, auth_token)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nota = db.Column(db.String(10))
    resolvido = db.Column(db.String(10))
    queixa = db.Column(db.Text)
    recomendaria = db.Column(db.String(10))

perguntas = [
    "Como você avalia nosso atendimento de 1 a 10?",
    "O atendimento resolveu seu problema?",
    "Você recomendaria nosso serviço para outras pessoas?"
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    feedbacks = Feedback.query.all()
    notas = [f.nota for f in feedbacks]
    resolvidos = [f.resolvido for f in feedbacks]
    recomendariam = [f.recomendaria for f in feedbacks]

    contagem_notas = dict(Counter(notas))
    contagem_resolvidos = dict(Counter(resolvidos))
    contagem_recomendariam = dict(Counter(recomendariam))

    return render_template(
        "admin.html",
        feedbacks=feedbacks,
        contagem_notas=contagem_notas,
        contagem_resolvidos=contagem_resolvidos,
        contagem_recomendariam=contagem_recomendariam
    )


@app.route('/perguntas', methods=['POST'])
def responder():
    data = request.json
    respostas = data.get("respostas", [])
    passo = len(respostas)

    if passo == 0:
        return jsonify({"pergunta": perguntas[0], "proximo_passo": 1})
    
    elif passo == 1:
        if not respostas[0].isdigit() or not (1 <= int(respostas[0]) <= 10):
            return jsonify({"erro": "Por favor, digite um número entre 1 e 10"}), 400
        return jsonify({"pergunta": perguntas[1], "proximo_passo": 2})
    
    elif passo == 2:
        resposta = respostas[1].lower()
        if resposta not in ['sim', 'não', 'nao', 's', 'n']:
            return jsonify({"erro": "Por favor, responda com Sim ou Não"}), 400
        return jsonify({"pergunta": perguntas[2], "proximo_passo": 3})
    
    elif passo == 3:
        resposta_recomendacao = respostas[2].lower()
        if resposta_recomendacao not in ['sim', 'não', 'nao', 's', 'n']:
            return jsonify({"erro": "Por favor, responda com Sim ou Não"}), 400
        if resposta_recomendacao in ['não', 'nao', 'n']:
            return jsonify({"solicitar_queixa": True, "pergunta": "Por favor, registre sua queixa:", "proximo_passo": 4})
        else:
            feedback = Feedback(
                nota=respostas[0],
                resolvido=respostas[1],
                queixa="",
                recomendaria=resposta_recomendacao
            )
            db.session.add(feedback)
            db.session.commit()

            try:
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=os.getenv('TWILIO_TARGET_NUMBER'),
                    content_sid=os.getenv('TWILIO_TEMPLATE_SID'), 
                    content_variables=json.dumps({
                        "1": respostas[0],
                        "2": respostas[1],
                        "3": "",
                        "4": resposta_recomendacao
                    })
                )
            except Exception as e:
                print("Erro ao enviar mensagem WhatsApp:", e)

            return jsonify({"finalizado": True, "mensagem": "Obrigado pelo seu feedback! 😊"})

    elif passo == 4:
        if len(respostas[3].strip()) < 5:
            return jsonify({"erro": "Por favor, descreva melhor sua queixa"}), 400
        feedback = Feedback(
            nota=respostas[0],
            resolvido=respostas[1],
            queixa=respostas[3],
            recomendaria=respostas[2]
        )
        db.session.add(feedback)
        db.session.commit()

        try:
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=os.getenv('TWILIO_TARGET_NUMBER'),
                content_sid=os.getenv('TWILIO_TEMPLATE_SID'),
                content_variables=json.dumps({
                    "1": respostas[0],
                    "2": respostas[1],
                    "3": respostas[3],
                    "4": respostas[2]
                })
            )
        except Exception as e:
            print("Erro ao enviar mensagem WhatsApp:", e)

        return jsonify({"finalizado": True, "mensagem": "Obrigado pelo seu feedback! 😊"})
    
    else:
        return jsonify({"finalizado": True, "mensagem": "Obrigado pelo seu feedback! 😊"})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
