# # backend/auth/inference.py
# from flask import Blueprint, request, jsonify, current_app, send_file
# from werkzeug.utils import secure_filename
# import os
# import uuid
# import tempfile
# import requests
# from datetime import datetime
# from .database import (
#     create_upload,
#     create_inference_job,
#     get_upload_by_job_id,
#     update_upload_status,
#     update_inference_status
# )

# inference_bp = Blueprint('inference', __name__)

# def allowed_file(filename):
#     """
#     Check if the file extension is allowed.
#     """
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'zip'

# @inference_bp.route('/upload', methods=['POST'])
# def upload_file():
#     """
#     Handle file upload and create inference job.
#     """
#     if 'file' not in request.files:
#         return jsonify({'success': False, 'error': 'No file part'}), 400
    
#     file = request.files['file']
#     config = request.form.get('config', '3d_fullres')
    
#     if file.filename == '':
#         return jsonify({'success': False, 'error': 'No selected file'}), 400
    
#     if not allowed_file(file.filename):
#         return jsonify({'success': False, 'error': 'Only ZIP files are allowed'}), 400
    
#     try:

#         # Generate unique job ID
#         job_id = str(uuid.uuid4())
        
#         # Create upload directory if it doesn't exist
#         upload_folder = os.path.join(current_app.root_path, 'uploads', 'inference_jobs', job_id)
#         os.makedirs(upload_folder, exist_ok=True)
        
#         # Save file
#         filename = secure_filename(file.filename)
#         file_path = os.path.join(upload_folder, filename)
#         file.save(file_path)
        
#         # Create upload record
#         username = request.form.get('username')  # Get username from form data
#         if not username:
#             return jsonify({'success': False, 'error': 'Username is required'}), 400
        
#         upload_data = create_upload(
#             username=username,
#             file_path=file_path,
#             config=config,
#             job_id=job_id
#         )
        
#         # Create inference job record
#         inference_job = create_inference_job(
#             username=username,
#             job_id=job_id,
#             config=config
#         )
        
#         return jsonify({
#             'success': True,
#             'job_id': job_id,
#             'config': config
#         }), 201
        
#     except Exception as e:
#         print(f"Error in upload: {str(e)}")
#         return jsonify({'success': False, 'error': str(e)}), 500

# @inference_bp.route('/run', methods=['POST'])
# def run_inference():
#     """
#     Run inference on uploaded file.
#     """
#     data = request.json
#     job_id = data.get('job_id')
#     config = data.get('config')
    
#     if not job_id:
#         return jsonify({'success': False, 'error': 'Job ID is required'}), 400
    
#     try:
#         # Get upload details
#         upload = get_upload_by_job_id(job_id)
#         if not upload:
#             return jsonify({'success': False, 'error': 'Upload not found'}), 404
        
#         # Update status to processing
#         update_upload_status(job_id, "processing")
#         update_inference_status(job_id, "processing")
        
#         # TODO: Add your actual inference processing logic here
#         # For now, we'll just simulate processing
        
#         # Create result directory
#         result_folder = os.path.join(current_app.root_path, 'uploads', 'inference_results', job_id)
#         os.makedirs(result_folder, exist_ok=True)
#         result_path = os.path.join(result_folder, f"result_{job_id}.nii.gz")
        
#         # Simulate creating a result file
#         with open(result_path, 'wb') as f:
#             f.write(b'Simulated NIfTI result')
        
#         # Update status to completed
#         update_upload_status(job_id, "completed", result_path)
#         update_inference_status(job_id, "completed")
        
#         # Return the result file
#         return send_file(
#             result_path,
#             as_attachment=True,
#             download_name=f"segmentation_result_{job_id}.nii.gz",
#             mimetype='application/gzip'
#         )
        
#     except Exception as e:
#         print(f"Error in inference: {str(e)}")
#         update_upload_status(job_id, "failed")
#         update_inference_status(job_id, "failed", str(e))
#         return jsonify({'success': False, 'error': str(e)}), 500

# @inference_bp.route('/status/<job_id>', methods=['GET'])
# def get_status(job_id):
#     """
#     Get status of an inference job.
#     """
#     upload = get_upload_by_job_id(job_id)
#     if not upload:
#         return jsonify({'success': False, 'error': 'Job not found'}), 404
    
#     return jsonify({
#         'success': True,
#         'status': upload['status'],
#         'config': upload['config'],
#         'created_at': upload['created_at'].isoformat()
#     })

# def download_cvat_annotations(task_id: str, cvat_server: str = "http://localhost:5000", export_format: str = 'CVAT') -> tuple:
#     """
#     Download annotations from CVAT server.
#     """
#     if not task_id:
#         return jsonify({"error": "The 'task_id' parameter is required."}), 400

#     url = f"{cvat_server}/api/tasks/{task_id}/annotations?format={export_format}"

#     try:
#         response = requests.get(url)
#         response.raise_for_status()

#         temp_folder = tempfile.mkdtemp(prefix="cvat_download_")
#         file_name = f"task_{task_id}_annotations.xml"
#         file_path = os.path.join(temp_folder, file_name)

#         with open(file_path, "wb") as f:
#             f.write(response.content)

#         return send_file(file_path, as_attachment=True, download_name=file_name), 200
    
#     except requests.HTTPError as http_err:
#         return jsonify({"error": f"HTTP error occurred: {str(http_err)}"}), 500
#     except Exception as err:
#         return jsonify({"error": f"An error occurred: {str(err)}"}), 500

# @inference_bp.route('/download-cvat-annotations', methods=['GET'])
# def get_cvat_annotations():
#     task_id = request.args.get('task_id')
#     export_format = request.args.get('format', 'CVAT')
#     cvat_server = current_app.config.get('CVAT_SERVER_URL', 'http://localhost:5000')
#     return download_cvat_annotations(task_id, cvat_server, export_format) 
