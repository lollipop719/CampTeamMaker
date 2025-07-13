from flask import Flask
from flask_cors import CORS
from auth import auth
from middleware import jwt_required
from flask import jsonify
from flask import render_template


app = Flask(
    __name__,
    static_folder='static',
    template_folder='templates'
)

CORS(app)

app.register_blueprint(auth)

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/protected')
@jwt_required
def protected():
    return jsonify({'msg': '이건 로그인된 사용자만 볼 수 있는 데이터입니다!'})

@app.route('/')
def home():
    return '서버 실행 중!'

if __name__ == '__main__':
    app.run(debug=True)
