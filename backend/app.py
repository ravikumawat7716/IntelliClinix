# backend/app.py
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from auth.database import init_db
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Define base directory as current working directory
    base_dir = os.path.abspath(os.getcwd())

    # Configure application folders
    app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'backend', 'uploads')
    app.config['PREDICTIONS_FOLDER'] = os.path.join(base_dir, 'backend', 'predictions')
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    # Configure additional directories used by CVAT routes:
    # - TEMP_UPLOADS: used to store data uploaded to CVAT.
    # - TEMP_RESULTS: used to store prediction results.
    # - ANNOTATION_FILES: intermediate storage for annotation JSON files.
    # - CREATED_TASKS: storage for task info created using the /create-task route.
    # - CORRECTED_TASKS: storage for tasks processed via the /send-to-dataset route.
    # - NIFTIS_FOLDER: a subdirectory of TEMP_UPLOADS where raw NIfTI files are stored.
    app.config['TEMP_UPLOADS'] = os.path.join(base_dir, 'temp_uploads')
    app.config['TEMP_RESULTS'] = os.path.join(base_dir, 'temp_results')
    app.config['ANNOTATION_FILES'] = os.path.join(base_dir, 'annotation_files')
    app.config['CREATED_TASKS'] = os.path.join(base_dir, 'created_tasks')
    app.config['CORRECTED_TASKS'] = os.path.join(base_dir, 'corrected_tasks')
    app.config['NIFTIS_FOLDER'] = os.path.join(app.config['TEMP_UPLOADS'], 'niftis')

    # Ensure necessary directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PREDICTIONS_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TEMP_UPLOADS'], exist_ok=True)
    os.makedirs(app.config['TEMP_RESULTS'], exist_ok=True)
    os.makedirs(app.config['ANNOTATION_FILES'], exist_ok=True)
    os.makedirs(app.config['CREATED_TASKS'], exist_ok=True)
    os.makedirs(app.config['CORRECTED_TASKS'], exist_ok=True)
    os.makedirs(app.config['NIFTIS_FOLDER'], exist_ok=True)

    # CORS setup with better security
    CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}},
         supports_credentials=True)

    # Initialize database (MongoDB setup)
    init_db(app)

    # Register blueprints with their URL prefixes
    with app.app_context():
        from auth.routes import auth_bp
        from inference.routes import inference_bp   # Inference now handles temp_results functionality
        from cvat.routes import cvat_bp
        from nnunet.routes import nnunet_bp
        app.register_blueprint(nnunet_bp)
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(inference_bp, url_prefix='/inference')
        app.register_blueprint(cvat_bp, url_prefix='/cvat')

    @app.route('/')
    def index():
        return jsonify({'status': 'Flask backend is running'})

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5328, debug=True)