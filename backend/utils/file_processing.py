import os
import zipfile
import nibabel as nib
import numpy as np
from PIL import Image
import shutil
import imageio
from glob import glob
import re
import matplotlib.pyplot as plt

def find_modality_folders(root_dir: str) -> dict:
    """
    Recursively search for directories whose names contain a 4-digit identifier 
    (e.g. "modality_0000" or "0000"). Returns a dictionary mapping the 4-digit code
    to its folder path.
    """
    modality_folders = {}
    # Match any string that ends with 4 digits.
    pattern = re.compile(r'.*?(\d{4})$')
    for item in os.listdir(root_dir):
        full_path = os.path.join(root_dir, item)
        if os.path.isdir(full_path):
            match = pattern.match(item)
            if match:
                modality = match.group(1)
                modality_folders[modality] = full_path
            else:
                # Recursively check subdirectories.
                sub_mods = find_modality_folders(full_path)
                if sub_mods:
                    modality_folders.update(sub_mods)
    return modality_folders

def convert_to_nifti(png_dir: str, output_path: str = None) -> str:
    """
    Convert a directory of PNG slices into a single-channel NIfTI file.
    
    Reads all PNG files (in sorted order) from png_dir in grayscale,
    stacks them into a 3D volume (D, H, W), permutes to (H, W, D),
    and then adds a new dimension to create shape (H, W, D).
    The resulting NIfTI file is saved with a modality suffix if no output_path is provided.
    """
    # Gather PNG files
    png_files = sorted(glob(os.path.join(png_dir, "*.png")))
    if not png_files:
        raise ValueError(f"No PNG files found in {png_dir}")
    print(f"Found {len(png_files)} PNG files in {png_dir} to convert.")
    
    # Read first image to determine dimensions
    first_img = np.array(Image.open(png_files[0]).convert('L'))
    H, W = first_img.shape
    num_slices = len(png_files)
    volume = np.zeros((num_slices, H, W), dtype=np.float64)
    
    for i, f in enumerate(png_files):
        img = Image.open(f).convert('L')
        arr = np.array(img, dtype=np.float64)
        # Normalize each slice to [0,1] (if any nonzero pixel exists)
        if arr.max() > 0:
            arr = arr / arr.max()
        volume[i,:,:] = arr
    
    # Permute dimensions: (D, H, W) -> (H, W, D)
    volume = np.transpose(volume, (1, 2, 0))
    
    if output_path is None:
        output_path = os.path.join(os.path.dirname(png_dir), f"{os.path.basename(png_dir)}_0000.nii.gz")
    
    affine = np.eye(4)
    nifti_img = nib.Nifti1Image(volume, affine)
    nifti_img.set_data_dtype(np.float64)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    nib.save(nifti_img, output_path)
    print(f"Successfully converted PNG slices from {png_dir} to NIfTI file: {output_path}")
    return output_path

def convert_modality_png_folders_to_nifti(png_folder_dict: dict, output_dir: str, job_id: str) -> dict:
    """
    Convert each modality PNG folder (each representing one channel) into a separate
    single-channel NIfTI file. Files are named as:
      brats_<job_id>_<modality>.nii.gz
    where <modality> is the extracted 4-digit code.
    """
    result = {}
    os.makedirs(output_dir, exist_ok=True)
    for modality, folder in png_folder_dict.items():
        output_path = os.path.join(output_dir, f"brats_{job_id}_{modality}.nii.gz")
        print(f"Converting modality {modality} from folder {folder} to NIfTI...")
        convert_to_nifti(folder, output_path)
        result[modality] = output_path
        print(f"Saved modality {modality} as {output_path}")
    return result

def nifti_to_png_slices(
    nifti_path: str, 
    output_dir: str, 
    use_viridis: bool = False, 
    transparent_bg: bool = False
) -> str:
    """
    Convert a single-channel NIfTI file to a set of PNG slices for UI display.
    Supports optional viridis colormap and transparent background where pixel intensity == 0.

    Parameters:
    - nifti_path: path to the NIfTI file
    - output_dir: directory to save PNG slices
    - use_viridis: if True, apply viridis colormap
    - transparent_bg: if True, make pixels with original intensity == 0 transparent
    """
    os.makedirs(output_dir, exist_ok=True)
    nifti_img = nib.load(nifti_path)
    data = nifti_img.get_fdata()
    
    num_slices = data.shape[2]
    for i in range(num_slices):
        slice_data = data[:, :, i]

        # Store original mask for transparency (before normalization)
        if transparent_bg:
            zero_mask = (slice_data != 0).astype(np.uint8) * 255

        # Normalize the data
        if slice_data.max() - slice_data.min() > 1e-6:
            normalized = (slice_data - slice_data.min()) / (slice_data.max() - slice_data.min())
        else:
            normalized = slice_data

        if use_viridis:
            colormap = plt.get_cmap('viridis')
            colored = colormap(normalized)[:, :, :3]  # RGB only
            rgb_slice = (colored * 255).astype(np.uint8)
        else:
            gray_slice = (normalized * 255).astype(np.uint8)
            rgb_slice = np.stack([gray_slice]*3, axis=-1)  # Convert grayscale to RGB

        if transparent_bg:
            rgba_slice = np.dstack((rgb_slice, zero_mask)).astype(np.uint8)
            img = Image.fromarray(rgba_slice, mode='RGBA')
        else:
            img = Image.fromarray(rgb_slice, mode='RGB')

        slice_path = os.path.join(output_dir, f"slice_{i:04d}.png")
        img.save(slice_path)

    print(f"Successfully converted NIfTI {nifti_path} to {num_slices} PNG slices in {output_dir}")
    return output_dir


def process_upload(zip_path: str, output_dir: str) -> dict:
    """
    Process an uploaded ZIP file containing either NIfTI files or image folders.
    
    If NIfTI files are present in the ZIP, they are used directly.
    Otherwise, if modality folders (e.g. folders ending with 4-digit codes such as "0000", "0001", etc.)
    are detected, each folder is processed and converted to a single-channel NIfTI file.
    
    The output files are placed in the inference directory and UI display directories as needed.
    """
    # Create output directories
    niftis_dir = os.path.join(output_dir, 'niftis')
    pngs_dir   = os.path.join(output_dir, 'pngs')
    os.makedirs(niftis_dir, exist_ok=True)
    os.makedirs(pngs_dir, exist_ok=True)
    
    # Generate job ID from ZIP filename
    job_id = os.path.basename(zip_path).split('.')[0]
    
    # Create temporary extraction and inference directories
    temp_extract_dir = os.path.join(output_dir, f'temp_extract_{job_id}')
    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir)
    os.makedirs(temp_extract_dir, exist_ok=True)
    
    inference_dir = os.path.join(output_dir, f'inference_temp_{job_id}')
    if os.path.exists(inference_dir):
        shutil.rmtree(inference_dir)
    os.makedirs(inference_dir, exist_ok=True)
    
    # Extract ZIP contents
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract_dir)
    
    result = {
        'nifti_paths': [],
        'png_dirs': [],
        'job_id': job_id,
        'inference_dir': inference_dir
    }
    
    # STEP 1: If NIfTI files already exist, use them directly.
    all_nifti_files = []
    channel0_nifti_files = []
    for root, _, files in os.walk(temp_extract_dir):
        for file in files:
            if file.lower().endswith(('.nii', '.nii.gz')):
                full_path = os.path.join(root, file)
                all_nifti_files.append(full_path)
                filename, ext = os.path.splitext(file)
                if ext == '.gz':
                    filename, _ = os.path.splitext(filename)
                if filename.endswith('_0000') or not any(ch.isdigit() for ch in filename.split('_')[-1]):
                    channel0_nifti_files.append(full_path)

    if all_nifti_files:
        for nifti_file in all_nifti_files:
            file_name = os.path.basename(nifti_file)
            inf_path = os.path.join(inference_dir, file_name)
            shutil.copy2(nifti_file, inf_path)
            print(f"Copied NIfTI {file_name} to inference directory.")
        for src_nifti in channel0_nifti_files:
            file_name = os.path.basename(src_nifti)
            base_name = os.path.splitext(file_name)[0]
            if base_name.lower().endswith('.nii'):
                base_name = os.path.splitext(base_name)[0]
            dest_nifti = os.path.join(niftis_dir, f"{job_id}_{file_name}")
            shutil.copy2(src_nifti, dest_nifti)
            result['nifti_paths'].append(dest_nifti)
            png_subfolder = os.path.join(pngs_dir, f"{job_id}_{base_name}")
            os.makedirs(png_subfolder, exist_ok=True)
            print("to be converted")
            nifti_to_png_slices(src_nifti, png_subfolder, False, False)
            result['png_dirs'].append(png_subfolder)
    print("pngs converted")
    # STEP 1.5: If no NIfTI files, try processing modality PNG folders.
    modality_folders = find_modality_folders(temp_extract_dir)
    modality_processed = False
    if modality_folders and not all_nifti_files:
        print("Detected modality folders:", modality_folders)
        modality_nifti_files = convert_modality_png_folders_to_nifti(modality_folders, niftis_dir, job_id)
        for mod, nifti_path in modality_nifti_files.items():
            result['nifti_paths'].append(nifti_path)
            # Copy the modality folder for UI display.
            dest_png = os.path.join(pngs_dir, f"{job_id}_{mod}")
            shutil.copytree(modality_folders[mod], dest_png)
            result['png_dirs'].append(dest_png)
            # Also copy the generated NIfTI file to inference directory with required naming.
            inf_nifti = os.path.join(inference_dir, f"brats_{job_id}_{mod}.nii.gz")
            shutil.copy2(nifti_path, inf_nifti)
        modality_processed = True
    
    # STEP 2: Fallback processing for standalone PNG folders.
    if not all_nifti_files and not modality_processed:
        png_folders = set()
        for root, _, files in os.walk(temp_extract_dir):
            if any(f.lower().endswith('.png') for f in files):
                png_folders.add(root)
        for png_folder in png_folders:
            folder_name = os.path.basename(png_folder)
            png_job_dir = os.path.join(pngs_dir, f"{job_id}_{folder_name}")
            os.makedirs(png_job_dir, exist_ok=True)
            for png_file in [os.path.join(png_folder, f) for f in os.listdir(png_folder) if f.lower().endswith('.png')]:
                dest_png = os.path.join(png_job_dir, os.path.basename(png_file))
                shutil.copy2(png_file, dest_png)
            result['png_dirs'].append(png_job_dir)
            dest_nifti = os.path.join(niftis_dir, f"{job_id}_{folder_name}_0000.nii.gz")
            convert_to_nifti(png_job_dir, dest_nifti)
            result['nifti_paths'].append(dest_nifti)
            inf_nifti = os.path.join(inference_dir, f"{folder_name}_0000.nii.gz")
            shutil.copy2(dest_nifti, inf_nifti)
    
    # STEP 3: Also process JPEG/TIFF image folders if present.
    other_image_folders = set()
    for root, _, files in os.walk(temp_extract_dir):
        if any(f.lower().endswith(('.jpg', '.jpeg', '.tiff', '.tif')) for f in files):
            other_image_folders.add(root)
    for other_folder in other_image_folders:
        folder_name = os.path.basename(other_folder)
        png_job_dir = os.path.join(pngs_dir, f"{job_id}_{folder_name}_converted")
        os.makedirs(png_job_dir, exist_ok=True)
        for file in os.listdir(other_folder):
            if file.lower().endswith(('.jpg', '.jpeg', '.tiff', '.tif')):
                file_path = os.path.join(other_folder, file)
                try:
                    with Image.open(file_path) as img:
                        img = img.convert('RGB')
                        png_filename = os.path.splitext(file)[0] + ".png"
                        dest_png = os.path.join(png_job_dir, png_filename)
                        img.save(dest_png, format='PNG')
                except Exception as e:
                    print(f"Error converting {file_path} to PNG: {e}")
        result['png_dirs'].append(png_job_dir)
        dest_nifti = os.path.join(niftis_dir, f"{job_id}_{folder_name}_converted_0000.nii.gz")
        convert_to_nifti(png_job_dir, dest_nifti)
        result['nifti_paths'].append(dest_nifti)
        inf_nifti = os.path.join(inference_dir, f"{folder_name}_converted_0000.nii.gz")
        shutil.copy2(dest_nifti, inf_nifti)
    
    # Clean up temporary extracted files and the input ZIP.
    shutil.rmtree(temp_extract_dir)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    
    if not result['nifti_paths'] and not os.listdir(inference_dir):
        shutil.rmtree(inference_dir)
        raise ValueError("No valid PNG slices or NIfTI files found in uploaded ZIP.")
    
    if result['nifti_paths']:
        result['nifti_path'] = result['nifti_paths'][0]
    if result['png_dirs']:
        result['png_dir'] = result['png_dirs'][0]
    
    return result
