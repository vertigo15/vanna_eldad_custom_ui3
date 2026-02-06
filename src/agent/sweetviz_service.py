"""Data profiling service using Sweetviz."""

import logging
import tempfile
import os
from typing import Dict, Any
import pandas as pd
import sweetviz as sv

from src.agent.profiling_utils import preprocess_dataset

logger = logging.getLogger(__name__)


async def generate_sweetviz_report(dataset: Dict[str, Any]) -> str:
    """
    Generate a comprehensive data profile report using Sweetviz.
    
    Args:
        dataset: Dictionary with 'rows' (list of lists) and 'columns' (list of column names)
        
    Returns:
        HTML string containing the full profile report
        
    Raises:
        ValueError: If dataset is invalid
        Exception: If profile generation fails
    """
    try:
        # Validate dataset structure
        if not dataset or 'rows' not in dataset or 'columns' not in dataset:
            raise ValueError("Invalid dataset structure. Expected 'rows' and 'columns' keys.")
        
        rows = dataset['rows']
        columns = dataset['columns']
        
        if not rows or not columns:
            raise ValueError("Dataset is empty")
        
        # Preprocess dataset (remove currency signs, combine date columns)
        df, original_columns = preprocess_dataset(dataset)
        
        logger.info(f"Generating Sweetviz report for dataset: {len(df)} rows, {len(df.columns)} columns")
        
        # Determine if sampling is needed for large datasets
        row_count = len(df)
        
        if row_count > 100000:
            # Very large dataset - sample
            logger.warning(f"Large dataset ({row_count:,} rows). Sampling 10,000 rows.")
            df_to_profile = df.sample(min(10000, row_count), random_state=42)
        else:
            df_to_profile = df
        
        # Configure Sweetviz analysis
        # Sweetviz auto-detects feature types
        feature_config = sv.FeatureConfig(skip=None, force_text=None, force_cat=None, force_num=None)
        
        # Generate Sweetviz report
        logger.info("Generating Sweetviz report...")
        report = sv.analyze(
            df_to_profile,
            feat_cfg=feature_config,
            target_feat=None,  # No target variable for general profiling
            pairwise_analysis="off"  # Disable pairwise for faster generation
        )
        
        # Save report to temporary file and read HTML content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Generate HTML file (Sweetviz doesn't have to_html() method)
            report.show_html(filepath=tmp_path, open_browser=False, layout='vertical')
            
            # Read the generated HTML
            with open(tmp_path, 'r', encoding='utf-8') as f:
                html_report = f.read()
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
        logger.info(f"Sweetviz report generated successfully: {len(html_report)} bytes")
        
        return html_report
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to generate Sweetviz report: {e}", exc_info=True)
        raise Exception(f"Sweetviz report generation failed: {str(e)}")
