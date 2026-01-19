"""
API utility functions for processing OMR sheets

This module provides utility functions to process OMR images
and extract responses without needing the full CLI workflow.
"""
import os
from pathlib import Path
import cv2
import tempfile

from src.constants.common import CONFIG_FILENAME, TEMPLATE_FILENAME
from src.defaults import CONFIG_DEFAULTS
from src.template import Template
from src.utils.parsing import open_config_with_defaults, get_concatenated_response


def process_single_omr_image(image_path: str, config_dir: str) -> dict:
    """
    Process a single OMR image and return the detected responses.
    
    Args:
        image_path: Path to the OMR image file
        config_dir: Directory containing config.json and template.json
        
    Returns:
        dict: Dictionary containing the detected responses
        
    Raises:
        Exception: If image processing fails or configuration files are missing
    """
    # Disable OpenCV GUI windows (headless mode)
    os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '0'
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    config_dir_path = Path(config_dir)
    
    # Load configuration
    config_path = config_dir_path.joinpath(CONFIG_FILENAME)
    if not os.path.exists(config_path):
        tuning_config = CONFIG_DEFAULTS
    else:
        tuning_config = open_config_with_defaults(config_path)
    
    # Override display settings for API mode (no GUI)
    tuning_config.outputs.show_image_level = 0
    
    # Load template
    template_path = config_dir_path.joinpath(TEMPLATE_FILENAME)
    if not os.path.exists(template_path):
        raise Exception(f"Template file not found: {template_path}")
    
    template = Template(template_path, tuning_config)
    
    # Read and process the image
    in_omr = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if in_omr is None:
        raise Exception(f"Failed to read image: {image_path}")
    
    # Apply preprocessors
    in_omr = template.image_instance_ops.apply_preprocessors(
        image_path, in_omr, template
    )
    
    if in_omr is None:
        raise Exception("Image preprocessing failed - markers not detected")
    
    # Read OMR response
    file_id = Path(image_path).stem
    (
        response_dict,
        final_marked,
        multi_marked,
        _,
    ) = template.image_instance_ops.read_omr_response(
        template, image=in_omr, name=file_id, save_dir=None
    )
    
    # Get concatenated response
    omr_response = get_concatenated_response(response_dict, template)
    
    return {
        "response": omr_response,
        "multi_marked_count": multi_marked
    }
