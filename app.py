import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Allow OAuth2 with HTTP for development

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from pymongo import MongoClient, ASCENDING
from bson.objectid import ObjectId # Import ObjectId to work with MongoDB _id
import google.generativeai as genai # Import the Gemini library
from werkzeug.utils import secure_filename
from flask import send_from_directory # Re-add for serving uploaded files
import smtplib
from email.mime.text import MIMEText
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
import json
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from genetic_algorithm import genetic_algorithm, weights

app = Flask(__name__)
app.secret_key = 'VeRYSECreT032&$90kdl2l1kdmfnt'

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Google OAuth2 Configuration ---
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI')

# --- MongoDB Configuration ---
# Use environment variables for sensitive info in production
# For local dev, you can hardcode, but ENV variables are best practice
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME") # Your database name

# Initialize MongoDB client
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME] # Access the specific database

# Get a reference to your collections
participants_collection = db.participants
users_collection = db.users  # New collection for user management
settings_collection = db.settings  # For global app settings

# --- User Model for Flask-Login ---
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.email = user_data['email']
        self.name = user_data['name']
        self.role = user_data.get('role', 'student')  # Default role is student
        self.picture = user_data.get('picture', '')

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({'_id': ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

# --- Role-Based Access Control Decorators ---
def professor_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'professor':
            flash('교수 권한이 필요합니다.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def student_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            flash('학생 권한이 필요합니다.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# --- Helper Functions ---
def determine_user_role(email):
    """Determine user role based on email domain or specific addresses"""
    # You can customize this logic based on your needs
    if email.endswith('@kaist.ac.kr'):
        return 'professor'
    elif email in ['admin@example.com', 'professor@example.com']:  # Add specific admin emails
        return 'professor'
    else:
        return 'student'

def create_or_update_user(google_user_info):
    """Create or update user in database"""
    email = google_user_info['email']
    user_data = {
        'email': email,
        'name': google_user_info['name'],
        'picture': google_user_info.get('picture', ''),
        'role': determine_user_role(email),
        'google_id': google_user_info['sub']
    }
    
    # Check if user exists
    existing_user = users_collection.find_one({'email': email})
    if existing_user:
        # Update existing user
        users_collection.update_one(
            {'email': email},
            {'$set': {
                'name': user_data['name'],
                'picture': user_data['picture'],
                'google_id': user_data['google_id']
            }}
        )
        user_data['_id'] = existing_user['_id']
        user_data['role'] = existing_user.get('role', 'student')  # Keep existing role
    else:
        # Create new user
        result = users_collection.insert_one(user_data)
        user_data['_id'] = result.inserted_id
    
    return User(user_data)

# --- File Upload Configuration (re-added for photos) ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} # Allowed image extensions

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max 16MB for uploads

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Gemini API Configuration ---
# IMPORTANT: Replace with your actual Gemini API Key
# For production, consider using os.getenv("GEMINI_API_KEY")
GEMINI_API_KEY = "AIzaSyC-R8GloQ2532iioEynN8A7UxBlwudmtsY" # <--- REPLACE WITH THE KEY YOU PROVIDED
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash') # Using gemini-pro for text generation

# --- Helper Function for Gemini Categorization ---
def categorize_with_gemini(participant_data):
    # Define the categories for each field
    major_categories = "컴퓨터, 전전, 자연, 인문, 기타"
    intern_exp_categories = "ai, backend, frontend, health, finance, robotics, 기타"
    immersion_exp_categories = "음악, 체육, 자기개발, 공부, 기타"
    club_exp_categories = "academic, art, sports, volunteer, global, hobby, self improvement, 기타"
    hobbies_categories = "예술, 운동, 디지털, 여행, 여유/감성, 학문, 기타"
    army_categories = "미필, 군필" # Not directly used in prompt but kept for context if needed elsewhere
    abroad_continents_categories = "Europe, North America, Asia, Africa, Oceania, 기타"


    # Construct the prompt
    # We include all relevant participant data for Gemini to consider
    prompt = f"""
    아래 참가자의 정보를 바탕으로 각 항목에 대해 카테고리를 분류하고, 개발 점수, 개성 점수, 열정 점수를 1점에서 100점 사이로 계산해주세요.
    각 카테고리 항목은 한글 단일 카테고리로만 응답해야 합니다.
    만약 주어진 카테고리 외에 적합한 것이 없다면 '기타'로 분류해주세요.
    각 점수 아래에 그 점수가 나온 한 줄짜리 이유를 한국어로 설명해주세요.

    --- 참가자 정보 ---
    개발 경험 상세: {participant_data.get('dev_exp', '없음')}
    전공: {participant_data.get('major', '없음')}
    인턴 경험 상세: {participant_data.get('intern_exp_details', '없음')}
    몰입해본 경험 상세: {participant_data.get('immersion_exp', '없음')}
    동아리 경험 상세: {participant_data.get('club_exp', '없음')}
    취미 상세: {participant_data.get('hobbies', '없음')}
    해외 생활 경험 상세: {participant_data.get('overseas_life', '없음')}
    수강한 전산 관련 과목 및 난이도: {participant_data.get('major_cs_courses', '없음')}
    공모전 및 대회 수상 경력: {participant_data.get('awards', '없음')}
    남들과 다른 취미: {participant_data.get('unique_hobby', '없음')}
    열정적으로 보냈던 방학: {participant_data.get('passionate_vacation', '없음')}
    추가로 더 하고 싶은 얘기: {participant_data.get('additional_comments', '없음')}
    지원동기: {participant_data.get('application_motive', '없음')}
    ---

    --- 분류 기준 ---
    전공 카테고리: {major_categories}
    인턴 경험 카테고리: {intern_exp_categories}
    몰입해본 경험 카테고리: {immersion_exp_categories}
    동아리 카테고리: {club_exp_categories}
    취미 카테고리: {hobbies_categories}
    해외 생활 경험 카테고리: {abroad_continents_categories}
    ---

    --- 점수 계산 기준 (1-100점) ---
    개발 점수 (dev_score): 지금까지 수강한 전산관련 과목 중 주요과목(수업 난이도에 따라 차등 점수 지급), 개발경험, 인턴경험, 공모전 및 대회 수상 경력
    개성 점수 (personality_score): 해외생활 경험, 남들과 다른 취미, 동아리, 열정적으로 보냈던 방학
    열정 점수 (passion_score): 추가로 더 하고 싶은 얘기, 지원동기
    ---

    --- 응답 형식 ---
    전공: 카테고리
    인턴 경험: 카테고리
    몰입해본 경험: 카테고리
    동아리: 카테고리
    취미: 카테고리
    해외 생활 경험: 카테고리
    개발 점수: 숫자 (1-100)
    개발 점수 이유: 한 줄 설명
    개성 점수: 숫자 (1-100)
    개성 점수 이유: 한 줄 설명
    열정 점수: 숫자 (1-100)
    열정 점수 이유: 한 줄 설명
    ---
    """
    print(f"Sending prompt for {participant_data.get('name')}:\n{prompt}") # For debugging

    try:
        response = model.generate_content(prompt)
        gemini_text = response.text.strip()
        print(f"Gemini response:\n{gemini_text}") # For debugging

        # Parse the Gemini response
        parsed_categories = {}
        for line in gemini_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                parsed_categories[key.strip()] = value.strip()

        # Safely convert scores to int, defaulting to 0 if not found or invalid
        dev_score = int(parsed_categories.get('개발 점수', 0))
        personality_score = int(
            parsed_categories.get('개성 점수', parsed_categories.get('성격 점수', 0))
        )
        passion_score = int(parsed_categories.get('열정 점수', 0))

        # Calculate avg_score, handle division by zero
        total_score = dev_score + personality_score + passion_score
        avg_score = round(total_score / 3, 2) if total_score > 0 else 0

        personality_score_reason = parsed_categories.get(
            '개성 점수 이유', parsed_categories.get('성격 점수 이유', '설명 없음')
        )

        return {
            "categorized_major": parsed_categories.get('전공', '기타'),
            "categorized_intern_exp": parsed_categories.get('인턴 경험', '기타'),
            "categorized_immersion_exp": parsed_categories.get('몰입해본 경험', '기타'),
            "categorized_club_exp": parsed_categories.get('동아리', '기타'),
            "categorized_hobbies": parsed_categories.get('취미', '기타'),
            "categorized_abroad_exp": parsed_categories.get('해외 생활 경험', '기타'),
            "dev_score": dev_score,
            "dev_score_reason": parsed_categories.get('개발 점수 이유', '설명 없음'),
            "personality_score": personality_score,
            "personality_score_reason": personality_score_reason,
            "passion_score": passion_score,
            "passion_score_reason": parsed_categories.get('열정 점수 이유', '설명 없음'),
            "avg_score": avg_score,
        }
    except Exception as e:
        print(f"Error calling Gemini API for {participant_data.get('name')}: {e}")
        return {
            "categorized_major": "오류",
            "categorized_intern_exp": "오류",
            "categorized_immersion_exp": "오류",
            "categorized_club_exp": "오류",
            "categorized_hobbies": "오류",
            "categorized_abroad_exp": "오류",
            "dev_score": 0,
            "dev_score_reason": "오류",
            "personality_score": 0,
            "personality_score_reason": "오류",
            "passion_score": 0,
            "passion_score_reason": "오류",
            "avg_score": 0,
        }

# --- Settings Helper Functions ---
def get_app_settings():
    settings = settings_collection.find_one({'_id': 'global'})
    if not settings:
        # Default: open always, pass_limit 5
        settings = {
            '_id': 'global',
            'open_time': None,
            'close_time': None,
            'pass_limit': 5
        }
        settings_collection.insert_one(settings)
    return settings

def update_app_settings(open_time, close_time, pass_limit):
    settings_collection.update_one(
        {'_id': 'global'},
        {'$set': {'open_time': open_time, 'close_time': close_time, 'pass_limit': pass_limit}},
        upsert=True
    )

# --- Authentication Routes ---

@app.route('/login')
def login():
    # Check if this is an OAuth callback (has 'code' parameter)
    if request.args.get('code'):
        # This is an OAuth callback, redirect to the callback handler
        return callback()
    
    # This is a regular login page request
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/google-login')
def google_login():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI]
            }
        },
        scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    try:
        print("DEBUG: Starting OAuth callback...")
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [GOOGLE_REDIRECT_URI]
                }
            },
            scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
        )
        flow.redirect_uri = GOOGLE_REDIRECT_URI
        
        print(f"DEBUG: Redirect URI set to: {GOOGLE_REDIRECT_URI}")
        
        # Use the authorization server's response to fetch the OAuth 2.0 tokens
        authorization_response = request.url
        print(f"DEBUG: Authorization response URL: {authorization_response}")
        
        flow.fetch_token(authorization_response=authorization_response)
        
        # Get user info from Google
        credentials = flow.credentials
        print("DEBUG: Got credentials from Google")
        
        id_info = id_token.verify_oauth2_token(
            credentials.id_token, requests.Request(), GOOGLE_CLIENT_ID
        )
        print(f"DEBUG: Got user info: {id_info.get('email')}")
        
        # Create or update user
        user = create_or_update_user(id_info)
        print(f"DEBUG: Created/updated user: {user.email} with role: {user.role}")
        
        login_user(user)
        print("DEBUG: User logged in successfully")
        
        flash(f'{user.name}님, 환영합니다! ({user.role} 권한)', 'success')
        return redirect(url_for('home'))
        
    except Exception as e:
        print(f"ERROR in callback: {e}")
        import traceback
        traceback.print_exc()
        flash('로그인 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('home'))

@app.route('/upgrade_role', methods=['POST'])
@login_required
def upgrade_role():
    code = request.form.get('code')
    professor_code = os.getenv('PROFESSOR_CODE', 'campsecret2024')
    if code and code == professor_code:
        users_collection.update_one({'_id': ObjectId(current_user.id)}, {'$set': {'role': 'professor'}})
        flash('교수 권한이 부여되었습니다.', 'success')
    else:
        flash('코드가 올바르지 않습니다.', 'error')
    return redirect(url_for('home'))

# --- Routes ---

@app.route('/')
def home():
    settings = get_app_settings()
    now = datetime.now().isoformat(timespec='minutes')
    app_open = True
    closed_message = ''
    if settings['open_time'] and now < settings['open_time']:
        app_open = False
        closed_message = '아직 지원 기간이 시작되지 않았습니다.'
    if settings['close_time'] and now > settings['close_time']:
        app_open = False
        closed_message = '지원 기간이 마감되었습니다.'
    if current_user.is_authenticated:
        if current_user.role == 'professor':
            num_participants = participants_collection.count_documents({})
            return render_template('home.html', user=current_user, num_participants=num_participants, is_professor=True, app_open=app_open, closed_message=closed_message)
        else:
            return render_template('home.html', user=current_user, is_professor=False, app_open=app_open, closed_message=closed_message)
    else:
        return render_template('home.html', user=None, app_open=app_open, closed_message=closed_message)

# Define a route for participant registration (GET to display form)
@app.route('/register', methods=['GET'])
@student_required
def register_form():
    settings = get_app_settings()
    now = datetime.now().isoformat(timespec='minutes')
    if settings['open_time'] and now < settings['open_time']:
        flash('아직 지원 기간이 시작되지 않았습니다.', 'warning')
        return redirect(url_for('home'))
    if settings['close_time'] and now > settings['close_time']:
        flash('지원 기간이 마감되었습니다.', 'warning')
        return redirect(url_for('home'))
    return render_template('register.html') # Render the HTML form from templates/


@app.route('/register', methods=['POST'])
@student_required
def register_submit():
    # Handle Photo Upload
    profile_photo_filename = None # Initialize the variable
    if 'profile_photo' in request.files:
        file = request.files['profile_photo']
        if file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(file_path)
                profile_photo_filename = filename # This line sets the filename if save is successful
                print(f"DEBUG: Photo '{filename}' saved and filename variable set.") # Add this
            except Exception as e:
                print(f"ERROR: Failed to save file {filename}: {e}")
                flash(f"사진 저장 중 오류 발생: {e}", "error")
                # If saving fails, profile_photo_filename will remain None or previous value
        elif file.filename != '' and not allowed_file(file.filename):
            flash("허용되지 않는 사진 파일 형식입니다. (png, jpg, jpeg, gif)", "error")
            return redirect(request.url)
    else:
        print("DEBUG: No 'profile_photo' in request.files or file input was empty.") # Add this

    # Video URL is now a direct form field, not a file upload
    video_url = request.form.get('self_video_url', '').strip()
    if not video_url:
        flash("동영상 URL은 필수 입력 항목입니다.", "error")
        return redirect(request.url)
    # Basic URL validation (you might want more robust validation here)
    if not (video_url.startswith('http://') or video_url.startswith('https://')):
        flash("유효한 동영상 URL을 입력해주세요 (http:// 또는 https://로 시작).", "error")
        return redirect(request.url)

    # Handle multiple selections for major_cs_courses
    major_cs_courses_list = request.form.getlist('major_cs_courses')
    if not major_cs_courses_list:
        flash("주요 전산관련 과목을 하나 이상 선택해주세요.", "error")
        return redirect(request.url)


    participant_data = {
        "name": request.form['name'],
        "contact": request.form['contact'],
        "email": request.form['email'],
        "university": request.form['university'],
        "major": request.form['major'], # New 'major' field
        "high_school_type": request.form['high_school_type'],
        "student_id": int(request.form['student_id']),
        "semester": int(request.form['semester']),
        "age": int(request.form['age']),
        "gender": request.form['gender'],
        "reapply": request.form['reapply'],
        "military_service": request.form['military_service'],
        "graduation_leave": request.form['graduation_leave'],
        "re_exam": request.form['re_exam'],
        "major_cs_courses": major_cs_courses_list, # Now a list

        # 대학생활 fields (textareas)
        "passion_vacation": request.form.get('passion_vacation', ''),
        "active_club": request.form.get('active_club', ''),
        "leave_period_work": request.form.get('leave_period_work', ''),
        "intern_exp_details": request.form.get('intern_exp_details', ''),
        "personal_project_details": request.form.get('personal_project_details', ''),

        # 기타 fields (textareas and video URL)
        "profile_photo_filename": profile_photo_filename,
        "self_video_url": video_url, # Now directly from form input
        "overseas_life": request.form.get('overseas_life', ''),
        "awards_competitions": request.form.get('awards_competitions', ''),
        "unique_hobby": request.form.get('unique_hobby', ''),
        "application_motive": request.form.get('application_motive', ''),
        "additional_comments": request.form.get('additional_comments', ''),
        "mbti": request.form.get('mbti', ''),

        # Old fields that might still be expected by existing categorization logic
        "school": request.form['university'],
        "major_cs_courses": major_cs_courses_list,
        "region": "",
        "dev_exp": request.form.get('personal_project_details', ''),
        "intern_exp": request.form.get('intern_exp_details', ''),
        "immersion_exp": request.form.get('passion_vacation', ''),
        "club_exp": request.form.get('active_club', ''),
        "hobbies": request.form.get('unique_hobby', ''),
        "overseas_exp": "유" if request.form.get('overseas_life') else "무",
        "overseas_details": {"duration": request.form.get('overseas_life', ''), "continent": "N/A"} if request.form.get('overseas_life') else None,
        # --- Link to Google user ---
        "google_id": str(current_user.id),
    }

    try:
        result = participants_collection.insert_one(participant_data)
        print(f"Inserted participant: {participant_data['name']} with ID: {result.inserted_id}")
        flash("참가자 정보가 성공적으로 등록되었습니다.", "success")
        return redirect(url_for('list_participants'))
    except Exception as e:
        print(f"Error registering participant: {e}")
        flash(f"참가자 등록 중 오류 발생: {e}", "error")
        return redirect(url_for('register_form'))


@app.route('/participants')
@professor_required
def list_participants():
    all_participants = list(participants_collection.find({}))
    graded = [p for p in all_participants if p.get('avg_score') is not None]
    ungraded = [p for p in all_participants if p.get('avg_score') is None]
    graded.sort(key=lambda p: float(p.get('avg_score', 0) or 0), reverse=True)
    ungraded.sort(key=lambda p: p['_id'], reverse=True)

    # Use aggregation for fast statistics
    pipeline = [
        {"$facet": {
            "pass": [
                {"$match": {"status": "합격"}},
                {"$group": {
                    "_id": None,
                    "kaist_male": {"$sum": {"$cond": [
                        {"$and": [
                            {"$eq": ["$university", "카이스트"]},
                            {"$eq": ["$gender", "남자"]}
                        ]}, 1, 0]}},
                    "kaist_female": {"$sum": {"$cond": [
                        {"$and": [
                            {"$eq": ["$university", "카이스트"]},
                            {"$eq": ["$gender", "여자"]}
                        ]}, 1, 0]}},
                    "other_male": {"$sum": {"$cond": [
                        {"$and": [
                            {"$ne": ["$university", "카이스트"]},
                            {"$eq": ["$gender", "남자"]}
                        ]}, 1, 0]}},
                    "other_female": {"$sum": {"$cond": [
                        {"$and": [
                            {"$ne": ["$university", "카이스트"]},
                            {"$eq": ["$gender", "여자"]}
                        ]}, 1, 0]}},
                    "total": {"$sum": 1}
                }}
            ],
            "fail": [{"$match": {"status": "불합격"}}, {"$count": "count"}],
            "pending": [{"$match": {"status": "미정"}}, {"$count": "count"}],
            "all": [{"$count": "count"}]
        }}
    ]
    result = list(participants_collection.aggregate(pipeline))[0]
    pass_stats = result['pass'][0] if result['pass'] else {"kaist_male": 0, "kaist_female": 0, "other_male": 0, "other_female": 0, "total": 0}
    fail_count = result['fail'][0]['count'] if result['fail'] else 0
    pending_count = result['pending'][0]['count'] if result['pending'] else 0
    total_count = result['all'][0]['count'] if result['all'] else 0
    statistics = {
        'total': pass_stats['total'],
        'pass': pass_stats['total'],
        'fail': fail_count,
        'pending': pending_count,
        'kaist_male': pass_stats['kaist_male'],
        'kaist_female': pass_stats['kaist_female'],
        'other_male': pass_stats['other_male'],
        'other_female': pass_stats['other_female']
    }
    return render_template('participants_list.html', graded_participants=graded, ungraded_participants=ungraded, statistics=statistics)

@app.route('/update_status/<participant_id>', methods=['POST'])
@professor_required
def update_status(participant_id):
    try:
        obj_id = ObjectId(participant_id)
        status = request.json.get('status')
        print(f"Updating status for participant {participant_id} to {status}")
        if status not in ['합격', '불합격', '미정']:
            return jsonify({'error': 'Invalid status'}), 400
        result = participants_collection.update_one(
            {'_id': obj_id},
            {'$set': {'status': status}}
        )
        print(f"Update result: modified_count = {result.modified_count}")
        if result.modified_count == 1:
            # Use aggregation for fast statistics
            pipeline = [
                {"$facet": {
                    "pass": [
                        {"$match": {"status": "합격"}},
                        {"$group": {
                            "_id": None,
                            "kaist_male": {"$sum": {"$cond": [
                                {"$and": [
                                    {"$eq": ["$university", "카이스트"]},
                                    {"$eq": ["$gender", "남자"]}
                                ]}, 1, 0]}},
                            "kaist_female": {"$sum": {"$cond": [
                                {"$and": [
                                    {"$eq": ["$university", "카이스트"]},
                                    {"$eq": ["$gender", "여자"]}
                                ]}, 1, 0]}},
                            "other_male": {"$sum": {"$cond": [
                                {"$and": [
                                    {"$ne": ["$university", "카이스트"]},
                                    {"$eq": ["$gender", "남자"]}
                                ]}, 1, 0]}},
                            "other_female": {"$sum": {"$cond": [
                                {"$and": [
                                    {"$ne": ["$university", "카이스트"]},
                                    {"$eq": ["$gender", "여자"]}
                                ]}, 1, 0]}},
                            "total": {"$sum": 1}
                        }}
                    ],
                    "fail": [{"$match": {"status": "불합격"}}, {"$count": "count"}],
                    "pending": [{"$match": {"status": "미정"}}, {"$count": "count"}],
                    "all": [{"$count": "count"}]
                }}
            ]
            result = list(participants_collection.aggregate(pipeline))[0]
            pass_stats = result['pass'][0] if result['pass'] else {"kaist_male": 0, "kaist_female": 0, "other_male": 0, "other_female": 0, "total": 0}
            fail_count = result['fail'][0]['count'] if result['fail'] else 0
            pending_count = result['pending'][0]['count'] if result['pending'] else 0
            total_count = result['all'][0]['count'] if result['all'] else 0
            response_data = {
                'success': True,
                'message': f'Status updated to {status}',
                'statistics': {
                    'total': pass_stats['total'],
                    'pass': pass_stats['total'],
                    'fail': fail_count,
                    'pending': pending_count,
                    'kaist_male': pass_stats['kaist_male'],
                    'kaist_female': pass_stats['kaist_female'],
                    'other_male': pass_stats['other_male'],
                    'other_female': pass_stats['other_female']
                }
            }
            print(f"Sending response: {response_data}")
            return jsonify(response_data)
        else:
            return jsonify({'success': False, 'error': 'Participant not found'}), 404
    except Exception as e:
        print(f"Error in update_status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/categorize_participants', methods=['GET'])
@professor_required
def categorize_all_participants():
    participants = participants_collection.find({})
    updated_count = 0
    errors_count = 0

    for participant in participants:
        participant_id = participant['_id']
        print(f"Processing participant: {participant.get('name')} (ID: {participant_id})")

        # Ensure 'major' field exists for Gemini, use its new value
        # This is important if you have old data without the 'major' field
        participant_for_gemini = participant.copy()
        if 'major_cs_courses' in participant_for_gemini and isinstance(participant_for_gemini['major_cs_courses'], list):
            participant_for_gemini['major'] = ", ".join(participant_for_gemini['major_cs_courses'])
        else:
            participant_for_gemini['major'] = participant_for_gemini.get('major', '없음') # Use the new 'major' field if it exists

        categorized_data = categorize_with_gemini(participant_for_gemini)

        if "오류" not in categorized_data.values():
            try:
                participants_collection.update_one(
                    {'_id': participant_id},
                    {'$set': categorized_data}
                )
                updated_count += 1
                print(f"Successfully categorized and updated: {participant.get('name')}")
            except Exception as e:
                errors_count += 1
                print(f"Failed to update MongoDB for {participant.get('name')}: {e}")
        else:
            errors_count += 1
            print(f"Skipping update for {participant.get('name')} due to Gemini API error.")

    flash(f"총 {updated_count}명의 참가자 분류 완료. {errors_count}명 오류 발생.", "info")
    return redirect(url_for('list_participants'))

@app.route('/categorize_participant/<participant_id>', methods=['POST'])
@professor_required
def categorize_participant(participant_id):
    try:
        obj_id = ObjectId(participant_id)
        participant = participants_collection.find_one({'_id': obj_id})
        if not participant:
            return jsonify({'success': False, 'error': '참가자를 찾을 수 없습니다.'}), 404
        # Prepare data for Gemini (ensure 'major' is a string)
        participant_for_gemini = participant.copy()
        if 'major_cs_courses' in participant_for_gemini and isinstance(participant_for_gemini['major_cs_courses'], list):
            participant_for_gemini['major'] = ", ".join(participant_for_gemini['major_cs_courses'])
        else:
            participant_for_gemini['major'] = participant_for_gemini.get('major', '없음')
        categorized_data = categorize_with_gemini(participant_for_gemini)
        if "오류" in categorized_data.values():
            return jsonify({'success': False, 'error': 'Gemini API 오류'}), 500
        participants_collection.update_one({'_id': obj_id}, {'$set': categorized_data})
        # Return only the updated fields for live update
        return jsonify({'success': True, 'data': categorized_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/edit_participant/<participant_id>', methods=['GET', 'POST'])
@professor_required
def edit_participant(participant_id):
    try:
        obj_id = ObjectId(participant_id)
    except Exception:
        flash("유효하지 않은 참가자 ID입니다.", "error")
        return redirect(url_for('list_participants'))

    participant = participants_collection.find_one({'_id': obj_id})
    if not participant:
        flash("참가자를 찾을 수 없습니다.", "error")
        return redirect(url_for('list_participants'))

    if request.method == 'POST':
        # Handle Photo Upload
        profile_photo_filename = participant.get('profile_photo_filename') # Keep existing if no new file
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                profile_photo_filename = filename
            elif file.filename != '' and not allowed_file(file.filename):
                flash("허용되지 않는 사진 파일 형식입니다. (png, jpg, jpeg, gif)", "error")
                return redirect(request.url)

        # Handle Video URL
        video_url = request.form.get('self_video_url', '').strip()
        if not video_url:
            flash("동영상 URL은 필수 입력 항목입니다.", "error")
            return redirect(request.url)
        if not (video_url.startswith('http://') or video_url.startswith('https://')):
            flash("유효한 동영상 URL을 입력해주세요 (http:// 또는 https://로 시작).", "error")
            return redirect(request.url)

        # Handle multiple selections for major_cs_courses
        major_cs_courses_list = request.form.getlist('major_cs_courses')
        if not major_cs_courses_list:
            flash("주요 전산관련 과목을 하나 이상 선택해주세요.", "error")
            return redirect(request.url)

        updated_data = {
            "name": request.form['name'],
            "contact": request.form['contact'],
            "email": request.form['email'],
            "university": request.form['university'],
            "major": request.form['major'], # New 'major' field
            "high_school_type": request.form['high_school_type'],
            "student_id": int(request.form['student_id']),
            "semester": int(request.form['semester']),
            "age": int(request.form['age']),
            "gender": request.form['gender'],
            "reapply": request.form['reapply'],
            "military_service": request.form['military_service'],
            "graduation_leave": request.form['graduation_leave'],
            "re_exam": request.form['re_exam'],
            "major_cs_courses": major_cs_courses_list, # Now a list

            "passion_vacation": request.form.get('passion_vacation', ''),
            "active_club": request.form.get('active_club', ''),
            "leave_period_work": request.form.get('leave_period_work', ''),
            "intern_exp_details": request.form.get('intern_exp_details', ''),
            "personal_project_details": request.form.get('personal_project_details', ''),

            "profile_photo_filename": profile_photo_filename, # Store filename
            "self_video_url": video_url,
            "overseas_life": request.form.get('overseas_life', ''),
            "awards_competitions": request.form.get('awards_competitions', ''),
            "unique_hobby": request.form.get('unique_hobby', ''),
            "application_motive": request.form.get('application_motive', ''),
            "additional_comments": request.form.get('additional_comments', ''),
            "mbti": request.form.get('mbti', participant.get('mbti', '')),

            # Proxying new fields to old names for categorization function compatibility
            "school": request.form['university'],
            # "major" is now taken directly from the new 'major' field for Gemini
            "region": participant.get('region', ''),
            "dev_exp": request.form.get('personal_project_details', ''),
            "intern_exp": request.form.get('intern_exp_details', ''),
            "immersion_exp": request.form.get('passion_vacation', ''),
            "club_exp": request.form.get('active_club', ''),
            "hobbies": request.form.get('unique_hobby', ''),
            "overseas_exp": "유" if request.form.get('overseas_life') else "무",
            "overseas_details": {"duration": request.form.get('overseas_life', ''), "continent": "N/A"} if request.form.get('overseas_life') else None,
        }

        try:
            participants_collection.update_one(
                {'_id': obj_id},
                {'$set': updated_data}
            )
            print(f"Participant {updated_data['name']} (ID: {participant_id}) updated successfully.")

            updated_participant = participants_collection.find_one({'_id': obj_id})
            if updated_participant:
                # Prepare participant data for Gemini categorization with the new 'major' field
                participant_for_gemini = updated_participant.copy()
                if 'major_cs_courses' in participant_for_gemini and isinstance(participant_for_gemini['major_cs_courses'], list):
                    participant_for_gemini['major'] = ", ".join(participant_for_gemini['major_cs_courses'])
                else:
                    participant_for_gemini['major'] = participant_for_gemini.get('major', '없음')

                categorized_data = categorize_with_gemini(participant_for_gemini)
                if "오류" not in categorized_data.values():
                    participants_collection.update_one(
                        {'_id': obj_id},
                        {'$set': categorized_data}
                    )
                    print(f"Re-categorized participant {updated_participant.get('name')}.")
                    flash("참가자 정보가 성공적으로 수정 및 재분류되었습니다.", "success")
                else:
                    print(f"Failed to re-categorize {updated_participant.get('name')} after edit.")
                    flash("참가자 정보는 수정되었으나, 재분류 중 오류가 발생했습니다.", "warning")
            else:
                flash("참가자 정보가 성공적으로 수정되었습니다.", "success")

            return redirect(url_for('list_participants', status='success', message=updated_data['name'] + ' 님 정보가 성공적으로 수정되었습니다.'))

        except Exception as e:
            print(f"Error updating participant {participant_id}: {e}")
            flash(f"참가자 수정 중 오류 발생: {e}", "error")
            return redirect(url_for('list_participants', status='error', message='참가자 수정 중 오류 발생'))

    else: # GET request
        return render_template('edit_participant.html', participant=participant)

@app.route('/delete_participant/<participant_id>', methods=['POST'])
@professor_required
def delete_participant(participant_id):
    try:
        obj_id = ObjectId(participant_id)
    except Exception:
        return jsonify(status='error', message='유효하지 않은 참가자 ID입니다.'), 400

    try:
        # Optional: Delete the actual photo file from the server
        participant = participants_collection.find_one({'_id': obj_id})
        if participant and participant.get('profile_photo_filename'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], participant['profile_photo_filename'])
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted photo file: {file_path}")

        result = participants_collection.delete_one({'_id': obj_id})
        if result.deleted_count == 1:
            print(f"Participant {participant_id} deleted successfully.")
            return jsonify(status='success', message='참가자가 성공적으로 삭제되었습니다.')
        else:
            return jsonify(status='error', message='삭제할 참가자를 찾을 수 없습니다.'), 404
    except Exception as e:
        print(f"Error deleting participant {participant_id}: {e}")
        return jsonify(status='error', message=f'참가자 삭제 중 오류 발생: {e}'), 500

# Route to serve uploaded files (re-added for photos)
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/divide_groups')
@professor_required
def divide_groups():
    합격자 = list(participants_collection.find({'status': '합격'}))
    if not 합격자 or len(합격자) < 4:
        flash('합격자가 4명 이상이어야 분반이 가능합니다.', 'error')
        return redirect(url_for('organize_page'))
    # Run the genetic algorithm with default weights
    from genetic_algorithm import weights
    grouping = genetic_algorithm(합격자, weights, num_groups=4)
    # Convert all ObjectIds to strings for session storage
    grouping_str = [[str(aid) for aid in group] for group in grouping]
    session['latest_grouping'] = grouping_str
    session['latest_weights'] = weights  # Store the weights used
    flash('분반이 완료되었습니다!', 'success')
    return redirect(url_for('group_results'))

@app.route('/group_results')
@professor_required
def group_results():
    grouping = session.get('latest_grouping')
    if not grouping:
        flash('먼저 분반을 실행해주세요.', 'error')
        return redirect(url_for('organize_page'))
    # Get the weights that were used for this grouping
    weights_used = session.get('latest_weights', {}) or {}
    # Fetch all 합격자 info
    합격자 = {str(p['_id']): p for p in participants_collection.find({'status': '합격'})}
    # Build group info
    groups = []
    for group in grouping:
        group_info = [합격자.get(str(aid)) for aid in group if 합격자.get(str(aid))]
        groups.append(group_info)
    return render_template('group_results.html', groups=groups, weights_used=weights_used)

@app.route('/organize')
@professor_required
def organize_page():
    participants = list(participants_collection.find({}))
    합격자_count = sum(1 for p in participants if p.get('status') == '합격')
    num_groups = 4
    try:
        pass_limit = int(request.args.get('pass_limit', 80))
    except Exception:
        pass_limit = 80
    # Compute statistics for the floating box
    statistics = {
        'pending': 0,
        'pass': 0,
        'fail': 0,
        'kaist_male': 0,
        'kaist_female': 0,
        'other_male': 0,
        'other_female': 0,
        'total': len(participants)
    }
    for p in participants:
        status = p.get('status', '미정') or '미정'
        if status == '합격':
            statistics['pass'] += 1
        elif status == '불합격':
            statistics['fail'] += 1
        else:
            statistics['pending'] += 1
        univ = p.get('university', '')
        gender = p.get('gender', '')
        if univ == '카이스트':
            if gender == '남자':
                statistics['kaist_male'] += 1
            elif gender == '여자':
                statistics['kaist_female'] += 1
        else:
            if gender == '남자':
                statistics['other_male'] += 1
            elif gender == '여자':
                statistics['other_female'] += 1
    return render_template('organize.html', participants=participants, pass_limit=pass_limit, statistics=statistics, 합격자_count=합격자_count, num_groups=num_groups)

@app.route('/get_mail_recipients')
@login_required
@professor_required
def get_mail_recipients():
    mail_type = request.args.get('type')
    if mail_type == 'pass':
        recipients = [p['email'] for p in participants_collection.find({'status': '합격'})]
    elif mail_type == 'fail':
        recipients = [p['email'] for p in participants_collection.find({'status': '불합격'})]
    else:
        return jsonify({'recipients': []})
    return jsonify({'recipients': recipients})

# --- Real Email Sending Function (Gmail SMTP) ---
def send_real_email(to_email, subject, body, user_email=None, user_password=None, bcc_list=None):
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    
    # Use provided credentials or fall back to environment variables
    if user_email and user_password:
        smtp_user = user_email
        smtp_password = user_password
    else:
        smtp_user = os.getenv('GMAIL_USER', 'sciencekid719@gmail.com')
        smtp_password = os.getenv('GMAIL_APP_PASSWORD')
    
    if not smtp_password:
        print('GMAIL_APP_PASSWORD environment variable not set!')
        return False
    
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to_email if to_email else ''
        if bcc_list:
            msg['Bcc'] = ','.join(bcc_list)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, [to_email] if to_email else [] + (bcc_list if bcc_list else []), msg.as_string())
        return True
    except Exception as e:
        print(f'Error sending email: {e}')
        return False

@app.route('/send_bulk_mail', methods=['POST'])
@login_required
@professor_required
def send_bulk_mail():
    data = request.get_json()
    mail_type = data.get('type')
    draft = data.get('draft')
    user_email = data.get('user_email')
    user_password = data.get('user_password')
    use_bcc = data.get('bcc', False)
    single = data.get('single', False)
    single_recipient = data.get('recipient')
    
    if mail_type == 'pass':
        recipients = [p['email'] for p in participants_collection.find({'status': '합격'})]
        subject = '합격을 축하합니다!'
    elif mail_type == 'fail':
        recipients = [p['email'] for p in participants_collection.find({'status': '불합격'})]
        subject = '불합격 안내'
    else:
        return jsonify({'message': '잘못된 요청'}), 400
    
    if use_bcc:
        # Send one mail with all in BCC
        try:
            send_real_email('', subject, draft, user_email, user_password, bcc_list=recipients)
            return jsonify({'message': f'BCC로 {len(recipients)}명에게 메일을 보냈습니다.'})
        except Exception as e:
            return jsonify({'message': f'BCC 메일 발송 중 오류: {e}'}), 500
    elif single and single_recipient:
        # Send to a single recipient (for progress)
        try:
            send_real_email(single_recipient, subject, draft, user_email, user_password)
            return jsonify({'message': f'{single_recipient}에게 메일을 보냈습니다.'})
        except Exception as e:
            return jsonify({'message': f'개별 메일 발송 중 오류: {e}'}), 500
    else:
        # Fallback: send all individually (legacy)
        sent_count = 0
        for email in recipients:
            try:
                send_real_email(email, subject, draft, user_email, user_password)
                sent_count += 1
            except Exception as e:
                print(f'Error sending to {email}: {e}')
        return jsonify({'message': f'{sent_count}명에게 메일을 보냈습니다.'})

@app.route('/my_registration', methods=['GET', 'POST'])
@login_required
def my_registration():
    # Only allow students
    if getattr(current_user, 'role', None) != 'student':
        flash('학생만 접근할 수 있습니다.', 'error')
        return redirect(url_for('home'))
    settings = get_app_settings()
    now = datetime.now().isoformat(timespec='minutes')
    if settings['open_time'] and now < settings['open_time']:
        flash('아직 지원 기간이 시작되지 않았습니다.', 'warning')
        return redirect(url_for('home'))
    if settings['close_time'] and now > settings['close_time']:
        flash('지원 기간이 마감되었습니다.', 'warning')
        return redirect(url_for('home'))

    participant = participants_collection.find_one({'google_id': str(current_user.id)})

    if request.method == 'POST':
        update_data = {
            'name': request.form['name'],
            'contact': request.form['contact'],
            'email': current_user.email,  # Do not allow changing email
            'university': request.form['university'],
            'major': request.form['major'],
            'high_school_type': request.form['high_school_type'],
            'student_id': int(request.form['student_id']),
            'semester': int(request.form['semester']),
            'age': int(request.form['age']),
            'gender': request.form['gender'],
            'reapply': request.form['reapply'],
            'military_service': request.form['military_service'],
            'graduation_leave': request.form['graduation_leave'],
            're_exam': request.form['re_exam'],
            'major_cs_courses': request.form.getlist('major_cs_courses'),
            'passion_vacation': request.form.get('passion_vacation', ''),
            'active_club': request.form.get('active_club', ''),
            'leave_period_work': request.form.get('leave_period_work', ''),
            'intern_exp_details': request.form.get('intern_exp_details', ''),
            'personal_project_details': request.form.get('personal_project_details', ''),
            'self_video_url': request.form.get('self_video_url', ''),
            'overseas_life': request.form.get('overseas_life', ''),
            'awards_competitions': request.form.get('awards_competitions', ''),
            'unique_hobby': request.form.get('unique_hobby', ''),
            'application_motive': request.form.get('application_motive', ''),
            'additional_comments': request.form.get('additional_comments', ''),
            'mbti': request.form.get('mbti', ''),
            'school': request.form['university'],
        }
        participants_collection.update_one({'google_id': str(current_user.id)}, {'$set': update_data})
        flash('정보가 성공적으로 수정되었습니다.', 'success')
        return redirect(url_for('home'))

    return render_template(
        'register.html',
        participant=participant,
        edit_mode=True
    )

# --- Settings API Endpoints ---
@app.route('/api/settings', methods=['GET'])
@login_required
def api_get_settings():
    settings = get_app_settings()
    return jsonify({
        'open_time': settings.get('open_time'),
        'close_time': settings.get('close_time'),
        'pass_limit': settings.get('pass_limit', 5)
    })

@app.route('/api/settings', methods=['POST'])
@login_required
def api_update_settings():
    data = request.get_json()
    open_time = data.get('open_time')
    close_time = data.get('close_time')
    pass_limit = int(data.get('pass_limit', 5))
    update_app_settings(open_time, close_time, pass_limit)
    return jsonify({'success': True})

@app.route('/api/group_fitness')
@professor_required
def api_group_fitness():
    grouping = session.get('latest_grouping')
    if not grouping:
        return jsonify({'error': 'No grouping found'}), 400
    # Use the weights that were used for this grouping
    weights_used = session.get('latest_weights', {})
    합격자 = {str(p['_id']): p for p in participants_collection.find({'status': '합격'})}
    applicants_dict = 합격자
    # Use the stored weights, fallback to default weights
    from genetic_algorithm import weights as default_weights, fitness
    weights_to_use = weights_used if weights_used else default_weights
    scores = []
    for group in grouping:
        if not group:
            scores.append(0)
            continue
        score = fitness([group], applicants_dict, weights_to_use)
        scores.append(score)
    return jsonify({'scores': scores})

@app.route('/api/redistribute_groups', methods=['POST'])
@professor_required
def api_redistribute_groups():
    data = request.get_json()
    new_weights = data.get('weights')
    if not new_weights:
        return jsonify({'error': 'No weights provided'}), 400
    # Convert all weights to int
    for k in new_weights:
        try:
            new_weights[k] = int(new_weights[k])
        except Exception:
            new_weights[k] = 1
    합격자 = list(participants_collection.find({'status': '합격'}))
    from genetic_algorithm import genetic_algorithm, fitness
    grouping = genetic_algorithm(합격자, new_weights, num_groups=4)
    # Convert ObjectIds to strings for session
    grouping_str = [[str(aid) for aid in group] for group in grouping]
    session['latest_grouping'] = grouping_str
    session['latest_weights'] = new_weights  # Store the new weights used
    # Prepare group info for frontend, serializing ObjectIds
    합격자_dict = {str(p['_id']): p for p in 합격자}
    def serialize_participant(p):
        if not p:
            return None
        p = dict(p)
        if '_id' in p:
            p['_id'] = str(p['_id'])
        return p
    groups = []
    scores = []
    for group in grouping_str:
        group_info = [serialize_participant(합격자_dict.get(str(aid))) for aid in group if 합격자_dict.get(str(aid))]
        groups.append(group_info)
        if group:
            scores.append(fitness([group], 합격자_dict, new_weights))
        else:
            scores.append(0)
    return jsonify({'groups': groups, 'scores': scores})

# --- Run the application ---
if __name__ == '__main__':
    app.run(debug=True)