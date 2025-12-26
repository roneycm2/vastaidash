"""Teste simples do Flask"""
from flask import Flask
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = Flask(__name__)

@app.route('/')
def index():
    return '<h1>Dashboard Teste - Funcionando!</h1><p>Acesse: <a href="/api/test">/api/test</a></p>'

@app.route('/api/test')
def test():
    return {'status': 'ok', 'message': 'Flask esta funcionando!'}

if __name__ == '__main__':
    print("Iniciando servidor Flask na porta 5000...")
    print("Acesse: http://localhost:5000")
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        print(f"Erro ao iniciar: {e}")
        import traceback
        traceback.print_exc()

