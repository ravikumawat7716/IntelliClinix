#backend/inference/routes.py
from flask import Blueprint, request, jsonify, send_file

import uuid
import os
from utils.file_processing import process_upload, nifti_to_png_slices
from utils.nnunet import run_inference_pipeline
import shutil
import logging


inference_bp = Blueprint('inference', __name__)

TEMP_UPLOADS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'temp_uploads'))
TEMP_RESULTS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'temp_results'))

os.makedirs(TEMP_UPLOADS_PATH, exist_ok=True)
os.makedirs(TEMP_RESULTS_PATH, exist_ok=True)

@inference_bp.route('/upload', methods=['POST'])
def handle_upload():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
            
        file = request.files['file']
        config = request.form.get('config', '3d_fullres')
        username = request.form.get('username')
        print(file)
        file = request.files['file']
        filename = file.filename  # e.g., "image_01.nii.gz"

        # Remove all extensions (including double ones like .nii.gz)
        name_without_ext = os.path.splitext(filename)[0]  # removes only ".gz"
        if name_without_ext.endswith('.nii'):
            name_without_ext = os.path.splitext(name_without_ext)[0]  # removes ".nii"
        if config not in ['2d', '3d_fullres']:
            return jsonify({'success': False, 'error': 'Invalid config'}), 400

        # Generate a unique job ID 
        job_id = name_without_ext
        
        # Save the uploaded ZIP file temporarily
        zip_path = os.path.join(TEMP_UPLOADS_PATH, f'{job_id}.zip')
        file.save(zip_path)
        
        # Process the upload and get paths
        try:
            result = process_upload(zip_path, TEMP_UPLOADS_PATH)
            print("processed")
            if username:
                result['username'] = username
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

        return jsonify({
            'success': True,
            'job_id': job_id,
            'config': config,
            'nifti_paths': result.get('nifti_paths', []),
            'nifti_path': result.get('nifti_path'),
            'png_dirs': result.get('png_dirs', []),
            'png_dir': result.get('png_dir'),
            'inference_dir': result.get('inference_dir')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@inference_bp.route('/run', methods=['POST'])
def handle_inference():
    try:
        data = request.json
        job_id = data.get('job_id')
        config = data.get('config', '3d_fullres')
        inference_dir = data.get('inference_dir')
        
        if not job_id or not config:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400

        # If no specific inference directory provided, try to find it
        if not inference_dir or not os.path.exists(inference_dir):
            inference_dir = os.path.join(TEMP_UPLOADS_PATH, f'inference_temp_{job_id}')
            if not os.path.exists(inference_dir):
                return jsonify({'success': False, 'error': f'Inference directory not found for job {job_id}'}), 500
        
        # Create organized storage structure in temp_results
        results_niftis_dir = os.path.join(TEMP_RESULTS_PATH, 'niftis')
        results_pngs_dir = os.path.join(TEMP_RESULTS_PATH, 'pngs')
        os.makedirs(results_niftis_dir, exist_ok=True)
        os.makedirs(results_pngs_dir, exist_ok=True)
        
        # Create a temporary directory for initial inference output
        temp_output_dir = os.path.join(TEMP_RESULTS_PATH, f'temp_inference_{job_id}')
        os.makedirs(temp_output_dir, exist_ok=True)
        
        # Run inference pipeline
        inference_results = run_inference_pipeline(
            input_dir=inference_dir,
            output_dir=temp_output_dir,
            config=config,
            job_id=job_id
        )
        
        if inference_results.get('status') == 'failed':
            shutil.rmtree(temp_output_dir)
            return jsonify({
                'success': False, 
                'error': inference_results.get('error', 'Inference failed')
            }), 500
        
        # Process inference results and organize into niftis/pngs structure
        result_files = []
        for root, _, files in os.walk(temp_output_dir):
            for file in files:
                if file.lower().endswith(('.nii', '.nii.gz')):
                    # Copy NIfTI result to the niftis directory
                    src_path = os.path.join(root, file)
                    dest_filename = f"{job_id}_{file}"
                    dest_path = os.path.join(results_niftis_dir, dest_filename)
                    
                    shutil.copy2(src_path, dest_path)
                    result_files.append(dest_path)
                    
                    # Create PNG slices for this result
                    base_name = os.path.splitext(file)[0]
                    if base_name.lower().endswith('.nii'):
                        base_name = os.path.splitext(base_name)[0]
                    
                    png_output_dir = os.path.join(results_pngs_dir, f"{job_id}_{base_name}")
                    os.makedirs(png_output_dir, exist_ok=True)
                    
                    # Convert NIfTI to PNG slices
                    nifti_to_png_slices(src_path, png_output_dir, True, True)
        
        # Clean up the temporary directory
        shutil.rmtree(temp_output_dir)
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'result_files': result_files,
            'niftis_dir': results_niftis_dir,
            'pngs_dir': results_pngs_dir,
            'inference_results': inference_results
        })
        
    except Exception as e:
        logging.error(f"Error in handle_inference: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# @inference_bp.route('/temp_results', methods=['GET'])
# def get_temp_results():
#     if not os.path.exists(TEMP_RESULTS_PATH):
#         return jsonify({'success': False, 'error': f'Directory not found: {TEMP_RESULTS_PATH}'}), 404

#     folder_names = [f for f in os.listdir(TEMP_RESULTS_PATH) if os.path.isdir(os.path.join(TEMP_RESULTS_PATH, f))]

#     return jsonify({'success': True, 'folders': folder_names})

@inference_bp.route('/nifti_files', methods=['GET'])
def get_nifti_files():
    try:
        niftis_dir = os.path.join(TEMP_RESULTS_PATH, 'niftis')
        if not os.path.exists(niftis_dir):
            return jsonify({'success': False, 'error': 'NIfTI directory not found'}), 404
        
        nifti_files = []
        for file in os.listdir(niftis_dir):
            if file.lower().endswith(('.nii', '.nii.gz')):
                # Extract job ID from filename (assuming format is job_id_filename.nii.gz)
                job_id = file.split('_', 1)[0] if '_' in file else "unknown"
                
                nifti_files.append({
                    'id': file,  # Use filename as ID
                    'filename': file,
                    'jobId': job_id
                })
        
        return jsonify({
            'success': True,
            'nifti_files': nifti_files
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@inference_bp.route('/comparison_slices', methods=['GET'])
def get_comparison_slices():
    try:
        # Get parameters
        nifti_id = request.args.get('nifti_id')
        job_id = request.args.get('job_id')
        
        if not nifti_id or not job_id:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400
        
        # Extract base name (without job_id prefix and extension)
        parts = nifti_id.split('_', 1)
        # print(parts)
        base_name = parts[1] if len(parts) > 1 else nifti_id
        base_name = os.path.splitext(base_name)[0]
        base_name = os.path.splitext(base_name)[0]
        # print(base_name)
        # Result folder path (segmentation result)
        result_folder = os.path.join(TEMP_RESULTS_PATH, 'pngs', f"{job_id}_{base_name}")
        # print("res", result_folder)
        # For original folder, check both with and without _0000 suffix
        original_folder = os.path.join(TEMP_UPLOADS_PATH, 'pngs', f"{job_id}_{base_name}")
        
        if not os.path.exists(original_folder):
            original_folder = os.path.join(TEMP_UPLOADS_PATH, 'pngs', f"{job_id}_{base_name}_0000")
        
        if not os.path.exists(original_folder):
            return jsonify({'success': False, 'error': f'Original folder not found: {original_folder}'}), 404
        
        if not os.path.exists(result_folder):
            return jsonify({'success': False, 'error': f'Result folder not found: {result_folder}'}), 404
        
        print(original_folder)
        # Get list of PNG files
        original_slices = sorted([
            f"http://localhost:5328/inference/slice_image?path={os.path.join(original_folder, f)}"
            for f in os.listdir(original_folder)
            if f.lower().endswith('.png')
        ])
        print(result_folder)
        result_slices = sorted([
            f"http://localhost:5328/inference/slice_image?path={os.path.join(result_folder, f)}"
            for f in os.listdir(result_folder)
            if f.lower().endswith('.png')
        ])
        
        return jsonify({
            'success': True,
            'original_slices': original_slices,
            'result_slices': result_slices
        })
        
    except Exception as e:
        print(f"Error in comparison_slices: {str(e)}")  # Debugging
        return jsonify({'success': False, 'error': str(e)}), 500

@inference_bp.route('/slice_image', methods=['GET'])
def get_slice_image():
    print("Slice image endpoint called!")  # Debug print to confirm the function runs
    
    try:
        # Get the image path from query parameters
        image_path = request.args.get('path')
        print(f"Requested image path: {image_path}")  # Debug print
        
        # Check if path exists
        if not image_path:
            print("No path provided")
            return "Image path not provided", 400
        
        # Fix path if it contains DEP_ds or DEP_results (which appear to be incorrect)
        if 'DEP_ds' in image_path:
            # Replace with proper temp_uploads path
            correct_path = image_path.replace('/home/ravi/Development/DEP_ds', 
                                             os.path.abspath(TEMP_UPLOADS_PATH))
            print(f"Corrected path from DEP_ds: {correct_path}")
            image_path = correct_path
            
        elif 'DEP_results' in image_path:
            # Replace with proper temp_results path
            correct_path = image_path.replace('/home/ravi/Development/DEP_results', 
                                             os.path.abspath(TEMP_RESULTS_PATH))
            print(f"Corrected path from DEP_results: {correct_path}")
            image_path = correct_path
        
        print(f"Final image path: {image_path}")
        
        # Check if file exists
        if not os.path.exists(image_path):
            print(f"File not found: {image_path}")
            # Try to list parent directory contents to help debug
            parent_dir = os.path.dirname(image_path)
            if os.path.exists(parent_dir):
                print(f"Files in {parent_dir}: {os.listdir(parent_dir)}")
            return f"Image not found: {image_path}", 404
        
        # Log success before sending file
        print(f"File found: {image_path}, sending to client")
        
        # Serve the image file
        return send_file(image_path, mimetype='image/png')
        
    except Exception as e:
        error_msg = f"Error in slice_image: {str(e)}"
        print(error_msg)
        return error_msg, 500
