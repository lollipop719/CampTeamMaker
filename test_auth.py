#!/usr/bin/env python3
"""
Simple test script to verify Google OAuth2 authentication setup
"""

import os
from app import app, determine_user_role

def test_role_assignment():
    """Test role assignment logic"""
    print("🧪 Testing role assignment...")
    
    # Test cases
    test_cases = [
        ("professor@kaist.ac.kr", "professor"),
        ("student@gmail.com", "student"),
        ("admin@example.com", "student"),  # Will be student unless added to custom list
        ("user@yahoo.com", "student")
    ]
    
    for email, expected_role in test_cases:
        actual_role = determine_user_role(email)
        status = "✅" if actual_role == expected_role else "❌"
        print(f"{status} {email} → {actual_role} (expected: {expected_role})")

def test_environment_variables():
    """Test environment variables setup"""
    print("\n🔧 Testing environment variables...")
    
    required_vars = [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET", 
        "GOOGLE_REDIRECT_URI"
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value and value != f"your-{var.lower()}-here":
            print(f"✅ {var} is set")
        else:
            print(f"❌ {var} is not set or has default value")

def test_app_configuration():
    """Test Flask app configuration"""
    print("\n🚀 Testing Flask app configuration...")
    
    try:
        with app.test_client() as client:
            # Test home route
            response = client.get('/')
            if response.status_code == 200:
                print("✅ Home route works")
            else:
                print(f"❌ Home route failed: {response.status_code}")
            
            # Test login route
            response = client.get('/login')
            if response.status_code == 200:
                print("✅ Login route works")
            else:
                print(f"❌ Login route failed: {response.status_code}")
                
    except Exception as e:
        print(f"❌ App configuration error: {e}")

if __name__ == "__main__":
    print("🏕️ Camp Team Maker - Authentication Test")
    print("=" * 50)
    
    test_role_assignment()
    test_environment_variables()
    test_app_configuration()
    
    print("\n" + "=" * 50)
    print("📋 Next Steps:")
    print("1. Set up Google Cloud Console OAuth2 credentials")
    print("2. Create .env file with your credentials")
    print("3. Run: python app.py")
    print("4. Visit: http://localhost:5000")
    print("\n📖 See SETUP_GUIDE.md for detailed instructions") 