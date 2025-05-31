from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/dep_users'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev'
    
    # nnUNet paths
    NNUNET_RAW_DATA_BASE = os.environ.get('NNUNET_RAW_DATA_BASE') or '~/Development/DEP_electrical/nnUNet_raw'
    NNUNET_PREPROCESSED = os.environ.get('NNUNET_PREPROCESSED') or '~/Development/DEP_electrical/nnUNet_preprocessed'
    NNUNET_RESULTS_FOLDER = os.environ.get('NNUNET_RESULTS_FOLDER') or '~/Development/DEP_electrical/nnUNet_results'
    
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TEMP_UPLOADS_PATH = os.path.join(BASE_DIR, "temp_uploads")
    TEMP_RESULTS_PATH = os.path.join(BASE_DIR, "temp_results")

    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    
    print("Loaded MONGO_URI:", MONGO_URI)


# Export these variables at the module level so they can be imported directly
BASE_DIR = Config.BASE_DIR
TEMP_UPLOADS_PATH = Config.TEMP_UPLOADS_PATH
TEMP_RESULTS_PATH = Config.TEMP_RESULTS_PATH
NNUNET_RAW_DATA_BASE = Config.NNUNET_RAW_DATA_BASE
NNUNET_PREPROCESSED = Config.NNUNET_PREPROCESSED
NNUNET_RESULTS_FOLDER = Config.NNUNET_RESULTS_FOLDER
UPLOAD_FOLDER = Config.UPLOAD_FOLDER
MAX_CONTENT_LENGTH = Config.MAX_CONTENT_LENGTH
