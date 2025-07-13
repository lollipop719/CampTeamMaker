from flask import request, jsonify
import jwt
from config import JWT_SECRET

def jwt_required(f):
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'msg': '토큰이 없습니다.'}), 401
        try:
            decoded = jwt.decode(token.split()[1], JWT_SECRET, algorithms=['HS256'])
            request.user = decoded
        except jwt.ExpiredSignatureError:
            return jsonify({'msg': '토큰 만료'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'msg': '유효하지 않은 토큰'}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper
