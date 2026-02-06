"""Shared data preprocessing utilities for profiling services."""

import logging
import re
from typing import Dict, Any, List, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


def preprocess_dataset(dataset: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    """
    Preprocess dataset for profiling:
    1. Remove currency signs from numeric columns
    2. Combine year/month columns into a single date column
    
    Args:
        dataset: Dictionary with 'rows' (list of lists) and 'columns' (list of column names)
        
    Returns:
        Tuple of (preprocessed DataFrame, list of original column names)
    """
    rows = dataset['rows']
    columns = dataset['columns']
    
    # Create DataFrame
    df = pd.DataFrame(rows, columns=columns)
    original_columns = columns.copy()
    
    logger.info(f"Preprocessing dataset: {len(df)} rows, {len(df.columns)} columns")
    
    # Step 1: Remove currency signs from columns
    df = remove_currency_signs(df)
    
    # Step 2: Combine year/month columns if they exist
    df = combine_date_columns(df)
    
    logger.info(f"After preprocessing: {len(df)} rows, {len(df.columns)} columns")
    
    return df, original_columns


def remove_currency_signs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove currency symbols ($, €, £, ¥, etc.) and commas from string columns
    and convert them to numeric if possible.
    
    Args:
        df: Input DataFrame
        
    Returns:
        DataFrame with currency signs removed
    """
    currency_pattern = re.compile(r'[$€£¥₹₽₩¢,]')
    
    for col in df.columns:
        if df[col].dtype == 'object':
            # Check if column contains currency values
            sample = df[col].dropna().head(20)
            has_currency = sample.astype(str).str.contains(currency_pattern).any()
            
            if has_currency:
                logger.info(f"Removing currency signs from column: {col}")
                # Remove currency symbols and commas
                cleaned = df[col].astype(str).str.replace(currency_pattern, '', regex=True).str.strip()
                # Try to convert to numeric
                try:
                    df[col] = pd.to_numeric(cleaned, errors='coerce')
                    # If too many NaN values, revert to original
                    if df[col].isna().sum() > len(df) * 0.5:
                        df[col] = cleaned
                except Exception:
                    df[col] = cleaned
    
    return df


def combine_date_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect and combine separate year/month/day columns into a single date column.
    
    Detection patterns:
    - Year: "year", "yr", "fiscal_year", "fy", "calendaryear"
    - Month: "month", "month_id", "month_num", "mm", "month_name", "month_abbr", "monthid"
    - Day: "day", "dd", "day_of_month"
    - Quarter: "quarter", "qtr", "q"
    
    Args:
        df: Input DataFrame
        
    Returns:
        DataFrame with combined date column (if applicable)
    """
    columns_lower = {col: col.lower().replace('_', '').replace(' ', '') for col in df.columns}
    
    # Detection patterns
    year_patterns = ['year', 'yr', 'fiscalyear', 'fy', 'calendaryear']
    month_patterns = ['month', 'monthid', 'monthnum', 'mm', 'monthname', 'monthabbr']
    day_patterns = ['day', 'dd', 'dayofmonth']
    quarter_patterns = ['quarter', 'qtr', 'q']
    
    # Find matching columns
    year_col = None
    month_col = None
    month_name_col = None
    day_col = None
    quarter_col = None
    
    for col, col_lower in columns_lower.items():
        # Check for year column
        if not year_col:
            for pattern in year_patterns:
                if col_lower == pattern or col_lower.endswith(pattern):
                    year_col = col
                    break
        
        # Check for month column (prefer numeric month over name)
        if col_lower in ['month', 'monthid', 'monthnum', 'mm']:
            month_col = col
        elif col_lower in ['monthname', 'monthabbr'] and not month_col:
            month_name_col = col
        
        # Check for day column
        if not day_col:
            for pattern in day_patterns:
                if col_lower == pattern:
                    day_col = col
                    break
        
        # Check for quarter column
        if not quarter_col:
            for pattern in quarter_patterns:
                if col_lower == pattern:
                    quarter_col = col
                    break
    
    # Use month name if no numeric month found
    if not month_col and month_name_col:
        month_col = month_name_col
    
    # If we have year and month, combine them
    if year_col and month_col:
        logger.info(f"Combining date columns: year={year_col}, month={month_col}")
        
        try:
            # Convert month to numeric if it's a name
            month_values = df[month_col].copy()
            if month_values.dtype == 'object':
                month_values = convert_month_name_to_number(month_values)
            
            # Create combined date column
            if day_col:
                # Year/Month/Day format
                df['date'] = df[year_col].astype(str) + '/' + \
                             month_values.astype(int).astype(str).str.zfill(2) + '/' + \
                             df[day_col].astype(int).astype(str).str.zfill(2)
            else:
                # Year/Month format
                df['date'] = df[year_col].astype(str) + '/' + \
                             month_values.astype(int).astype(str).str.zfill(2)
            
            # Remove original date component columns
            cols_to_drop = [year_col, month_col]
            if month_name_col and month_name_col != month_col:
                cols_to_drop.append(month_name_col)
            if day_col:
                cols_to_drop.append(day_col)
            
            # Only drop columns that exist
            cols_to_drop = [c for c in cols_to_drop if c in df.columns]
            df = df.drop(columns=cols_to_drop)
            
            # Move date column to the front
            cols = ['date'] + [c for c in df.columns if c != 'date']
            df = df[cols]
            
            logger.info(f"Created combined 'date' column, removed: {cols_to_drop}")
            
        except Exception as e:
            logger.warning(f"Failed to combine date columns: {e}")
    
    elif year_col and quarter_col:
        logger.info(f"Combining date columns: year={year_col}, quarter={quarter_col}")
        
        try:
            # Year/Quarter format
            df['date'] = df[year_col].astype(str) + '/Q' + df[quarter_col].astype(int).astype(str)
            
            # Remove original columns
            df = df.drop(columns=[year_col, quarter_col])
            
            # Move date column to the front
            cols = ['date'] + [c for c in df.columns if c != 'date']
            df = df[cols]
            
            logger.info(f"Created combined 'date' column from year and quarter")
            
        except Exception as e:
            logger.warning(f"Failed to combine year/quarter columns: {e}")
    
    return df


def convert_month_name_to_number(series: pd.Series) -> pd.Series:
    """
    Convert month names/abbreviations to numeric values.
    
    Args:
        series: Pandas Series with month names
        
    Returns:
        Series with numeric month values
    """
    month_map = {
        # Full names
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        # Abbreviations
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9,
        'oct': 10, 'nov': 11, 'dec': 12
    }
    
    def convert_month(val):
        if pd.isna(val):
            return val
        
        # Try direct numeric conversion first
        try:
            num = int(float(val))
            if 1 <= num <= 12:
                return num
        except (ValueError, TypeError):
            pass
        
        # Try month name lookup
        val_lower = str(val).lower().strip()
        return month_map.get(val_lower, val)
    
    return series.apply(convert_month)
