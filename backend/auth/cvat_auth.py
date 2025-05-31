#backend/auth/cvat_auth.py
import requests

def authenticate_with_cvat(username, password):
    """
    Authenticate with CVAT using username and password.
    """
    url = "https://app.cvat.ai/api/auth/login"
    
    # The correct payload format for CVAT authentication
    payload = {
        'username': username,
        'password': password
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code != 200:
        # Log the actual error message from CVAT for debugging
        print(f"CVAT authentication failed: {response.text}")
        raise Exception("Invalid credentials or failed to authenticate with CVAT")
    
    # Return token data
    return response.json()
