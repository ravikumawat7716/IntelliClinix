from flask_pymongo import PyMongo
from pymongo.collection import Collection
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import os
from bson import ObjectId
from flask import current_app
from pymongo import MongoClient, ASCENDING

# MongoDB instance
mongo = PyMongo()

def get_db():
    """Get database instance."""
    if 'db' not in current_app.config:
        client = MongoClient(current_app.config['MONGO_URI'])
        current_app.config['db'] = client.get_database()
    return current_app.config['db']


def get_users_collection():
    """Get users collection."""
    return get_db()['users']


def get_uploads_collection():
    """Get uploads collection."""
    return get_db()['uploads']


def get_inference_collection():
    """Get inference jobs collection."""
    return get_db()['inference_jobs']


def init_db(app):
    """Initialize database with required collections and indexes."""
    with app.app_context():
        try:
            # Connect to MongoDB
            client = MongoClient(app.config['MONGO_URI'])
            db = client.get_database()
            app.config['db'] = db
            
            # Initialize users collection
            users = db['users']
            users.create_index([('username', ASCENDING)], unique=True)
            
            # Initialize uploads collection
            uploads = db['uploads']
            uploads.create_index([('job_id', ASCENDING)], unique=True)
            uploads.create_index([('username', ASCENDING), ('created_at', ASCENDING)])
            
            # Initialize inference jobs collection
            inference_jobs = db['inference_jobs']
            inference_jobs.create_index([('job_id', ASCENDING)], unique=True)
            inference_jobs.create_index([('username', ASCENDING), ('created_at', ASCENDING)])
            
            print("Database initialized successfully")
            return True
            
        except Exception as e:
            print(f"Error initializing database: {str(e)}")
            return False


def create_user(username: str, password: str) -> Dict[str, Any]:
    """
    Create a new user in the database.
    """
    users_collection = get_users_collection()
    
    user_data = {
        "username": username,
        "password": password,  # Should be hashed before calling this function
        "created_at": datetime.now(timezone.utc).timestamp() * 1000 ,
        "last_login": datetime.now(timezone.utc).timestamp() * 1000 ,
        "is_active": True,
        "cvat_verified": True,  # Since they authenticated with CVAT
        "uploads": []  # List to store upload IDs
    }
    
    result = users_collection.insert_one(user_data)
    user_data['_id'] = result.inserted_id
    return user_data


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a user by username.
    """
    users_collection = get_users_collection()
    return users_collection.find_one({"username": username})


def update_last_login(username: str) -> None:
    """
    Update the last login timestamp for a user.
    """
    users_collection = get_users_collection()
    users_collection.update_one(
        {"username": username},
        {"$set": {"last_login": datetime.now(timezone.utc).timestamp() * 1000 }}
    )


def is_user_validated(username: str) -> bool:
    """
    Check if a user is validated by CVAT.
    """
    user = get_user_by_username(username)
    return user is not None and user.get("cvat_verified", False)


def create_upload(username: str, file_path: str, config: str, job_id: str) -> Dict[str, Any]:
    """
    Create a new upload record in the database.
    """
    uploads_collection = get_uploads_collection()
    
    upload_data = {
        "username": username,
        "file_path": file_path,
        "config": config,  # "2d" or "3d_fullres"
        "job_id": job_id,
        "created_at": datetime.now(timezone.utc).timestamp() * 1000 ,
        "status": "pending",  # pending, processing, completed, failed
        "result_path": None  # Will be updated when processing is complete
    }
    
    result = uploads_collection.insert_one(upload_data)
    upload_data['_id'] = result.inserted_id
    
    # Update user's uploads list
    users_collection = get_users_collection()
    users_collection.update_one(
        {"username": username},
        {"$push": {"uploads": result.inserted_id}}
    )
    
    return upload_data


def create_inference_job(username: str, job_id: str, config: str) -> Dict[str, Any]:
    """
    Create a new inference job record.
    """
    inference_collection = get_inference_collection()
    
    job_data = {
        "username": username,
        "job_id": job_id,
        "config": config,
        "created_at": datetime.now(timezone.utc).timestamp() * 1000,
        "status": "pending",
        "started_at": None,
        "completed_at": None,
        "error": None
    }
    
    result = inference_collection.insert_one(job_data)
    job_data['_id'] = result.inserted_id
    return job_data


def get_user_uploads(username: str) -> List[Dict[str, Any]]:
    """
    Get all uploads for a specific user.
    """
    uploads_collection = get_uploads_collection()
    return list(uploads_collection.find({"username": username}).sort("created_at", -1))


def get_upload_by_job_id(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get upload details by job ID.
    """
    uploads_collection = get_uploads_collection()
    return uploads_collection.find_one({"job_id": job_id})


def update_upload_status(job_id: str, status: str, result_path: Optional[str] = None) -> None:
    """
    Update the status and result path of an upload.
    """
    uploads_collection = get_uploads_collection()
    update_data = {"status": status}
    if result_path:
        update_data["result_path"] = result_path
    
    uploads_collection.update_one(
        {"job_id": job_id},
        {"$set": update_data}
    )


def update_inference_status(job_id: str, status: str, error: Optional[str] = None) -> None:
    """
    Update the status of an inference job.
    """
    inference_collection = get_inference_collection()
    update_data: Dict[str, Any] = {
        "status": status,
        "error": error
    }
    
    if status == "processing":
        update_data["started_at"] = datetime.now(timezone.utc).timestamp() * 1000 
    elif status in ["completed", "failed"]:
        update_data["completed_at"] = datetime.now(timezone.utc).timestamp() * 1000 
    
    inference_collection.update_one(
        {"job_id": job_id},
        {"$set": update_data}
    )


def delete_upload(job_id: str, username: str) -> bool:
    """
    Delete an upload and its associated inference job.
    """
    uploads_collection = get_uploads_collection()
    inference_collection = get_inference_collection()
    
    # Get upload details
    upload = uploads_collection.find_one({"job_id": job_id, "username": username})
    if not upload:
        return False
    
    # Delete the physical files if they exist
    if upload.get("file_path") and os.path.exists(upload["file_path"]):
        os.remove(upload["file_path"])
    if upload.get("result_path") and os.path.exists(upload["result_path"]):
        os.remove(upload["result_path"])
    
    # Delete from database
    uploads_collection.delete_one({"job_id": job_id})
    inference_collection.delete_one({"job_id": job_id})
    
    return True
