import os
import subprocess
from flask import Blueprint, request, jsonify, current_app

nnunet_bp = Blueprint('nnunet', __name__)

@nnunet_bp.route('/train-nnunet', methods=['POST'])
def train_nnunet():
    """
    Expects JSON:
    {
      "dataset_id": <int>,            # e.g. 1 for Dataset001_BrainTumour, 2 for Dataset002_Heart
      "resolution": "2d"|"3d"|"3d_fullres",
      "folds": <int> or "all",
      "trainer_class": "<string>"     # optional, e.g. "nnUNetTrainer_1epoch"
    }
    Runs nnUNetv2_plan_and_preprocess and then nnUNetv2_train for one epoch.
    """
    data = request.get_json() or {}
    dataset_id    = data.get("dataset_id")
    resolution    = data.get("resolution", "3d_fullres")
    folds         = data.get("folds", "all")
    trainer_class = data.get("trainer_class", "nnUNetTrainer_1epoch")

    # Validate
    if not isinstance(dataset_id, int):
        return jsonify({"error": "dataset_id (integer) is required"}), 400
    if resolution not in ("2d", "3d", "3d_fullres"):
        return jsonify({"error": "resolution must be one of 2d, 3d, 3d_fullres"}), 400

    # build fold list
    if folds == "all":
        fold_list = ["all"]
    else:
        try:
            fold_list = [str(int(folds))]
        except:
            return jsonify({"error": "folds must be an integer or 'all'"}), 400

    cwd = os.path.abspath(os.getcwd())

    try:
        # 1) Preprocessing
        preprocess_cmd = [
            "nnUNetv2_plan_and_preprocess",
            "-d", str(dataset_id)      # dataset ID is integer :contentReference[oaicite:0]{index=0}
        ]
        current_app.logger.info("Running preprocess: %s", " ".join(preprocess_cmd))
        subprocess.run(preprocess_cmd, check=True, cwd=cwd)  # :contentReference[oaicite:1]{index=1}

        # 2) Training each fold (one epoch via trainer_class)
        for fold in fold_list:
            train_cmd = [
                "nnUNetv2_train",
                str(dataset_id),
                resolution,
                fold,
                "-tr", trainer_class
            ]
            current_app.logger.info("Running train: %s", " ".join(train_cmd))
            subprocess.run(train_cmd, check=True, cwd=cwd)

        return jsonify({
            "message": f"nnU‑Net V2 run for dataset {dataset_id}, res {resolution}, folds {fold_list}"
        }), 200

    except subprocess.CalledProcessError as e:
        current_app.logger.error("Subprocess error: %s", str(e))
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        current_app.logger.error("Unexpected error: %s", str(e))
        return jsonify({"error": str(e)}), 500
