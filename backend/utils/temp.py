import os
import tempfile
import zipfile
import shutil
import nibabel as nib
import numpy as np
import cv2
import json
import requests
from PIL import Image
from flask import Blueprint, request, jsonify, current_app
from cvat_sdk import make_client
from cvat_sdk.core.proxies.tasks import ResourceType
from auth.cvat_auth import authenticate_with_cvat  # Import the authentication function

cvat_bp = Blueprint('cvat', __name__)

# Get paths from config or use default ones
from config import TEMP_UPLOADS_PATH, TEMP_RESULTS_PATH

# Updated dataset configuration with COCO format labels.
# Note: The file_ending has been changed to ".nii.gz"
DATASET_INFO = {
    "name": "BRATS",
    "description": "Gliomas segmentation tumour and oedema in brain images",
    "reference": "https://www.med.upenn.edu/sbia/brats2017.html",
    "licence": "CC-BY-SA 4.0",
    "release": "2.0 04/05/2018",
    "labels": {
        "background": 0,
        "edema": 1,
        "non-enhancing tumor": 2,
        "enhancing tumour": 3  # British spelling to match target format
    },
    "file_ending": ".nii.gz"
}

# ---------------------------- Helper Functions ----------------------------

# def convert_nii_to_png(nii_file, output_dir):
#     """Convert NIfTI to PNG with proper normalization."""
#     try:
#         img = nib.load(nii_file)
#         data = img.get_fdata()
#         data_min, data_max = np.min(data), np.max(data)
#         normalized = ((data - data_min) / (data_max - data_min + 1e-8) * 255).astype(np.uint8)
#         os.makedirs(output_dir, exist_ok=True)
#         for i in range(normalized.shape[2]):
#             Image.fromarray(normalized[:, :, i]).save(
#                 os.path.join(output_dir, f"slice_{i:03d}.png")
#             )
#         return normalized.shape[2]
#     except Exception as e:
#         raise ValueError(f"NIfTI conversion failed: {str(e)}")

def get_bounding_box(mask, label):
    """Calculate COCO-format bounding box."""
    coords = np.argwhere(mask == label)
    if coords.size == 0:
        return None
    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)
    return [float(x_min), float(y_min), float(x_max - x_min + 1), float(y_max - y_min + 1)]

def get_segmentation(mask, label):
    """Generate COCO-compatible polygon coordinates."""
    binary_mask = (mask == label).astype(np.uint8)
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [contour.flatten().tolist() for contour in contours if contour.size >= 6]

def create_zip_from_directory(directory_path):
    """Create ZIP archive with proper path handling."""
    zip_path = tempfile.mktemp(suffix=".zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, directory_path))
    return zip_path

def process_nii_to_cvat_annotations(nii_file):
    """Generate COCO-format annotations from a NIfTI file."""
    nii_data = nib.load(nii_file).get_fdata()
    coco_data = {
        "info": {
            "description": DATASET_INFO["description"],
            "url": DATASET_INFO["reference"],
            "version": DATASET_INFO["release"],
            "year": 2018,
            "contributor": "Generated",
            "date_created": "2025-01-28"
        },
        "licenses": [{
            "id": 1,
            "name": DATASET_INFO["licence"],
            "url": "https://creativecommons.org/licenses/by-sa/4.0/"
        }],
        "images": [],
        "annotations": [],
        "categories": [
            {"id": v, "name": k}
            for k, v in DATASET_INFO["labels"].items()
            if v != 0
        ]
    }
    annotation_id = 0
    image_id = 0
    for slice_idx in range(nii_data.shape[2]):
        slice_data = nii_data[:, :, slice_idx]
        coco_data["images"].append({
            "id": image_id,
            "file_name": f"slice_{slice_idx:03d}.png",
            "height": slice_data.shape[0],
            "width": slice_data.shape[1]
        })
        unique_labels = np.unique(slice_data)
        for label in unique_labels:
            if label == 0:
                continue
            bbox = get_bounding_box(slice_data, label)
            segmentation = get_segmentation(slice_data, label)
            if not bbox or not segmentation:
                continue
            coco_data["annotations"].append({
                "id": annotation_id,
                "image_id": image_id,
                "category_id": int(label),
                "segmentation": segmentation,
                "bbox": bbox,
                "area": int(np.sum(slice_data == label)),
                "iscrowd": 0
            })
            annotation_id += 1
        image_id += 1
    return coco_data

def save_annotations(annotations, task_id, output_dir="annotation_files"):
    """Save COCO-format annotations and return the file path."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"task_{task_id}_coco_annotations.json")
    try:
        def convert(o):
            if isinstance(o, np.generic):
                return o.item()
            raise TypeError
        with open(output_path, 'w') as f:
            json.dump(annotations, f, indent=4, default=convert)
        return output_path
    except Exception as e:
        print(f"Failed to save COCO annotations: {str(e)}")
        return None

def download_corrected_annotations_for_task(task, output_dir):
    """
    Downloads the corrected annotation (COCO JSON) for a given task,
    saving it in output_dir.
    """
    ann_data = task.download_annotations(format_name="COCO 1.1")
    output_path = os.path.join(output_dir, f"task_{task.id}_corrected.json")
    with open(output_path, "wb") as f:
        f.write(ann_data)
    return output_path

def convert_coco_annotations_to_nii(coco_json_path, output_nii_path):
    """
    Converts COCO-format annotations (from a JSON file) to a 3D NIfTI segmentation volume.
    Assumes each image corresponds to a 2D slice with filename format "slice_###.png".
    """
    with open(coco_json_path, 'r') as f:
        coco_data = json.load(f)
    if not coco_data.get("images"):
        raise ValueError("No images found in COCO annotations.")
    def extract_slice_index(filename):
        basename = os.path.splitext(filename)[0]
        parts = basename.split('_')
        try:
            return int(parts[-1])
        except ValueError:
            return 0
    images_info = sorted(coco_data["images"], key=lambda x: extract_slice_index(x["file_name"]))
    num_slices = len(images_info)
    height = images_info[0]["height"]
    width = images_info[0]["width"]
    segmentation_volume = np.zeros((height, width, num_slices), dtype=np.uint8)
    annotations_by_image = {}
    for ann in coco_data.get("annotations", []):
        img_id = ann["image_id"]
        annotations_by_image.setdefault(img_id, []).append(ann)
    for img in images_info:
        img_id = img["id"]
        slice_index = extract_slice_index(img["file_name"])
        slice_mask = np.zeros((height, width), dtype=np.uint8)
        for ann in annotations_by_image.get(img_id, []):
            category_id = int(ann["category_id"])
            for poly in ann["segmentation"]:
                if len(poly) < 6:
                    continue
                pts = np.array(poly, dtype=np.int32).reshape((-1, 2))
                pts = pts.reshape((-1, 1, 2))
                cv2.fillPoly(slice_mask, [pts], color=category_id)
        segmentation_volume[:, :, slice_index] = slice_mask
    nii_img = nib.Nifti1Image(segmentation_volume, affine=np.eye(4))
    nib.save(nii_img, output_nii_path)
    print(f"Saved converted NIfTI segmentation at: {output_nii_path}")

def insert_corrected_annotation_with_multichannel(corrected_nii_file, dataset_folder, raw_images_src, original_seg_filename):
    """
    Inserts the corrected segmentation (NIfTI file) and its corresponding multi-channel raw image files
    into the nnU-Net dataset. The corrected segmentation is copied into labelsTr and each raw channel file
    is copied into imagesTr with a new case identifier.
    
    Parameters:
      - corrected_nii_file: Path to the corrected NIfTI segmentation.
      - dataset_folder: The nnU-Net dataset folder (e.g., "Dataset001_BrainTumor").
      - raw_images_src: Folder containing the original multi-channel files.
      - original_seg_filename: Original filename for channel 0000 (e.g., "BRATS_002.nii.gz").
      
    Returns:
      new_case_id: New case identifier (zero-padded string).
    """
    imagesTr_path = os.path.join(dataset_folder, "imagesTr")
    labelsTr_path = os.path.join(dataset_folder, "labelsTr")
    dataset_json_path = os.path.join(dataset_folder, "dataset.json")
    for d in [imagesTr_path, labelsTr_path]:
        if not os.path.exists(d):
            raise FileNotFoundError(f"Required folder {d} does not exist.")
    if not os.path.exists(dataset_json_path):
        raise FileNotFoundError(f"dataset.json not found in {dataset_folder}")
    with open(dataset_json_path, 'r') as f:
        dataset = json.load(f)
    file_ending = dataset.get("file_ending", ".nii.gz")
    current_num = dataset.get("numTraining", 0)
    new_case_id = str(current_num).zfill(4)
    new_label_filename = f"{new_case_id}{file_ending}"
    dest_label_path = os.path.join(labelsTr_path, new_label_filename)
    shutil.copy(corrected_nii_file, dest_label_path)
    print(f"Copied corrected annotation to: {dest_label_path}")
    # Derive common base name from original_seg_filename
    base_name = os.path.splitext(original_seg_filename)[0]
    # Determine the number of channels from DATASET_INFO.channel_names (if defined); otherwise assume 1.
    num_channels = len(DATASET_INFO.get("channel_names", {})) or 1
    for ch in range(num_channels):
        src_filename = f"{base_name}_{ch:04d}{file_ending}"
        src_file = os.path.join(raw_images_src, src_filename)
        if not os.path.exists(src_file):
            raise FileNotFoundError(f"Expected raw file not found: {src_file}")
        dest_filename = f"{new_case_id}_{ch:04d}{file_ending}"
        dest_file = os.path.join(imagesTr_path, dest_filename)
        shutil.copy(src_file, dest_file)
        print(f"Copied channel {ch} file to: {dest_file}")
    dataset["numTraining"] = current_num + 1
    if "training" in dataset:
        new_training_entry = {
            "image": os.path.join("./imagesTr", f"{new_case_id}_0000{file_ending}"),
            "label": os.path.join("./labelsTr", new_label_filename)
        }
        dataset["training"].append(new_training_entry)
        print("Appended new training entry to dataset.json.")
    with open(dataset_json_path, 'w') as f:
        json.dump(dataset, f, indent=4)
    return new_case_id

# ------------------- Existing Routes for Corrected Tasks -------------------

@cvat_bp.route('/send-to-dataset', methods=['POST'])
def send_to_dataset():
    """
    Expects JSON:
    {
      "username": "cvat_user",
      "password": "cvat_pass",
      "task_ids": [123, 456, ...]
    }
    For each task, this route:
      1. Retrieves the corrected annotation (COCO JSON) from CVAT.
      2. Converts the COCO annotation to a NIfTI segmentation file.
      3. Inserts the corrected segmentation and the raw multi-channel file(s)
         (located in temp_uploads/niftis) into the nnU-Net dataset.
      4. Stores processed task info locally in the "corrected_tasks" folder.
    The task name should follow the format: "folder - BRATS_XXX.nii.gz".
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided."}), 400
        task_ids = data.get("task_ids", [])
        cvat_username = data.get("username")
        cvat_password = data.get("password")
        if not task_ids:
            return jsonify({"error": "No task_ids provided."}), 400
        if not cvat_username or not cvat_password:
            return jsonify({"error": "Missing CVAT credentials."}), 400
        try:
            authenticate_with_cvat(cvat_username, cvat_password)
        except Exception as e:
            return jsonify({"error": f"Authentication failed: {str(e)}"}), 401

        base_dir = current_app.root_path
        raw_images_src = os.path.join(base_dir, "temp_uploads", "niftis")
        if not os.path.exists(raw_images_src):
            return jsonify({"error": "Raw images folder not found in temp_uploads/niftis."}), 500
        dataset_folder = os.path.join(base_dir, "Dataset001_BrainTumor")
        corrected_tasks_dir = os.path.join(base_dir, "corrected_tasks")
        os.makedirs(corrected_tasks_dir, exist_ok=True)

        temp_dir = tempfile.mkdtemp(prefix="send_dataset_")
        results = []
        with make_client(host="https://app.cvat.ai", credentials=(cvat_username, cvat_password)) as client:
            for t_id in task_ids:
                try:
                    task = client.tasks.retrieve(t_id)
                    if " - " not in task.name:
                        return jsonify({"error": f"Task name format invalid for task {t_id}."}), 400
                    _, original_seg_filename = task.name.split(" - ", 1)
                    coco_json_path = download_corrected_annotations_for_task(task, temp_dir)
                    output_nii_path = os.path.join(temp_dir, f"task_{t_id}_segmentation{DATASET_INFO['file_ending']}")
                    convert_coco_annotations_to_nii(coco_json_path, output_nii_path)
                    new_case_id = insert_corrected_annotation_with_multichannel(
                        corrected_nii_file=output_nii_path,
                        dataset_folder=dataset_folder,
                        raw_images_src=raw_images_src,
                        original_seg_filename=original_seg_filename
                    )
                    corrected_file = os.path.join(corrected_tasks_dir, task.name)
                    with open(corrected_file, "w") as f:
                        f.write(new_case_id)
                    results.append({
                        "task_id": t_id,
                        "new_case_id": new_case_id,
                        "label_file": os.path.join("labelsTr", f"{new_case_id}{DATASET_INFO['file_ending']}")
                    })
                except Exception as e:
                    results.append({"task_id": t_id, "error": str(e)})
                    continue
        shutil.rmtree(temp_dir)
        return jsonify({
            "message": "Processed corrected files and sent to dataset.",
            "results": results
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@cvat_bp.route('/corrected-tasks', methods=['GET'])
def list_corrected_tasks():
    """
    Returns a JSON array of corrected tasks stored locally in the "corrected_tasks" folder.
    Each file's name should be in the format: "folder - BRATS_XXX.nii.gz"
    Returns:
      - taskId: the part before " - "
      - taskName: full task name
      - displayName: the portion after " - "
    """
    try:
        base_dir = current_app.root_path
        corrected_tasks_dir = os.path.join(base_dir, "corrected_tasks")
        tasks = []
        if os.path.exists(corrected_tasks_dir):
            for f in os.listdir(corrected_tasks_dir):
                if " - " in f:
                    uuid_part, filename = f.split(" - ", 1)
                    tasks.append({
                        "taskId": uuid_part,
                        "taskName": f,
                        "displayName": filename.strip()
                    })
        return jsonify({"correctedTasks": tasks}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------- New Endpoints for Send to CVAT and Discard -------------------

@cvat_bp.route('/discard_files', methods=['POST'])
def discard_files():
    """Delete selected NIfTI files and associated PNG slices."""
    try:
        data = request.get_json()
        nifti_ids = data.get('nifti_ids', [])
        
        if not nifti_ids:
            return jsonify({'success': False, 'error': 'No files specified for deletion'}), 400
        
        deleted_files = []
        
        for nifti_id in nifti_ids:
            # Extract job_id and base_name from nifti_id
            parts = nifti_id.split('_', 1)
            job_id = parts[0]
            base_name = parts[1] if len(parts) > 1 else nifti_id
            base_name = os.path.splitext(base_name)[0]
            if base_name.lower().endswith('.nii'):
                base_name = os.path.splitext(base_name)[0]  # Handle .nii.gz
            
            # Delete NIfTI file from temp_results
            nifti_path = os.path.join(TEMP_RESULTS_PATH, 'niftis', nifti_id)
            if os.path.exists(nifti_path):
                os.remove(nifti_path)
                deleted_files.append(nifti_path)
            
            # Delete PNG slices from temp_results
            png_dir = os.path.join(TEMP_RESULTS_PATH, 'pngs', f"{job_id}_{base_name}")
            if os.path.exists(png_dir):
                shutil.rmtree(png_dir)
                deleted_files.append(png_dir)
            
            # Find and delete original PNG slices (with or without _0000 suffix)
            original_png_dir = os.path.join(TEMP_UPLOADS_PATH, 'pngs', f"{job_id}_{base_name}")
            if not os.path.exists(original_png_dir):
                original_png_dir = os.path.join(TEMP_UPLOADS_PATH, 'pngs', f"{job_id}_{base_name}_0000")
            
            if os.path.exists(original_png_dir):
                shutil.rmtree(original_png_dir)
                deleted_files.append(original_png_dir)
            
            # Find and delete original NIfTI file
            original_nifti_path = os.path.join(TEMP_UPLOADS_PATH, 'niftis', f"{job_id}_{base_name}.nii.gz")
            if not os.path.exists(original_nifti_path):
                original_nifti_path = os.path.join(TEMP_UPLOADS_PATH, 'niftis', f"{job_id}_{base_name}_0000.nii.gz")
            
            if os.path.exists(original_nifti_path):
                os.remove(original_nifti_path)
                deleted_files.append(original_nifti_path)
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted {len(deleted_files)} files',
            'deleted_files': deleted_files
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@cvat_bp.route('/upload_tasks', methods=['POST'])
def upload_tasks():
    """Upload selected files to CVAT as tasks with annotations."""
    try:
        data = request.get_json()
        nifti_ids = data.get('nifti_ids', [])
        cvat_username = data.get('cvat_username')
        cvat_password = data.get('cvat_password')
        
        if not nifti_ids:
            return jsonify({'success': False, 'error': 'No files specified for upload'}), 400
        
        if not cvat_username or not cvat_password:
            return jsonify({'success': False, 'error': 'CVAT credentials required'}), 400
        
        base_dir = current_app.root_path
        
        # Authenticate with CVAT using the existing function
        try:
            auth_data = authenticate_with_cvat(cvat_username, cvat_password)
            token = auth_data.get('key')
            
            if not token:
                return jsonify({
                    'success': False, 
                    'error': 'Failed to retrieve authentication token from CVAT'
                }), 401
                
            print(f"Successfully authenticated with CVAT. Token obtained.")
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': f'CVAT authentication failed: {str(e)}'
            }), 401
        
        # CVAT API base URL
        cvat_api_url = "https://app.cvat.ai/api"
        
        # Headers for authenticated requests
        auth_headers = {
            "Authorization": f"Token {token}"
        }
        
        # Get current user info
        user_response = requests.get(
            f"{cvat_api_url}/users/self",
            headers=auth_headers
        )
        
        if user_response.status_code != 200:
            return jsonify({
                'success': False, 
                'error': f'Failed to get CVAT user info: {user_response.text}'
            }), 400
        
        user_data = user_response.json()
        user_id = user_data['id']
        
        print(f"Authenticated user ID: {user_id}")
        
        # Process each selected NIfTI file
        uploaded_tasks = []
        
        for nifti_id in nifti_ids:
            # Extract job_id and base_name from nifti_id
            parts = nifti_id.split('_', 1)
            job_id = parts[0]
            base_name = parts[1] if len(parts) > 1 else nifti_id
            base_name = os.path.splitext(base_name)[0]
            if base_name.lower().endswith('.nii'):
                base_name = os.path.splitext(base_name)[0]  # Handle .nii.gz
            
            # Find PNG slices - original images
            original_png_dir = os.path.join(TEMP_UPLOADS_PATH, 'pngs', f"{job_id}_{base_name}")
            if not os.path.exists(original_png_dir):
                original_png_dir = os.path.join(TEMP_UPLOADS_PATH, 'pngs', f"{job_id}_{base_name}_0000")
            
            if not os.path.exists(original_png_dir):
                return jsonify({
                    'success': False, 
                    'error': f'Original PNG directory not found for {nifti_id}'
                }), 404
            
            # Find segmentation result PNG slices
            result_png_dir = os.path.join(TEMP_RESULTS_PATH, 'pngs', f"{job_id}_{base_name}")
            
            if not os.path.exists(result_png_dir):
                return jsonify({
                    'success': False, 
                    'error': f'Result PNG directory not found for {nifti_id}'
                }), 404
            
            # Create a new task in CVAT
            task_name = f"Medical Scan - {base_name}"
            
            # Create CVAT task
            create_task_response = requests.post(
                f"{cvat_api_url}/tasks",
                headers={**auth_headers, "Content-Type": "application/json"},
                json={
                    "name": task_name,
                    "labels": [
                        {"name": l, "color": "#ff0000"} 
                        for l in DATASET_INFO["labels"] 
                        if l != "background"
                    ],
                    "owner_id": user_id
                }
            )
            
            if create_task_response.status_code != 201:
                print(f"Task creation failed: {create_task_response.text}")
                return jsonify({'success': False, 'error': f'Failed to create CVAT task: {create_task_response.text}'}), 400
            
            task_data = create_task_response.json()
            task_id = task_data['id']
            
            # Upload original PNG slices as images to the task
            png_files = sorted([f for f in os.listdir(original_png_dir) if f.lower().endswith('.png')])

            # Prepare a temporary directory with images to upload
            temp_upload_dir = os.path.join('/tmp', f'cvat_upload_{job_id}_{base_name}')
            os.makedirs(temp_upload_dir, exist_ok=True)
            # print(temp_upload_dir)
            # print(original_png_dir)
            for png_file in png_files:
                shutil.copy2(
                    os.path.join(original_png_dir, png_file),
                    os.path.join(temp_upload_dir, png_file)
                )
            
            # Create ZIP archive for data upload
            zip_path = os.path.join('/tmp', f'{job_id}_{base_name}.zip')
            shutil.make_archive(
                os.path.splitext(zip_path)[0],  # Path without extension
                'zip',
                temp_upload_dir
            )
            print(zip_path)
            # Upload data to CVAT task
            with open(zip_path, 'rb') as zip_file:
                data_upload_response = requests.post(
                    f"{cvat_api_url}/tasks/{task_id}/data",
                    headers=auth_headers,
                    files={'client_files[0]': zip_file},
                    data={
                        'image_quality': 70,  # Or any other value appropriate for your use case
                        'use_zip_chunks': True,
                        'use_cache': True,
                        'chunk_size': 10  # Optional, depending on your setup
                    }
                )

            if data_upload_response.status_code != 202:
                print(data_upload_response.text)
                return jsonify({
                    'success': False,
                    'error': f'Failed to upload data to CVAT task: {data_upload_response.text}'
                }), 400

            
            uploaded_tasks.append({
                'task_id': task_id,
                'task_name': task_name,
                'redirect_url': f"https://app.cvat.ai/tasks/{task_id}"
            })
        
        return jsonify({
            'success': True,
            'message': f'Successfully uploaded {len(uploaded_tasks)} task(s) to CVAT',
            'tasks': uploaded_tasks
        })
        
    except Exception as e:
        print(f"Unexpected error in upload_tasks: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
