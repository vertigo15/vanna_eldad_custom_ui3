"""Data profiling service using ydata-profiling."""

import logging
from typing import Dict, Any, List
import pandas as pd
from ydata_profiling import ProfileReport

from src.agent.profiling_utils import preprocess_dataset

logger = logging.getLogger(__name__)


async def generate_profile_report(dataset: Dict[str, Any]) -> str:
    """
    Generate a comprehensive data profile report using ydata-profiling.
    
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
        
        logger.info(f"Generating profile report for dataset: {len(df)} rows, {len(df.columns)} columns")
        
        # Determine profiling mode based on dataset size
        row_count = len(df)
        
        if row_count > 100000:
            # Very large dataset - sample and use minimal mode
            logger.warning(f"Large dataset ({row_count:,} rows). Sampling 10,000 rows.")
            df_to_profile = df.sample(min(10000, row_count), random_state=42)
            minimal_mode = True
            explorative_mode = False
        elif row_count > 10000:
            # Large dataset - use minimal mode
            logger.info(f"Dataset has {row_count:,} rows. Using minimal profiling mode.")
            df_to_profile = df
            minimal_mode = True
            explorative_mode = False
        else:
            # Small dataset - full profiling
            df_to_profile = df
            minimal_mode = False
            explorative_mode = True
        
        # Configure profiling options
        profile_config = {
            "title": "Query Results Profile",
            "minimal": minimal_mode,
            "explorative": explorative_mode,
            "correlations": {
                "pearson": {"calculate": True},
                "spearman": {"calculate": explorative_mode},
                "kendall": {"calculate": False},
                "phi_k": {"calculate": False},
            },
            "missing_diagrams": {
                "heatmap": explorative_mode,
                "bar": True,
            },
            "samples": {
                "head": 10,
                "tail": 10,
            },
            "duplicates": {
                "head": 10,
            }
        }
        
        # Generate profile report
        logger.info("Generating profile report...")
        profile = ProfileReport(df_to_profile, **profile_config)
        
        # Convert to HTML
        html_report = profile.to_html()
        
        logger.info(f"Profile report generated successfully: {len(html_report)} bytes")
        
        return html_report
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to generate profile report: {e}", exc_info=True)
        raise Exception(f"Profile generation failed: {str(e)}")


def _determine_profiling_mode(row_count: int) -> Dict[str, Any]:
    """
    Determine profiling configuration based on dataset size.
    
    Args:
        row_count: Number of rows in dataset
        
    Returns:
        Dictionary with profiling configuration
    """
    if row_count > 100000:
        return {
            "mode": "minimal",
            "sample_size": 10000,
            "explorative": False,
            "warning": f"Large dataset ({row_count:,} rows). Profiling a sample of 10,000 rows."
        }
    elif row_count > 10000:
        return {
            "mode": "minimal",
            "sample_size": None,
            "explorative": False,
            "warning": f"Dataset has {row_count:,} rows. Using minimal profiling mode."
        }
    else:
        return {
            "mode": "full",
            "sample_size": None,
            "explorative": True,
            "warning": None
        }
