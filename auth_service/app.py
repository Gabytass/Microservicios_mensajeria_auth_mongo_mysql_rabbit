from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import timedelta

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your_secret_key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

jwt = JWTManager(app)

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST', 'mysql-service'),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', 'password'),
        database=os.environ.get('MYSQL_DATABASE', 'auth_db')
    )

@app.route('/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"msg": "Username and password are required"}), 400
        
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            connection.close()
            return jsonify({"error": "Username already exists"}), 409

        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({"msg": "User created successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"msg": "Username and password are required"}), 400

        connection = get_db_connection()
        cursor = connection.cursor(dict)

        cursor.execute("SELECT * FROM users WHERE username = %s", (username, ))
        user = cursor.fetchone()

        if not user or not check_password_hash(user['password'], password):
            return jsonify({"msg": "Invalid username or password"}), 401

        access_token = create_access_token(
            identity=user['id'],
            additional_claims={"username": user['username']}
            )
        return jsonify({
            "access_token": access_token,
            "user_id": user['id'],
            "username": user['username']
            }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/auth/validate', methods=['POST'])
@jwt_required()
def validate():
    try:
        current_user = get_jwt_identity()
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT id, username FROM users WHERE id = %s", (current_user,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"msg": "User not found"}), 404

        return jsonify({
            "msg": "Token is valid",
            "user_id": user['id'],
            "username": user['username']
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "message": "Auth service is running smoothly."}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)