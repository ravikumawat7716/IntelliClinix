# # backend/auth/uploads.py
# from flask import Blueprint, request, jsonify, current_app, send_file
# from werkzeug.utils import secure_filename
# import os
# import zipfile
# from .database import (
#     create_upload,
#     get_user_uploads,
#     get_upload_by_id,
#     update_upload_status,
#     delete_upload
# )

# uploads_bp = Blueprint('uploads', __name__)

# def allowed_file(filename):
#     """
#     Check if the file extension is allowed.
#     """
#     ALLOWED_EXTENSIONS = {'zip'}  # Only ZIP files are allowed
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# def validate_zip_contents(file_path):
#     """
#     Validate that the ZIP file contains valid medical images.
#     """
#     try:
#         with zipfile.ZipFile(file_path, 'r') as zip_ref:
#             # Check file size (500MB limit)
#             total_size = sum(file_info.file_size for file_info in zip_ref.filelist)
#             if total_size > 500 * 1024 * 1024:  # 500MB in bytes
#                 return False, "ZIP file exceeds 500MB limit"
            
#             # Check for valid image files
#             valid_extensions = {'.png', '.nii', '.nii.gz'}
#             has_valid_files = False
            
#             for file_info in zip_ref.filelist:
#                 ext = os.path.splitext(file_info.filename)[1].lower()
#                 if ext in valid_extensions:
#                     has_valid_files = True
#                     break
            
#             if not has_valid_files:
#                 return False, "ZIP file must contain PNG or NIfTI images"
            
#             return True, "Valid medical image archive"
#     except Exception as e:
#         return False, f"Invalid ZIP file: {str(e)}"

# @uploads_bp.route('/upload', methods=['POST'])
# def upload_file():
#     """
#     Handle file upload and link it with the current user.
#     """
#     if 'file' not in request.files:
#         return jsonify({'error': 'No file part'}), 400
    
#     file = request.files['file']
#     if file.filename == '':
#         return jsonify({'error': 'No selected file'}), 400
    
#     if file and allowed_file(file.filename):
#         # Get username from session
#         username = request.form.get('username')
#         if not username:
#             return jsonify({'error': 'Username is required'}), 400
        
#         # Create uploads directory if it doesn't exist
#         upload_folder = os.path.join(current_app.root_path, 'uploads', username)
#         os.makedirs(upload_folder, exist_ok=True)
        
#         # Save file
#         filename = secure_filename(file.filename)
#         file_path = os.path.join(upload_folder, filename)
#         file.save(file_path)
        
#         # Validate ZIP contents
#         is_valid, message = validate_zip_contents(file_path)
#         if not is_valid:
#             # Delete the file if validation fails
#             os.remove(file_path)
#             return jsonify({'error': message}), 400
        
#         # Create upload record in database
#         upload_data = create_upload(
#             username=username,
#             file_path=file_path,
#             file_name=filename,
#             file_type=file.content_type
#         )
        
#         # Update status to ready for processing
#         update_upload_status(upload_data['_id'], 'Ready for Processing')
        
#         return jsonify({
#             'message': 'File uploaded successfully',
#             'upload': upload_data
#         }), 201
    
#     return jsonify({'error': 'Only ZIP files are allowed'}), 400

# @uploads_bp.route('/uploads', methods=['GET'])
# def get_uploads():
#     """
#     Get all uploads for the current user.
#     """
#     username = request.args.get('username')
#     if not username:
#         return jsonify({'error': 'Username is required'}), 400
    
#     uploads = get_user_uploads(username)
#     # Format the response to match frontend expectations
#     formatted_uploads = []
#     for upload in uploads:
#         formatted_upload = {
#             'name': upload['file_name'],
#             'size': str(os.path.getsize(upload['file_path'])),
#             'timestamp': upload['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
#             'studyId': str(upload['_id']),  # Using MongoDB ID as study ID
#             'status': upload['status'],
#             'type': 'Medical Image Archive',
#             'estimatedImages': 0  # This would need to be calculated based on ZIP contents
#         }
#         formatted_uploads.append(formatted_upload)
    
#     return jsonify({'uploads': formatted_uploads}), 200

# @uploads_bp.route('/uploads/<upload_id>', methods=['GET'])
# def get_upload(upload_id):
#     """
#     Get details of a specific upload.
#     """
#     upload = get_upload_by_id(upload_id)
#     if not upload:
#         return jsonify({'error': 'Upload not found'}), 404
    
#     # Format the response to match frontend expectations
#     formatted_upload = {
#         'name': upload['file_name'],
#         'size': str(os.path.getsize(upload['file_path'])),
#         'timestamp': upload['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
#         'studyId': str(upload['_id']),
#         'status': upload['status'],
#         'type': 'Medical Image Archive',
#         'estimatedImages': 0
#     }
    
#     return jsonify({'upload': formatted_upload}), 200

# @uploads_bp.route('/uploads/<upload_id>/download', methods=['GET'])
# def download_upload(upload_id):
#     """
#     Download a specific upload.
#     """
#     upload = get_upload_by_id(upload_id)
#     if not upload:
#         return jsonify({'error': 'Upload not found'}), 404
    
#     if not os.path.exists(upload['file_path']):
#         return jsonify({'error': 'File not found'}), 404
    
#     return send_file(
#         upload['file_path'],
#         as_attachment=True,
#         download_name=upload['file_name']
#     )

# @uploads_bp.route('/uploads/<upload_id>', methods=['DELETE'])
# def delete_upload_route(upload_id):
#     """
#     Delete a specific upload.
#     """
#     username = request.args.get('username')
#     if not username:
#         return jsonify({'error': 'Username is required'}), 400
    
#     if delete_upload(upload_id, username):
#         return jsonify({'message': 'Upload deleted successfully'}), 200
#     else:
#         return jsonify({'error': 'Upload not found or unauthorized'}), 404 