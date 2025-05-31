import subprocess
import os
import logging
import glob
from pathlib import Path

# Define dataset-specific configurations
DATASET_CONFIGS = {
    "Dataset001_BrainTumour": {
        "model_folder": "Dataset001_BrainTumour/nnUNet_2d/fold_all",  # Path relative to NNUNET_RESULTS_FOLDER
        "num_channels": 4,  # BRATS typically has 4 channels
        "file_pattern": ["BRATS_*_*.nii.gz", "*_0000.nii.gz"]
    },
    "Dataset002_Heart": {
        "model_folder": "Dataset002_Heart/nnUNet_2d/fold_all",  # Path relative to NNUNET_RESULTS_FOLDER
        "num_channels": 1,  # Heart typically has 1 channel
        "file_pattern": ["la_*_0000.nii.gz"]
    }
}

def verify_model_paths(model_folder: str, dataset: str) -> None:
    """Verify that all required model files exist."""
    required_files = ['dataset.json', f'{DATASET_CONFIGS[dataset]["model_checkpoint"]}.pth']
    for file in required_files:
        file_path = os.path.join(model_folder, file)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Required model file not found: {file_path}")

def run_inference_pipeline(input_dir: str, output_dir: str, config: str, job_id: str, dataset: str = "Dataset001_BrainTumour") -> dict:
    """
    Run nnUNet inference on all NIfTI files in the specified directory.
    
    Parameters:
    -----------
    input_dir : str
        Directory containing NIfTI files to process (including all channels)
    output_dir : str
        Directory where inference results will be saved
    config : str
        Configuration for inference ('2d' or '3d_fullres')
    job_id : str
        Unique identifier for the job
    dataset : str
        Dataset identifier ('Dataset001_BrainTumour' or 'Dataset002_Heart')
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Processing input directory: {input_dir}")
        print(f"Using dataset: {dataset}")
        print(f"Absolute path: {os.path.abspath(input_dir)}")
        print(f"Directory exists? {os.path.exists(input_dir)}")
        print(f"Directory contents: {os.listdir(input_dir)}")
        print(f"Output directory: {output_dir}")
        
        # Verify the input directory is valid
        if not os.path.isdir(input_dir):
            raise ValueError(f"Input path is not a directory: {input_dir}")
        
        # Auto-detect dataset type based on file patterns
        if any(fname.startswith('la_') for fname in os.listdir(input_dir)):
            print("Detected heart dataset based on file patterns")
            dataset = "Dataset002_Heart"
        elif any(fname.startswith('BRATS_') for fname in os.listdir(input_dir)):
            print("Detected brain dataset based on file patterns")
            dataset = "Dataset001_BrainTumour"
        
        # Find all NIfTI files in the input directory
        nifti_files = []
        for ext in ['.nii', '.nii.gz']:
            nifti_files.extend(glob.glob(os.path.join(input_dir, f"*{ext}")))
        
        if not nifti_files:
            error_msg = f"No NIfTI files found in directory: {input_dir}"
            logging.error(error_msg)
            raise ValueError(error_msg)
            
        print(f"Found {len(nifti_files)} NIfTI file(s) to process: {[os.path.basename(f) for f in nifti_files]}")
        
        # Ensure nnUNet environment variables are set with absolute paths
        env = os.environ.copy()
        env["NNUNET_RAW_DATA_BASE"] = os.path.expanduser(os.getenv("NNUNET_RAW_DATA_BASE", "~/Development/DEP_electrical/nnUNet_raw"))
        env["NNUNET_PREPROCESSED"] = os.path.expanduser(os.getenv("NNUNET_PREPROCESSED", "~/Development/DEP_electrical/nnUNet_preprocessed"))
        env["NNUNET_RESULTS_FOLDER"] = os.path.expanduser(os.getenv("NNUNET_RESULTS_FOLDER", "~/Development/DEP_electrical/nnUNet_results"))
        
        # Build the nnUNet command - simplified to match working brain tumor approach
        command = [
            'nnUNetv2_predict',
            '-i', input_dir,
            '-o', output_dir,
            '-d', dataset,
            '-c', config,
            '-f', 'all',
            '--disable_tta'
        ]
        
        print(f"Running command: {' '.join(command)}")
        
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        logging.info(f"Inference completed successfully: {result.stdout}")
        
        # Find output files
        output_files = glob.glob(os.path.join(output_dir, "*.nii.gz"))
        
        return {
            'job_id': job_id,
            'status': 'success',
            'output_dir': output_dir,
            'log': result.stdout,
            'output_files': output_files,
            'dataset': dataset
        }
            
    except subprocess.CalledProcessError as e:
        error_msg = f"Inference failed: {e.stderr}"
        logging.error(error_msg)
        return {
            'job_id': job_id,
            'status': 'failed',
            'error': error_msg,
            'dataset': dataset
        }
    except Exception as e:
        error_msg = f"Unexpected error during inference: {str(e)}"
        logging.error(error_msg)
        return {
            'job_id': job_id,
            'status': 'failed',
            'error': error_msg,
            'dataset': dataset
        }
