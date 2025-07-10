from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
import os

app = Flask(__name__)

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


# Define a route to handle participant registration form submission (POST)
@app.route('/register', methods=['POST'])
def register_submit():
    # Get data from the form
    participant_data = {
        "name": request.form['name'],
        "gender": request.form['gender'],
        "mbti": request.form.get('mbti', ''), # .get() allows optional fields
        "school": request.form.get('school', ''),
        "major": request.form.get('major', ''),
        "age": int(request.form.get('age', 0)) if request.form.get('age') else None, # Convert to int, handle empty
        # "region": request.form.get('region', ''), # ADDED
        "dev_exp": request.form.get('dev_exp', ''), # CHANGED: Now a string input
        "intern_exp": request.form.get('intern_exp', ''), # ADDED
        "immersion_exp": request.form.get('immersion_exp', ''), # ADDED
        "club_exp": request.form.get('club_exp', ''), # ADDED
        "hobbies": [h.strip() for h in request.form.get('hobbies', '').split(',') if h.strip()], # Split by comma into list
        # "tmi": request.form.get('tmi', ''), # REMOVED: TMI field
        "overseas_exp": request.form.get('overseas_exp', '무'),
    }

    # Handle conditional fields for overseas_exp
    if participant_data["overseas_exp"] == "유":
        participant_data["overseas_details"] = {
            "duration": request.form.get('overseas_duration', ''),
            "continent": request.form.get('overseas_continent', '')
        }
    else:
        participant_data["overseas_details"] = None # Or omit this field entirely

    # Save participant data to MongoDB
    try:
        result = participants_collection.insert_one(participant_data)
        print(f"Inserted participant: {participant_data['name']} with ID: {result.inserted_id}")
        # Redirect to a success page or the participant list
        return redirect(url_for('list_participants')) # Redirect to the list view
    except Exception as e:
        print(f"Error registering participant: {e}")
        return f"Error registering participant: {e}", 500


@app.route('/participants')
def list_participants():
    participants = participants_collection.find({}) # Fetch all participants
    # Render a template to display participants nicely
    return render_template('participants_list.html', participants=participants)


# --- Run the application ---
if __name__ == '__main__':
    app.run(debug=True)