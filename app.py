from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from pymongo import MongoClient
from bson.objectid import ObjectId # Import ObjectId to work with MongoDB _id
import os
import google.generativeai as genai # Import the Gemini library
from werkzeug.utils import secure_filename
from flask import send_from_directory # Re-add for serving uploaded files

app = Flask(__name__)
app.secret_key = 'VeRYSECreT032&$90kdl2l1kdmfnt'

# --- MongoDB Configuration ---
# Use environment variables for sensitive info in production
# For local dev, you can hardcode, but ENV variables are best practice
MONGO_URI = "mongodb+srv://sciencekid719:WD3zXfPzYdTDpQh2@campteammakercluster.yikpgdv.mongodb.net/?retryWrites=true&w=majority&appName=campTeamMakerCluster"
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "campTeamMakerDB") # Your database name

# Initialize MongoDB client
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME] # Access the specific database

# Get a reference to your participants collection
participants_collection = db.participants

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

# --- Routes ---

@app.route('/')
def home():
    # Example: Count participants from MongoDB
    num_participants = participants_collection.count_documents({})
    return f"Hello, Camp Team Builder! We have {num_participants} participants registered."

# Define a route for participant registration (GET to display form)
@app.route('/register', methods=['GET'])
def register_form():
    return render_template('register.html') # Render the HTML form from templates/


@app.route('/register', methods=['POST'])
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
def list_participants():
    # Sort participants by average score in descending order (highest first)
    participants = list(participants_collection.find({}).sort('avg_score', -1))
    
    # Calculate statistics for the floating box
    total_participants = len(participants)
    
    # Pass/Fail statistics
    pass_count = sum(1 for p in participants if p.get('status') == '합격')
    fail_count = sum(1 for p in participants if p.get('status') == '불합격')
    pending_count = total_participants - pass_count - fail_count
    
    # Gender and university statistics
    kaist_male = sum(1 for p in participants if p.get('university') == '카이스트' and p.get('gender') == '남자')
    kaist_female = sum(1 for p in participants if p.get('university') == '카이스트' and p.get('gender') == '여자')
    other_male = sum(1 for p in participants if p.get('university') != '카이스트' and p.get('gender') == '남자')
    other_female = sum(1 for p in participants if p.get('university') != '카이스트' and p.get('gender') == '여자')
    
    statistics = {
        'total': total_participants,
        'pass': pass_count,
        'fail': fail_count,
        'pending': pending_count,
        'kaist_male': kaist_male,
        'kaist_female': kaist_female,
        'other_male': other_male,
        'other_female': other_female
    }
    
    return render_template('participants_list.html', participants=participants, statistics=statistics)

@app.route('/update_status/<participant_id>', methods=['POST'])
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
            # Get updated statistics
            participants = list(participants_collection.find({}))
            total_participants = len(participants)
            pass_count = sum(1 for p in participants if p.get('status') == '합격')
            fail_count = sum(1 for p in participants if p.get('status') == '불합격')
            pending_count = total_participants - pass_count - fail_count
            
            kaist_male = sum(1 for p in participants if p.get('university') == '카이스트' and p.get('gender') == '남자')
            kaist_female = sum(1 for p in participants if p.get('university') == '카이스트' and p.get('gender') == '여자')
            other_male = sum(1 for p in participants if p.get('university') != '카이스트' and p.get('gender') == '남자')
            other_female = sum(1 for p in participants if p.get('university') != '카이스트' and p.get('gender') == '여자')
            
            response_data = {
                'success': True,
                'message': f'Status updated to {status}',
                'statistics': {
                    'total': total_participants,
                    'pass': pass_count,
                    'fail': fail_count,
                    'pending': pending_count,
                    'kaist_male': kaist_male,
                    'kaist_female': kaist_female,
                    'other_male': other_male,
                    'other_female': other_female
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

@app.route('/edit_participant/<participant_id>', methods=['GET', 'POST'])
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

# --- Run the application ---
if __name__ == '__main__':
    app.run(debug=True)