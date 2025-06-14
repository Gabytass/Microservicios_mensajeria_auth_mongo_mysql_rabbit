from fask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import pymongo
import pika
import json
import	os
from datetime import datetime
import threading
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key')
socketio = SocketIO(app, cors_allowed_origins='*')
# MongoDB connection
mongo_client = pymongo.MongoClient(os.environ.get('MONGODB_URI', 'mongodb://mongodb-service:27017/'))
db = mongo_client.messaging_db
messages_collection = db.messages
# RabbitMQ connection
def get_rabbitmq_connection():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.environ.get('RABBITMQ_HOST', 'rabbitmq-service')))
    return connection

def validate_token(token):
    try:
        response = requests.post(f"http://{os.environ.get('AUTH_SERVICE_HOST', 'auth-service')}:5000/auth/validate", 
                                 headers={'Authorization': f'Bearer {token}'})
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except:
        return False, None

@app.route('/messages', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token is required'}), 401
        
        is_valid, user_data = validate_token(token)
        if not is_valid:    
            return jsonify({'error': 'Invalid token'}), 401
        message_data = {
            'sender_id': user_data['user_id'],
            'sender_username': user_data['username'],
            'recipient_id': data.get('recipient_id'),
            'content': data.get('content'),
            'timestamp': datetime.utcnow(),
            'status': 'sent'
        }
        result = messages_collection.insert_one(message_data)
        message_data['_id'] = str(result.inserted_id)

        connection = get_rabbitmq_connection()
        channel = connection.channel()
        channel.queue_declare(queue='messages')
        channel.basic_publish(exchange='', routing_key='messages', body=json.dumps(message_data, default=str))
        connection.close()
        return jsonify({'message': 'Message sent successfully', 'id': str(result.inserted_id)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/messages/<user_id>', methods=['GET'])
def get_message(user_id):
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token is required'}), 401

        is_valid, user_data = validate_token(token)
        if not is_valid:
            return jsonify({'error': 'Invalid token'}), 401
        
        messages = list(messages_collection.find({
            '$or': [{'sender_id': int(user_id)}, {'recipient_id': int(user_id)}]
        }).sort('timestamp', -1))
        for message in messages:
            message['_id'] = str(message['_id'])
        return jsonify({'messages': messages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    
@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room')
    join_room(room)
    emit('status', {'msg': f'Joined room {room}'})

def consume_messages():
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    channel.queue_declare(queue='messages')

    def callback(ch, method, properties, body):
        try:
            message = json.loads(body)
            socketio.emit('new_message', message)
            messages_collection.update_one({'_id': pymongo.ObjectId(message['_id'])}, {'$set': {'status': 'delivered'}})
        except Exception as e:
            print(f"Error processing message: {e}")
    channel.basic_consume(queue='messages', on_message_callback=callback, auto_ack=True)
    channel.start_consuming()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    consumer_thread = threading.Thread(target=consume_messages)
    consumer_thread.daemon = True
    consumer_thread.start()
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
