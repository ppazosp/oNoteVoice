import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from flasgger import Swagger
from flask_httpauth import HTTPTokenAuth

# Cargar variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

client = OpenAI(api_key=OPENAI_API_KEY)

# Configuración de Flask
app = Flask(__name__)
swagger = Swagger(app)
auth = HTTPTokenAuth(scheme='Bearer')


@auth.verify_token
def verify_token(token):
    return True  # Puedes reemplazar con una verificación real si lo deseas


@app.route('/summarize', methods=['POST'])
def summarize_text():
    """
    Genera un resumen del texto proporcionado.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            text:
              type: string
              description: Texto a resumir
    responses:
      200:
        description: Resumen generado correctamente
    """
    # Obtener datos del JSON recibido
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "No se encontró la clave 'text' en la solicitud."}), 400

    text = data["text"]

    # Generar `prompt` para OpenAI
    prompt = f"""
    A partir del siguiente texto, genera un resumen conciso manteniendo la información más relevante:

    {text}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system",
                 "content": "Eres un asistente experto en resumen de textos. Tu tarea es condensar información manteniendo la claridad y relevancia."},
                {"role": "user", "content": prompt}
            ]
        )

        summary = response.choices[0].message.content
        return jsonify({"summary": summary})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
