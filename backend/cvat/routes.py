import os
import re
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
import datetime
import time

cvat_bp = Blueprint('cvat', __name__)

# Get paths from config or use default ones
from config import TEMP_UPLOADS_PATH, TEMP_RESULTS_PATH
CVAT_HOST = "https://app.cvat.ai/api"
# Updated dataset configuration for both brain and heart
LABEL_COLORS = {
    # Brain tumor labels
    "edema": "#00FF00",         # Bright Green
    "non-enhancing tumor": "#0000FF",  # Blue
    "enhancing tumour": "#FFFF00",      # Yellow
    # Heart labels
    "left_atrium": "#FF0000"    # Red for left atrium - updated to match dataset.json
}

DATASET_CONFIGS = {
    "Dataset001_BrainTumour": {
        "name": "BRATS",
        "description": "Gliomas segmentation tumour and oedema in brain images",
        "reference": "https://www.med.upenn.edu/sbia/brats2017.html",
        "licence": "CC-BY-SA 4.0",
        "release": "2.0 04/05/2018",
        "labels": {
            "background": 0,
            "edema": 1,
            "non-enhancing tumor": 2,
            "enhancing tumour": 3
        },
        "file_ending": ".nii.gz",
    },
    "Dataset002_Heart": {
        "name": "Heart",
        "description": "Left atrium segmentation in cardiac MRI",
        "reference": "Heart dataset reference",
        "licence": "CC-BY-SA 4.0",
        "release": "1.0",
        "channel_names": {
            "0": "image"
        },
        "labels": {
            "background": 0,
            "left_atrium": 1
        },
        "file_ending": ".nii.gz",
        "numTraining": 0,  # Will be updated dynamically
        "training": [],    # Will be updated dynamically
        "test": []
    }
}

def get_dataset_config(filename: str) -> dict:
    """Determine dataset configuration based on filename pattern."""
    if filename.startswith('la_'):
        return DATASET_CONFIGS["Dataset002_Heart"]
    return DATASET_CONFIGS["Dataset001_BrainTumour"]

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

def get_bounding_box(mask, label_id):
    """Calculate precise COCO-format bounding boxes."""
    coords = np.argwhere(mask == label_id)
    if coords.size == 0:
        return None
        
    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)
    
    return [
        float(x_min),  # x
        float(y_min),  # y 
        float(x_max - x_min + 1),  # width
        float(y_max - y_min + 1)   # height
    ]

def get_segmentation(mask, label_id):
    """Generate COCO-style segmentation polygons with proper axis correction."""
    binary_mask = (mask == label_id).astype(np.uint8)
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    height, width = binary_mask.shape

    valid_segments = []
    for contour in contours:
        if len(contour) >= 3:
            contour = contour.squeeze()

            if contour.ndim != 2 or contour.shape[0] < 3:
                continue

            # # Flip Y-axis (vertical flip)
            # contour[:, 1] = height - contour[:, 1] - 1
            # # Flip X-axis (horizontal flip)
            # contour[:, 0] = width - contour[:, 0] - 1

            coords = contour[:, [0, 1]].flatten().tolist()
            if len(coords) % 2 == 0 and len(coords) >= 6:
                valid_segments.append(coords)

    return valid_segments or None


def create_zip_from_directory(directory_path):
    """Create ZIP archive with proper path handling."""
    zip_path = tempfile.mktemp(suffix=".zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, directory_path))
    return zip_path

# def process_nii_to_cvat_annotations(nii_file):
#     """Generate COCO-format annotations from a NIfTI file."""
#     nii_data = nib.load(nii_file).get_fdata()
#     coco_data = {
#         "info": {
#             "description": DATASET_INFO["description"],
#             "url": DATASET_INFO["reference"],
#             "version": DATASET_INFO["release"],
#             "year": 2018,
#             "contributor": "Generated",
#             "date_created": "2025-01-28"
#         },
#         "licenses": [{
#             "id": 1,
#             "name": DATASET_INFO["licence"],
#             "url": "https://creativecommons.org/licenses/by-sa/4.0/"
#         }],
#         "images": [],
#         "annotations": [],
#         "categories": [
#             {"id": v, "name": k}
#             for k, v in DATASET_INFO["labels"].items()
#             if v != 0
#         ]
#     }
#     annotation_id = 0
#     image_id = 0
#     for slice_idx in range(nii_data.shape[2]):
#         slice_data = nii_data[:, :, slice_idx]
#         coco_data["images"].append({
#             "id": image_id,
#             "file_name": f"slice_{slice_idx:03d}.png",
#             "height": slice_data.shape[0],
#             "width": slice_data.shape[1]
#         })
#         unique_labels = np.unique(slice_data)
#         for label in unique_labels:
#             if label == 0:
#                 continue
#             bbox = get_bounding_box(slice_data, label)
#             segmentation = get_segmentation(slice_data, label)
#             if not bbox or not segmentation:
#                 continue
#             coco_data["annotations"].append({
#                 "id": annotation_id,
#                 "image_id": image_id,
#                 "category_id": int(label),
#                 "segmentation": segmentation,
#                 "bbox": bbox,
#                 "area": int(np.sum(slice_data == label)),
#                 "iscrowd": 0
#             })
#             annotation_id += 1
#         image_id += 1
#     return coco_data
# Helper functions
# Add these helper functions to your existing code

def parse_nifti_id(nifti_id):
    """Extract job ID and base filename from NIfTI ID."""
    parts = nifti_id.split('_', 1)
    job_id = parts[0]
    base_name = parts[1] if len(parts) > 1 else nifti_id
    base_name = os.path.splitext(base_name)[0]  # Remove .nii.gz extension
    if base_name.endswith('.nii'):
        base_name = os.path.splitext(base_name)[0]
    return job_id, base_name

def get_png_paths(job_id, base_name):
    """Get original and result PNG directories for a given job."""
    original_dir = os.path.join(
        TEMP_UPLOADS_PATH, 
        'pngs', 
        f"{job_id}_{base_name}"
    )
    result_dir = os.path.join(
        TEMP_RESULTS_PATH,
        'pngs',
        f"{job_id}_{base_name}"
    )
    
    # Handle possible _0000 suffix for original images
    if not os.path.exists(original_dir):
        original_dir = os.path.join(
            TEMP_UPLOADS_PATH,
            'pngs',
            f"{job_id}_{base_name}_0000"
        )
    
    return original_dir, result_dir

# def rgb_to_label(mask_rgb):
#     """Convert a viridis-colored RGB mask to a label mask by assigning each unique RGB value an ID."""
#     h, w, _ = mask_rgb.shape
#     flat_rgb = mask_rgb.reshape(-1, 3)
#     unique_colors, indices = np.unique(flat_rgb, axis=0, return_inverse=True)
#     label_mask = indices.reshape(h, w)
#     return label_mask, unique_colors

def generate_coco_annotations_from_nifti(nifti_path):
    """Convert segmentation NIfTI file (3D) to COCO format with dynamic label mapping."""
    label_values = set()

    # Load the NIfTI file
    nifti_img = nib.load(nifti_path)
    volume = nifti_img.get_fdata().astype(np.uint8)  # assuming labels are integers

    # Determine dataset type from filename
    dataset_type = "Dataset002_Heart" if "la_" in nifti_path else "Dataset001_BrainTumour"
    dataset_config = DATASET_CONFIGS[dataset_type]

    # Iterate over each 2D slice along the z-axis
    for i in range(volume.shape[2]):
        slice_2d = volume[:, :, i]
        label_values.update(np.unique(slice_2d))

    print("Found label values:", label_values)
    label_values = sorted(label_values)
    print("Sorted label values:", label_values)

    # Invert the labels dictionary: label_id -> label_name
    id_to_name = {v: k for k, v in dataset_config["labels"].items()}
    print("ID to name mapping:", id_to_name)

    labels = []
    try:
        for label_id in label_values:
            if label_id == 0:  # Skip background
                continue
            print("Looking up label_id:", label_id)
            print("Label name:", id_to_name[label_id])
            labels.append(id_to_name[label_id])
            print("Current labels list:", labels)
    except Exception as e:
        print("ERROR:", e)

    coco_data = {
        "info": {
            "description": dataset_config["description"],
            "url": dataset_config["reference"],
            "version": dataset_config["release"],
            "year": 2025,
            "contributor": "AI System",
            "date_created": datetime.datetime.now().strftime("%Y-%m-%d")
        },
        "licenses": [{
            "id": 1,
            "name": dataset_config["licence"],
            "url": "https://creativecommons.org/licenses/by-sa/4.0/"
        }],
        "categories": [
            {
                "id": label_id,
                "name": labels[label_id-1],
            }
            for label_id in label_values if label_id != 0
        ],
        "images": [],
        "annotations": []
    }

    annotation_id = 0
    image_id = 0

    # Iterate over each 2D slice (along z-axis)
    for z in range(volume.shape[2]):
        print(f"Processing slice {z}")
        label_mask = volume[:, :, z]

        coco_data["images"].append({
            "id": image_id,
            "file_name": f"slice_{z:04d}.png",
            "height": label_mask.shape[0],
            "width": label_mask.shape[1]
        })

        for original_value in np.unique(label_mask):
            if original_value == 0:  # Skip background
                continue
            if original_value not in label_values:
                continue

            label_id = original_value
            segmentation = get_segmentation(label_mask, label_id)
            bbox = get_bounding_box(label_mask, label_id)

            if segmentation and bbox:
                coco_data["annotations"].append({
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": label_id,
                    "segmentation": segmentation,
                    "bbox": [float(x) for x in bbox],
                    "area": float(np.sum(label_mask == original_value)),
                    "iscrowd": 0
                })
                annotation_id += 1

        image_id += 1

    return coco_data



# def generate_coco_annotations(png_dir):
#     """Convert segmentation PNGs to CVAT-compatible COCO format."""
#     coco_data = {
#         "info": {
#             "description": DATASET_INFO["description"],
#             "url": DATASET_INFO["reference"],
#             "version": DATASET_INFO["release"],
#             "year": 2025,
#             "contributor": "Medical Annotation System",
#             # FIX: Use imported datetime module
#             "date_created": datetime.datetime.now().strftime("%Y-%m-%d")
#         },
#         "licenses": [{
#             "id": 1,
#             "name": DATASET_INFO["licence"],
#             "url": "https://creativecommons.org/licenses/by-sa/4.0/"
#         }],
#         "images": [],
#         "annotations": [],
#         "categories": [
#             {
#                 "id": label_id,
#                 "name": label_name,
#                 "supercategory": "tumor"  # Required by CVAT's COCO parser
#             }
#             for label_name, label_id in DATASET_INFO["labels"].items()
#             if label_id != 0
#         ]
#     }

#     annotation_id = 0
#     for image_id, png_file in enumerate(sorted(os.listdir(png_dir))):
#         if not png_file.lower().endswith('.png'):
#             continue
            
#         mask = cv2.imread(os.path.join(png_dir, png_file), cv2.IMREAD_GRAYSCALE)
        
#         # Add image entry (must match uploaded filenames exactly)
#         coco_data["images"].append({
#             "id": image_id,
#             "file_name": png_file,
#             "height": mask.shape[0],
#             "width": mask.shape[1]
#         })
        
#         # Process annotations for each label
#         for label_id in np.unique(mask):
#             if label_id == 0:
#                 continue
                
#             # Get validated segmentation and bbox
#             segmentation = get_segmentation(mask, label_id)
#             bbox = get_bounding_box(mask, label_id)
            
#             if segmentation and bbox:
#                 coco_data["annotations"].append({
#                     "id": annotation_id,
#                     "image_id": image_id,
#                     "category_id": int(label_id),
#                     "segmentation": segmentation,
#                     "bbox": [float(x) for x in bbox],  # Ensure float values
#                     "area": int(np.sum(mask == label_id)),
#                     "iscrowd": 0
#                 })
#                 annotation_id += 1
                
#     return coco_data

def save_annotations(annotations, task_id, output_dir="annotation_files"):
    """Save COCO annotations with proper type handling."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"task_{task_id}_coco_annotations.json")
    
    def _converter(o):
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError
    
    try:
        with open(output_path, 'w') as f:
            json.dump(annotations, f, indent=4, default=_converter)
        return output_path
    except Exception as e:
        print(f"Failed to save annotations: {str(e)}")
        return None

def get_cvat_token(cvat_api_url="https://app.cvat.ai/api", username=None, password=None):
    """
    Authenticates with CVAT using the provided credentials
    and returns the authentication token and API URL.
    Note: This version requires that username and password be passed in.
    """
    if not username or not password:
        raise Exception("CVAT credentials must be provided as arguments.")
    
    login_url = f"{cvat_api_url}/auth/login"
    data = {"username": username, "password": password}
    
    response = requests.post(login_url, json=data)
    response.raise_for_status()  # Will raise an error if authentication fails
    
    token = response.json().get("key")
    if not token:
        raise Exception("Failed to retrieve authentication token from CVAT.")
    return token, cvat_api_url


def download_corrected_annotations_for_task(task, persistent_dir, cvat_username, cvat_password):
    """
    Downloads the corrected annotation for the specified CVAT task.
    It will initiate an export with the "COCO 1.0" format (without images),
    poll until the export is finished, then download the file.

    If the result is a ZIP archive, it extracts the JSON file from it.
    If it is already a JSON file, it saves it directly.
    
    Parameters:
      task (object): A CVAT task object (assumed to have an 'id' attribute).
      persistent_dir (str): Local directory to save the exported file.
      cvat_username (str): CVAT username (from JSON input in your route).
      cvat_password (str): CVAT password (from JSON input in your route).
    
    Returns:
      str: File path to the downloaded (and possibly extracted) JSON annotation file.
    """
    cvat_api_url = "https://app.cvat.ai/api"
    # Get authentication token using the provided credentials
    token, _ = get_cvat_token(username=cvat_username, password=cvat_password)
    
    headers = {"Authorization": f"Token {token}"}
    export_url = f"{cvat_api_url}/tasks/{task.id}/dataset/export?format=COCO%201.0&save_images=False"
    print(f"Initiating export for task {task.id}...")
    export_response = requests.post(export_url, headers=headers)
    if export_response.status_code != 202:
        raise Exception(f"Failed to initiate export for task {task.id}: {export_response.status_code} - {export_response.text}")
    
    export_data = export_response.json()
    rq_id = export_data.get("rq_id")
    if not rq_id:
        raise Exception(f"No export request ID returned for task {task.id}.")
    print(f"Export initiated. Request ID: {rq_id}")
    
    # Poll for the export status until it is finished
    status_url = f"{cvat_api_url}/requests/{rq_id}"
    print("Polling for export status...")
    while True:
        status_response = requests.get(status_url, headers=headers)
        if status_response.status_code != 200:
            raise Exception(f"Failed to check export status for task {task.id}: {status_response.status_code} - {status_response.text}")
        status_data = status_response.json()
        if status_data.get("status") == "finished":
            print("Export finished.")
            break
        print("Export in progress... waiting 2 seconds")
        time.sleep(2)
    
    # Once finished, download the file from the provided result_url
    result_url = status_data.get("result_url")
    if not result_url:
        raise Exception(f"No result URL found for task {task.id}.")
    
    print(f"Downloading exported annotations from {result_url} ...")
    file_response = requests.get(result_url, headers=headers)
    if not file_response.ok:
        raise Exception(f"Failed to download annotations for task {task.id}: {file_response.status_code} - {file_response.text}")
    
    # Determine if the downloaded file is a ZIP archive or a JSON file
    file_extension = os.path.splitext(result_url)[1].lower()  # get extension from the URL
    content_type = file_response.headers.get("Content-Type", "").lower()
    
    if file_extension == ".zip" or "zip" in content_type:
        output_zip = os.path.join(persistent_dir, f"task_{task.id}_annotations.zip")
        with open(output_zip, "wb") as f:
            f.write(file_response.content)
        print(f"Annotations downloaded as zip file to {output_zip}.")
        
        # Extract the JSON file from the ZIP archive
        with zipfile.ZipFile(output_zip, 'r') as zip_ref:
            json_files = [f for f in zip_ref.namelist() if f.endswith(".json")]
            if not json_files:
                raise Exception(f"No JSON file found in the downloaded zip for task {task.id}.")
            # Extract the first JSON file found
            zip_ref.extract(json_files[0], persistent_dir)
            extracted_json_path = os.path.join(persistent_dir, json_files[0])
        return extracted_json_path
    else:
        # If not a ZIP, assume the content is already a JSON file
        output_json = os.path.join(persistent_dir, f"task_{task.id}_annotations.json")
        with open(output_json, "wb") as f:
            f.write(file_response.content)
        print(f"Annotations downloaded as JSON file to {output_json}.")
        return output_json


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

    # Sort images by slice index
    images_info = sorted(coco_data["images"], key=lambda x: extract_slice_index(x["file_name"]))
    
    # Compute the correct number of slices based on maximum slice index
    slice_indices = [extract_slice_index(img["file_name"]) for img in images_info]
    num_slices = max(slice_indices) + 1

    height = images_info[0]["height"]
    width = images_info[0]["width"]

    segmentation_volume = np.zeros((height, width, num_slices), dtype=np.uint8)

    # Organize annotations by image_id
    annotations_by_image = {}
    for ann in coco_data.get("annotations", []):
        img_id = ann["image_id"]
        annotations_by_image.setdefault(img_id, []).append(ann)

    # Fill each slice of the volume using the annotations from COCO
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

def insert_corrected_annotation_with_multichannel(corrected_nii_file, dataset_folder, raw_images_src, nifti_id):
    """
    Insert corrected annotations into the dataset structure.
    For heart dataset: la_XXX format (e.g., la_018) - only channel 0000
    For brain dataset: BRATS_XXX format (e.g., BRATS_006) - multiple channels
    """
    imagesTr_path = os.path.join(dataset_folder, "imagesTr")
    labelsTr_path = os.path.join(dataset_folder, "labelsTr")
    dataset_json_path = os.path.join(dataset_folder, "dataset.json")
    
    # Ensure directories exist
    for d in [imagesTr_path, labelsTr_path]:
        if not os.path.exists(d):
            raise FileNotFoundError(f"Required folder {d} does not exist.")
    if not os.path.exists(dataset_json_path):
        raise FileNotFoundError(f"dataset.json not found in {dataset_folder}")
    
    # Load dataset configuration
    with open(dataset_json_path, 'r') as f:
        dataset = json.load(f)
    
    # Extract case number and determine if it's a heart dataset
    is_heart_dataset = 'la_' in nifti_id
    if is_heart_dataset:
        case_match = re.search(r'la_(\d+)', nifti_id)
        if not case_match:
            raise ValueError(f"Invalid heart dataset ID format: {nifti_id}")
        case_number = case_match.group(1)
        base_case_id = f"la_{case_number.zfill(3)}"
        num_channels = 1  # Heart dataset only has one channel
    else:
        # For brain dataset, try different patterns
        brats_match = re.search(r'BRATS[_-]?(\d+)', nifti_id)
        if brats_match:
            case_number = brats_match.group(1)
        else:
            case_match = re.search(r'(\d+)', nifti_id)
            if not case_match:
                raise ValueError(f"Could not extract case number from: {nifti_id}")
            case_number = case_match.group(1)
        base_case_id = f"BRATS_{case_number.zfill(3)}"
        num_channels = 4  # BRATS dataset has 4 channels
    
    file_ending = dataset.get("file_ending", ".nii.gz")
    new_label_filename = f"{base_case_id}{file_ending}"
    
    # Copy the corrected segmentation
    dest_label_path = os.path.join(labelsTr_path, new_label_filename)
    print(f"Copying corrected annotation from {corrected_nii_file} to {dest_label_path}")
    shutil.copy(corrected_nii_file, dest_label_path)
    
    # For brain dataset, first try to find a UUID that has all channels
    if not is_heart_dataset:
        # List all files in the directory
        all_files = os.listdir(raw_images_src)
        # Look for files with pattern brats_UUID_0000.nii.gz
        uuid_pattern = re.compile(r'brats_([a-f0-9-]+)_0000' + re.escape(file_ending))
        uuid_matches = [uuid_pattern.match(f) for f in all_files]
        uuid_matches = [m for m in uuid_matches if m]  # Remove None matches
        
        if uuid_matches:
            # Use the first UUID that has all channels
            for match in uuid_matches:
                uuid = match.group(1)
                has_all_channels = True
                found_files = []
                
                # Check if all channels exist for this UUID
                for ch in range(num_channels):
                    channel_file = f"brats_{uuid}_{ch:04d}{file_ending}"
                    if channel_file not in all_files:
                        has_all_channels = False
                        break
                    found_files.append(os.path.join(raw_images_src, channel_file))
                
                if has_all_channels:
                    # Copy all channels
                    for ch, src_file in enumerate(found_files):
                        dest_filename = f"{base_case_id}_{ch:04d}{file_ending}"
                        dest_file = os.path.join(imagesTr_path, dest_filename)
                        print(f"Copying channel {ch} from {src_file} to {dest_file}")
                        shutil.copy(src_file, dest_file)
                    break
            else:
                raise FileNotFoundError(f"Could not find complete set of channels for case {base_case_id}")
            
            # Skip the regular file search since we found and copied all channels
            found_all_channels = True
        else:
            found_all_channels = False
    else:
        found_all_channels = False
    
    # If we haven't found all channels yet (for heart dataset or if brain dataset UUID search failed)
    if not found_all_channels:
        channels_to_process = range(num_channels)  # Will be 0 only for heart dataset, 0-3 for BRATS
        
        for ch in channels_to_process:
            # Try different possible filename patterns
            if is_heart_dataset:
                possible_filenames = [
                    f"{case_number}_0000{file_ending}",  # Without la_ prefix
                    f"la_{case_number}_0000{file_ending}",  # With la_ prefix
                    f"*_{case_number}_0000{file_ending}",  # With UUID
                    f"*_la_{case_number}_0000{file_ending}",  # With UUID and la_ prefix
                    f"*_{base_case_id}_0000{file_ending}"  # Full pattern with UUID
                ]
            else:
                # For brain dataset, try more patterns
                possible_filenames = [
                    f"*_BRATS_{case_number}_{ch:04d}{file_ending}",  # UUID with BRATS prefix
                    f"BRATS_{case_number}_{ch:04d}{file_ending}",  # Standard BRATS format
                    f"brats_{case_number}_{ch:04d}{file_ending}",  # Lowercase brats prefix
                    f"{case_number}_{ch:04d}{file_ending}",  # Just number
                    f"*_{case_number}_{ch:04d}{file_ending}",  # With UUID
                    f"BRATS{case_number}_{ch:04d}{file_ending}"  # Without underscore
                ]
            
            found_file = None
            for pattern in possible_filenames:
                matching_files = []
                if '*' in pattern:
                    import glob
                    matching_files = glob.glob(os.path.join(raw_images_src, pattern))
                else:
                    direct_path = os.path.join(raw_images_src, pattern)
                    if os.path.exists(direct_path):
                        matching_files = [direct_path]
                
                if matching_files:
                    found_file = matching_files[0]
                    break
            
            if not found_file:
                print(f"Available files in {raw_images_src}:")
                for f in os.listdir(raw_images_src):
                    print(f"  - {f}")
                print(f"Tried patterns: {possible_filenames}")
                raise FileNotFoundError(f"Could not find raw file for case {base_case_id} channel {ch}")
            
            dest_filename = f"{base_case_id}_{ch:04d}{file_ending}"
            dest_file = os.path.join(imagesTr_path, dest_filename)
            print(f"Copying channel {ch} from {found_file} to {dest_file}")
            shutil.copy(found_file, dest_file)
    
    # Update dataset.json
    if "training" not in dataset:
        dataset["training"] = []
    
    new_training_entry = {
        "image": os.path.join("./imagesTr", f"{base_case_id}_0000{file_ending}"),
        "label": os.path.join("./labelsTr", new_label_filename)
    }
    
    # Remove any existing entry for this case
    dataset["training"] = [entry for entry in dataset["training"] 
                          if base_case_id not in entry["image"]]
    
    dataset["training"].append(new_training_entry)
    dataset["numTraining"] = len(dataset["training"])
    
    print(f"Updating dataset.json with new entry: {new_training_entry}")
    with open(dataset_json_path, 'w') as f:
        json.dump(dataset, f, indent=4)
    
    return base_case_id

def generate_dataset_config(dataset_type: str, dataset_path: str) -> dict:
    """
    Dynamically generate dataset configuration by scanning the dataset directory.
    
    Args:
        dataset_type: Type of dataset (e.g., "Dataset002_Heart")
        dataset_path: Path to the dataset directory
        
    Returns:
        dict: Updated dataset configuration
    """
    config = DATASET_CONFIGS[dataset_type].copy()
    
    # Get paths
    images_tr_path = os.path.join(dataset_path, "imagesTr")
    labels_tr_path = os.path.join(dataset_path, "labelsTr")
    
    if not os.path.exists(images_tr_path) or not os.path.exists(labels_tr_path):
        return config
    
    # Find all training files
    training_files = []
    for file in os.listdir(images_tr_path):
        if file.endswith(config["file_ending"]):
            # Extract case ID (e.g., "003" from "la_003_0000.nii.gz")
            case_id = file.split("_")[1]
            label_file = f"la_{case_id}{config['file_ending']}"
            
            if os.path.exists(os.path.join(labels_tr_path, label_file)):
                training_files.append({
                    "image": f"./imagesTr/{file}",
                    "label": f"./labelsTr/{label_file}"
                })
    
    # Update configuration
    config["numTraining"] = len(training_files)
    config["training"] = sorted(training_files, key=lambda x: x["image"])
    
    return config

# ------------------- Updated send_to_dataset Route -------------------

@cvat_bp.route('/send-to-dataset', methods=['POST'])
def send_to_dataset():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided."}), 400

        task_ids = data.get("task_ids", [])
        cvat_username = data.get("username")
        cvat_password = data.get("password")
        dataset_type = data.get("dataset")  # Don't set default here

        if not task_ids:
            return jsonify({"error": "No task IDs provided."}), 400

        if not cvat_username or not cvat_password:
            return jsonify({"error": "CVAT credentials are required."}), 400

        # Get CVAT token with credentials
        try:
            token, _ = get_cvat_token(username=cvat_username, password=cvat_password)
            if not token:
                return jsonify({"error": "Failed to authenticate with CVAT."}), 401
        except Exception as e:
            return jsonify({"error": f"CVAT authentication failed: {str(e)}"}), 401

        results = []
        with make_client(host="https://app.cvat.ai", credentials=(cvat_username, cvat_password)) as client:
            for task_id in task_ids:
                try:
                    # Ensure task_id is an integer
                    task_id = int(task_id)
                    print(f"Processing task {task_id}...")
                    
                    try:
                        task = client.tasks.retrieve(task_id)
                    except Exception as e:
                        err_msg = f"Task {task_id} not found: {str(e)}"
                        print(err_msg)
                        results.append({"task_id": task_id, "error": "Task not found in CVAT."})
                        continue

                    # Use persistent folder to store annotation files permanently
                    persistent_dir = os.path.join(current_app.root_path, "cvat_annotations")
                    os.makedirs(persistent_dir, exist_ok=True)

                    # Download corrected annotations
                    coco_json_path = download_corrected_annotations_for_task(task, persistent_dir, cvat_username, cvat_password)
                    if not os.path.exists(coco_json_path):
                        raise Exception("Annotation download did not create a file")
                    print(f"Annotation JSON saved at {coco_json_path}")

                    # Find the corresponding nifti_id from corrected_tasks
                    corrected_tasks_dir = os.path.join(current_app.root_path, "corrected_tasks")
                    nifti_id = None
                    task_info = None
                    if os.path.exists(corrected_tasks_dir):
                        for filename in os.listdir(corrected_tasks_dir):
                            if filename.endswith(".json"):
                                file_path = os.path.join(corrected_tasks_dir, filename)
                                with open(file_path, "r") as f:
                                    task_info = json.load(f)
                                if task_info.get("task_id") == task_id:
                                    nifti_id = task_info.get("nifti_id")
                                    # If dataset_type wasn't provided in the request, use it from task_info
                                    if not dataset_type:
                                        dataset_type = task_info.get("dataset_type")
                                    break

                    if nifti_id is None:
                        raise Exception(f"Nifti ID not found for task {task_id}")

                    # Determine dataset type based on nifti_id pattern
                    is_heart_dataset = bool(re.search(r'la_\d+', nifti_id))
                    # Override any previous dataset_type setting if we detect a heart dataset pattern
                    if is_heart_dataset:
                        dataset_type = "Dataset002_Heart"
                    elif not dataset_type:  # Only set to brain if not already set and not heart
                        dataset_type = "Dataset001_BrainTumour"

                    print(f"Determined dataset type: {dataset_type} for nifti_id: {nifti_id}")

                    # Get dataset configuration
                    dataset_config = DATASET_CONFIGS.get(dataset_type)
                    if not dataset_config:
                        raise Exception(f"Invalid dataset type: {dataset_type}")

                    # Set up paths based on dataset type
                    base_dir = "/home/ravi/Development/DEP_electrical/nnUNet_raw"
                    dataset_folder = os.path.join(base_dir, dataset_type)
                    images_tr_path = os.path.join(dataset_folder, "imagesTr")
                    labels_tr_path = os.path.join(dataset_folder, "labelsTr")
                    
                    # Create directories if they don't exist
                    os.makedirs(images_tr_path, exist_ok=True)
                    os.makedirs(labels_tr_path, exist_ok=True)

                    output_nii_path = os.path.join(persistent_dir, f"task_{task_id}_segmentation{dataset_config['file_ending']}")
                    convert_coco_annotations_to_nii(coco_json_path, output_nii_path)
                    if not os.path.exists(output_nii_path):
                        raise Exception("NIfTI conversion failed to create a file")
                    print(f"Converted NIfTI saved at {output_nii_path}")

                    # Raw images are in the temp_uploads/niftis directory
                    raw_images_src = os.path.join(current_app.root_path, "temp_uploads", "niftis")
                    if not os.path.exists(raw_images_src):
                        raise Exception(f"Raw images folder not found at {raw_images_src}")

                    # For heart dataset, ensure we're using the la_XXX format
                    if dataset_type == "Dataset002_Heart":
                        # Extract the case number from the nifti_id
                        case_match = re.search(r'la_(\d+)', nifti_id)
                        if not case_match:
                            # Try to find the number in the task name
                            task_name = task_info.get("task_name", "")
                            case_match = re.search(r'la_(\d+)', task_name)
                            if not case_match:
                                # Just extract any number
                                case_match = re.search(r'(\d+)', nifti_id)
                        
                        if case_match:
                            case_number = case_match.group(1).zfill(3)
                            nifti_id = f"la_{case_number}"
                            print(f"Formatted heart dataset case ID: {nifti_id}")

                    # Insert into dataset
                    new_case_id = insert_corrected_annotation_with_multichannel(
                        corrected_nii_file=output_nii_path,
                        dataset_folder=dataset_folder,
                        raw_images_src=raw_images_src,
                        nifti_id=nifti_id
                    )

                    results.append({
                        "task_id": task_id,
                        "status": "success",
                        "new_case_id": new_case_id,
                        "dataset_type": dataset_type
                    })

                except Exception as e:
                    print(f"Error processing task {task_id}: {str(e)}")
                    results.append({
                        "task_id": task_id,
                        "status": "error",
                        "error": str(e)
                    })

        return jsonify({
            "success": True,
            "message": "Tasks processed successfully",
            "results": results
        })

    except Exception as e:
        print(f"Error in send_to_dataset: {str(e)}")
        return jsonify({"error": str(e)}), 500


@cvat_bp.route('/corrected-tasks', methods=['GET'])
def list_corrected_tasks():
    """
    Reads all JSON files from the "corrected_tasks" folder. Each file is expected
    to contain a JSON object with the keys "task_id", "task_name", "nifti_id", and "dataset_type".
    Returns an array of these objects with properly formatted display names.
    """
    try:
        base_dir = current_app.root_path
        corrected_tasks_dir = os.path.join(base_dir, "corrected_tasks")
        tasks = []
        
        if os.path.exists(corrected_tasks_dir):
            for filename in os.listdir(corrected_tasks_dir):
                if filename.endswith(".json"):
                    file_path = os.path.join(corrected_tasks_dir, filename)
                    with open(file_path, "r") as f:
                        task_info = json.load(f)
                    
                    # Get the display name from the task name or filename
                    task_name = task_info.get("task_name", "")
                    display_name = task_name.split(" - ")[1].strip() if " - " in task_name else task_name
                    
                    # Format display name based on dataset type
                    dataset_type = task_info.get("dataset_type")
                    if dataset_type == "Dataset002_Heart":
                        # For heart dataset, ensure we use la_XXX format
                        heart_match = re.search(r'la_\d+', display_name)
                        if heart_match:
                            display_name = heart_match.group(0)
                        else:
                            # Try to extract from nifti_id if not found in display_name
                            nifti_id = task_info.get("nifti_id", "")
                            heart_match = re.search(r'la_\d+', nifti_id)
                            if heart_match:
                                display_name = heart_match.group(0)
                            else:
                                # If still not found, try to extract from filename
                                heart_match = re.search(r'la_\d+', filename)
                                if heart_match:
                                    display_name = heart_match.group(0)
                    else:
                        # For BRATS dataset, use BRATS_XXX format
                        if not display_name.startswith("BRATS_"):
                            number_match = re.search(r'\d+', display_name)
                            if number_match:
                                display_name = f"BRATS_{number_match.group(0).zfill(3)}"
                    
                    task_info["displayName"] = display_name
                    tasks.append(task_info)
        
        return jsonify({"correctedTasks": tasks}), 200
    except Exception as e:
        print(f"Error in list_corrected_tasks: {str(e)}")
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

        # Authenticate with CVAT using the existing function
        try:
            auth_data = authenticate_with_cvat(cvat_username, cvat_password)
            token = auth_data.get('key')
            if not token:
                return jsonify({'success': False, 'error': 'Failed to retrieve authentication token from CVAT'}), 401
            print(f"Successfully authenticated with CVAT. Token obtained.")
        except Exception as e:
            return jsonify({'success': False, 'error': f'CVAT authentication failed: {str(e)}'}), 401

        cvat_api_url = "https://app.cvat.ai/api"
        auth_headers = { "Authorization": f"Token {token}" }

        uploaded_tasks = []

        # Directory where we store created task info locally.
        corrected_tasks_dir = os.path.join(current_app.root_path, "corrected_tasks")
        os.makedirs(corrected_tasks_dir, exist_ok=True)

        for nifti_id in nifti_ids:
            try:
                # Determine dataset type based on filename pattern
                dataset_type = "Dataset002_Heart" if "la_" in nifti_id else "Dataset001_BrainTumour"
                
                # Extract job_id and base_name from nifti_id
                parts = nifti_id.split('_', 1)
                job_id = parts[0]
                base_name = parts[1] if len(parts) > 1 else nifti_id
                base_name = os.path.splitext(base_name)[0]
                # Handle .nii.gz extension
                if base_name.lower().endswith('.nii'):
                    base_name = os.path.splitext(base_name)[0]

                # Find PNG slices from original images (raw)
                original_png_dir = os.path.join(TEMP_UPLOADS_PATH, 'pngs', f"{job_id}_{base_name}")
                if not os.path.exists(original_png_dir):
                    original_png_dir = os.path.join(TEMP_UPLOADS_PATH, 'pngs', f"{job_id}_{base_name}_0000")
                if not os.path.exists(original_png_dir):
                    return jsonify({'success': False, 'error': f'Original PNG directory not found for {nifti_id}'}), 404

                # Find segmentation result PNG slices
                result_nifti = os.path.join(TEMP_RESULTS_PATH, 'niftis', f"{job_id}_{base_name}.nii.gz")
                if not os.path.exists(result_nifti):
                    return jsonify({'success': False, 'error': f'Result PNG directory not found for {nifti_id}'}), 404

                # Create a new task in CVAT with appropriate labels based on dataset type
                task_name = f"Medical Scan - {base_name}"
                dataset_config = DATASET_CONFIGS[dataset_type]
                create_task_response = requests.post(
                    f"{cvat_api_url}/tasks",
                    headers={**auth_headers, "Content-Type": "application/json"},
                    json={
                        "name": task_name,
                        "labels": [
                            {
                                "name": label,
                                "color": LABEL_COLORS[label],
                                "attributes": []
                            }
                            for label in dataset_config["labels"] if label != "background"
                        ]
                    }
                )
                if create_task_response.status_code != 201:
                    print(f"Task creation failed: {create_task_response.text}")
                    return jsonify({'success': False, 'error': f'Failed to create CVAT task: {create_task_response.text}'}), 400

                task_data = create_task_response.json()
                task_id = task_data['id']

                # Upload original PNG slices as images to the task
                png_files = sorted([f for f in os.listdir(original_png_dir) if f.lower().endswith('.png')])
                temp_upload_dir = os.path.join('/tmp', f'cvat_upload_{job_id}_{base_name}')
                os.makedirs(temp_upload_dir, exist_ok=True)
                for png_file in png_files:
                    shutil.copy2(
                        os.path.join(original_png_dir, png_file),
                        os.path.join(temp_upload_dir, png_file)
                    )
                zip_path = os.path.join('/tmp', f'{job_id}_{base_name}.zip')
                shutil.make_archive(os.path.splitext(zip_path)[0], 'zip', temp_upload_dir)

                with open(zip_path, 'rb') as zip_file:
                    data_upload_response = requests.post(
                        f"{cvat_api_url}/tasks/{task_id}/data",
                        headers=auth_headers,
                        files={'client_files[0]': zip_file},
                        data={
                            'image_quality': 70,
                            'use_zip_chunks': True,
                            'use_cache': True,
                            'chunk_size': 10
                        }
                    )
                if data_upload_response.status_code != 202:
                    print(data_upload_response.text)
                    return jsonify({
                        'success': False,
                        'error': f'Failed to upload data to CVAT task: {data_upload_response.text}'
                    }), 400

                # Generate and save annotations
                coco_data = generate_coco_annotations_from_nifti(result_nifti)
                annotation_path = save_annotations(coco_data, task_id)
                if not annotation_path:
                    raise Exception('Annotation generation failed')

                with open(annotation_path, 'rb') as ann_file:
                    ann_res = requests.put(
                        f"{cvat_api_url}/tasks/{task_id}/annotations?format=COCO%201.0",
                        headers=auth_headers,
                        files={'annotation_file': ann_file}
                    )
                print(ann_res.text)
                if ann_res.status_code not in (200,202):
                    raise Exception(f'Annotation upload failed: {ann_res.text}')

                # Store the created task info locally
                task_info = {
                    'task_id': task_id,
                    'task_name': task_name,
                    'nifti_id': nifti_id,
                    'dataset_type': dataset_type
                }
                
                # For heart dataset, use the base name without UUID
                if dataset_type == "Dataset002_Heart":
                    display_name = re.search(r'la_\d+', base_name)
                    if display_name:
                        base_name = display_name.group(0)
                
                task_file = os.path.join(corrected_tasks_dir, f"{task_id} - {base_name}.json")

                print("Storing task info at:", task_file)
                with open(task_file, "w") as f:
                    json.dump(task_info, f, indent=4)

                uploaded_tasks.append({
                    'task_id': task_id,
                    'task_name': task_name,
                    'redirect_url': f"https://app.cvat.ai/tasks/{task_id}"
                })
            except Exception as e:
                print(f"Error processing {nifti_id}: {str(e)}")
                continue

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




