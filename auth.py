from flask import Blueprint, request, jsonify
from pymongo import MongoClient
import bcrypt
import jwt
import datetime
from config import MONGO_URI, JWT_SECRET

auth = Blueprint('auth', __name__)
client = MongoClient(MONGO_URI)
db = client['mydb']
users = db['users']

@auth.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data['email']
    password = data['password']

    if users.find_one({'email': email}):
        return jsonify({'msg': '이미 존재하는 이메일입니다.'}), 400

    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    users.insert_one({'email': email, 'password': hashed_pw})

    return jsonify({'msg': '회원가입 성공'}), 201

@auth.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data['email']
    password = data['password']

    user = users.find_one({'email': email})
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return jsonify({'msg': '이메일 또는 비밀번호가 올바르지 않습니다.'}), 401

    payload = {
        'email': email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return jsonify({'token': token}), 200
