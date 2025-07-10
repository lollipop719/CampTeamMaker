from flask import Flask, render_template, request, redirect, url_for

# Create a Flask web application instance
app = Flask(__name__)

# --- Routes ---

# Define a route for the homepage
@app.route('/')
def home():
    return "Hello, Camp Team Builder!"

# Define a route for participant registration (GET to display form)
@app.route('/register', methods=['GET'])
def register_form():
    # In a real app, you'd render an HTML template here
    return "<h2>Register Participant</h2><form method='POST' action='/register'><label for='name'>Name:</label><input type='text' id='name' name='name'><br><input type='submit' value='Register'></form>"

# Define a route to handle participant registration form submission (POST)
@app.route('/register', methods=['POST'])
def register_submit():
    participant_name = request.form['name']
    # In a real app, you'd save this to your SQLite DB
    return f"Participant '{participant_name}' registered successfully! (Not saved to DB yet)"

# --- Run the application ---
if __name__ == '__main__':
    # In a development environment, you can run with debug=True
    # This allows auto-reloading on code changes and provides a debugger
    app.run(debug=True)