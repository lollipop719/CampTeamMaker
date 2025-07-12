# 🏕️ Camp Team Maker - Google OAuth2 Setup Guide

## 📋 Overview

This guide will help you set up Google OAuth2 authentication with role-based access control for your Camp Team Maker application.

## 🔧 Prerequisites

1. **Google Cloud Console Account**
2. **Python 3.7+**
3. **MongoDB Database** (already configured)

## 🚀 Step-by-Step Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Google Cloud Console Setup

#### 2.1 Create a New Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google+ API and Gmail API

#### 2.2 Configure OAuth2 Credentials
1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth 2.0 Client IDs**
3. Choose **Web application**
4. Set the following:
   - **Name**: Camp Team Maker
   - **Authorized JavaScript origins**: 
     - `http://localhost:5000` (for development)
     - `https://yourdomain.com` (for production)
   - **Authorized redirect URIs**:
     - `http://localhost:5000/callback` (for development)
     - `https://yourdomain.com/callback` (for production)

#### 2.3 Get Your Credentials
After creating, you'll get:
- **Client ID**
- **Client Secret**

### 3. Environment Variables Setup

Create a `.env` file in your project root:

```env
# Google OAuth2
GOOGLE_CLIENT_ID=your-client-id-here
GOOGLE_CLIENT_SECRET=your-client-secret-here
GOOGLE_REDIRECT_URI=http://localhost:5000/callback

# MongoDB (already configured)
MONGO_URI=your-mongodb-uri
MONGO_DB_NAME=molipDB

# Gmail (for fallback email sending)
GMAIL_USER=your-admin-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
```

### 4. Role Configuration

#### 4.1 Default Role Assignment
The system automatically assigns roles based on email domains:

- **@kaist.ac.kr** → Professor role
- **Other domains** → Student role

#### 4.2 Custom Role Assignment
To add specific emails as professors, edit the `determine_user_role()` function in `app.py`:

```python
def determine_user_role(email):
    if email.endswith('@kaist.ac.kr'):
        return 'professor'
    elif email in ['admin@example.com', 'professor@example.com']:  # Add your emails
        return 'professor'
    else:
        return 'student'
```

### 5. Gmail App Password Setup

For email sending functionality, users need to create Gmail App Passwords:

1. Go to [Google Account Settings](https://myaccount.google.com/)
2. Navigate to **Security** > **2-Step Verification**
3. Scroll down to **App passwords**
4. Generate a new app password for "Mail"
5. Use this password in the email popup

## 🔐 Access Control

### Student Access
- ✅ View home page
- ✅ Register as participant
- ❌ View participant list
- ❌ Access organize page
- ❌ Send bulk emails

### Professor Access
- ✅ All student permissions
- ✅ View participant list
- ✅ Access organize page
- ✅ Update participant status
- ✅ Send bulk emails
- ✅ Run AI categorization

## 📧 Email Sending

### Method 1: User Credentials (Recommended)
Users enter their own Gmail credentials in the email popup:
- Gmail address
- App password (not regular password)

### Method 2: Admin Credentials (Fallback)
If no user credentials provided, uses environment variables:
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`

## 🚀 Running the Application

```bash
python app.py
```

Visit `http://localhost:5000` and click "Google로 로그인하기"

## 🔧 Troubleshooting

### Common Issues

1. **"Invalid redirect URI"**
   - Check that your redirect URI matches exactly in Google Cloud Console
   - Ensure no trailing slashes

2. **"Client ID not found"**
   - Verify your environment variables are set correctly
   - Check that the `.env` file is in the project root

3. **"Email sending failed"**
   - Ensure Gmail App Password is correct
   - Check that 2-Factor Authentication is enabled
   - Verify the email has "Less secure app access" or uses App Password

4. **"Role not assigned correctly"**
   - Check the `determine_user_role()` function
   - Verify email domain logic

### Debug Mode

For development, the app runs in debug mode. Check the console for detailed error messages.

## 🔒 Security Considerations

1. **Never commit credentials to version control**
2. **Use environment variables for all secrets**
3. **Enable HTTPS in production**
4. **Regularly rotate app passwords**
5. **Monitor OAuth consent screen usage**

## 📱 Production Deployment

For production deployment:

1. Update redirect URIs to your domain
2. Set up HTTPS
3. Use production MongoDB
4. Configure proper logging
5. Set up monitoring

## 🎯 Features Summary

- ✅ Google OAuth2 Authentication
- ✅ Role-based Access Control
- ✅ Student Registration
- ✅ Professor Dashboard
- ✅ Participant Management
- ✅ AI-powered Categorization
- ✅ Bulk Email Sending
- ✅ Real-time Statistics
- ✅ Mobile-responsive UI

## 📞 Support

If you encounter issues:
1. Check the console logs
2. Verify all environment variables
3. Test with a simple Gmail account first
4. Ensure all dependencies are installed

---

**Happy Camp Team Making! 🏕️** 