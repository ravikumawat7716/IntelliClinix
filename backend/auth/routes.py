from flask import Blueprint, request, jsonify, session
from bson.objectid import ObjectId  # Import ObjectId for serialization
from .cvat_auth import authenticate_with_cvat
from .database import (
    get_users_collection,
    create_user,
    get_user_by_username,
    update_last_login,
    is_user_validated
)
import bcrypt

auth_bp = Blueprint('auth', __name__)

def serialize_objectid(data):
    """
    Helper function to convert ObjectId to string recursively in a dictionary.
    """
    if isinstance(data, dict):
        return {key: serialize_objectid(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [serialize_objectid(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    return data

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Endpoint to authenticate with CVAT using username and password.
    If the user is new and validated by CVAT, they will be added to the database.
    """
    print("\n=== Login Request Received ===")
    data = request.json
    print(f"Request data: {data}")
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        print("Error: Missing username or password")
        return jsonify({'error': 'Username and password are required'}), 400
    
    try:
        print(f"\nAttempting CVAT authentication for user: {username}")
        # Authenticate with CVAT
        token_data = authenticate_with_cvat(username, password)
        print(f"CVAT authentication successful: {token_data}")
        token = token_data.get('key')
        
        # Check if user exists in MongoDB
        print(f"\nChecking if user exists in database: {username}")
        existing_user = get_user_by_username(username)
        
        if not existing_user:
            print(f"User {username} not found in database. Creating new user...")
            # Create new user if they don't exist
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            new_user = create_user(username, hashed_password)
            print(f"New user created successfully: {new_user}")
        else:
            print(f"User {username} found in database. Updating last login...")
            # Update last login for existing user
            update_last_login(username)
            print(f"Last login updated for user: {username}")
        
        # Store token in session
        session['cvat_token'] = token
        session['username'] = username
        print(f"\nSession created for user: {username}")
        
        return jsonify({
            'token': token,
            'username': username,
            'is_new_user': not existing_user
        }), 200
    
    except Exception as e:
        print(f"\nError in login process: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/user', methods=['GET'])
def get_user():
    """
    Endpoint to get current user information.
    """
    username = session.get('username')
    if not username:
        return jsonify({'authenticated': False}), 401
    
    user = get_user_by_username(username)
    if not user:
        return jsonify({'authenticated': False}), 401
    
    # Serialize ObjectId and remove sensitive information
    user.pop('password', None)
    serialized_user = serialize_objectid(user)
    
    return jsonify({
        'authenticated': True,
        'user': serialized_user
    })

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Endpoint to logout the current user.
    """
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200
