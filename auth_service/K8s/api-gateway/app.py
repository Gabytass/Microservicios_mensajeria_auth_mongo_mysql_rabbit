from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

AUTH_SERVICE_URL = f"http://{os.environ.get('AUTH_SERVICE_HOST', 'auth-service')}:5000"

@app.route('/api/auth/<path:path>', methods=['POST', 'GET', 'PUT', 'DELETE'])
def auth_proxy(path):
    try:
        url = f"{AUTH_SERVICE_URL}/auth/{path}"
        response = requests.request(
            method=request.method,
            url=url,
            headers={key: value for (key, value) in request.headers if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False
        )
        return (response.content, response.status_code, response.headers.items())
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "message": "API Gateway is running smoothly."}), 200	

@app.route('/', methods=['GET'])
def root():
    return jsonify({"message": "Welcome to the API Gateway",
                    'endpoints': {
                        'auth': '/api/auth/*'
                    }
                }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)