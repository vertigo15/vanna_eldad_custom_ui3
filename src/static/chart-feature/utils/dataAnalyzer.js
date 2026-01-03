/**
 * Data Analyzer Utility
 * Detects column types and suggests appropriate chart types
 * 
 * @module dataAnalyzer
 */

/// <reference path="../types/chart.types.js" />

/**
 * Analyzes query results and determines chart suitability
 * 
 * @param {import('../types/chart.types.js').QueryResults} results - Query results to analyze
 * @returns {import('../types/chart.types.js').DataAnalysis} Analysis results
 */
export function analyzeData(results) {
    console.log('[DataAnalyzer] Starting data analysis', results);
    
    if (!results || !results.columns || results.columns.length === 0) {
        return {
            columns: [],
            suggestedChartType: 'bar',
            xAxisColumn: null,
            yAxisColumn: null,
            canChart: false,
            reason: 'No columns found in results'
        };
    }
    
    // Get rows from either 'data' or 'rows' field
    const rows = results.data || results.rows || [];
    
    if (rows.length === 0) {
        return {
            columns: [],
            suggestedChartType: 'bar',
            xAxisColumn: null,
            yAxisColumn: null,
            canChart: false,
            reason: 'No data rows found'
        };
    }
    
    if (results.columns.length === 1) {
        return {
            columns: [],
            suggestedChartType: 'bar',
            xAxisColumn: null,
            yAxisColumn: null,
            canChart: false,
            reason: 'Need at least 2 columns to create a chart'
        };
    }
    
    // Analyze each column
    const columnAnalysis = results.columns.map((colName, index) => 
        analyzeColumn(colName, index, rows, results.columns)
    );
    
    console.log('[DataAnalyzer] Column analysis results:', columnAnalysis);
    
    // Find suitable columns for charting
    const numericColumns = columnAnalysis.filter(col => col.type === 'numeric');
    const categoryColumns = columnAnalysis.filter(col => col.type === 'category');
    const dateColumns = columnAnalysis.filter(col => col.type === 'date');
    
    // Need at least one numeric column
    if (numericColumns.length === 0) {
        return {
            columns: columnAnalysis,
            suggestedChartType: 'bar',
            xAxisColumn: null,
            yAxisColumn: null,
            canChart: false,
            reason: 'No numeric columns found for charting'
        };
    }
    
    // Select X and Y axis columns
    let xAxisColumn = null;
    let yAxisColumn = numericColumns[0]; // First numeric column for Y-axis
    
    // Prefer date columns for X-axis, then category columns
    if (dateColumns.length > 0) {
        xAxisColumn = dateColumns[0];
    } else if (categoryColumns.length > 0) {
        xAxisColumn = categoryColumns[0];
    } else {
        // Use first non-numeric column, or first column if all numeric
        xAxisColumn = columnAnalysis.find(col => col.type !== 'numeric') || columnAnalysis[0];
    }
    
    // Determine suggested chart type
    const suggestedType = suggestChartType(xAxisColumn, yAxisColumn, rows);
    
    console.log('[DataAnalyzer] Suggested chart type:', suggestedType);
    console.log('[DataAnalyzer] X-axis column:', xAxisColumn.name);
    console.log('[DataAnalyzer] Y-axis column:', yAxisColumn.name);
    
    return {
        columns: columnAnalysis,
        suggestedChartType: suggestedType,
        xAxisColumn,
        yAxisColumn,
        canChart: true,
        reason: 'Data is suitable for charting'
    };
}

/**
 * Analyzes a single column to determine its type
 * 
 * @param {string} colName - Column name
 * @param {number} index - Column index
 * @param {Array} rows - Data rows
 * @param {string[]} allColumns - All column names
 * @returns {import('../types/chart.types.js').ColumnInfo}
 */
function analyzeColumn(colName, index, rows, allColumns) {
    const sampleSize = Math.min(20, rows.length);
    const values = [];
    const uniqueValues = new Set();
    
    // Extract column values
    for (let i = 0; i < sampleSize; i++) {
        const row = rows[i];
        let value;
        
        if (Array.isArray(row)) {
            value = row[index];
        } else {
            value = row[colName];
        }
        
        if (value !== null && value !== undefined) {
            values.push(value);
            uniqueValues.add(String(value));
        }
    }
    
    if (values.length === 0) {
        return {
            name: colName,
            type: 'category',
            index,
            uniqueCount: 0
        };
    }
    
    // Detect column type
    const type = detectColumnType(values);
    
    return {
        name: colName,
        type,
        index,
        uniqueCount: uniqueValues.size
    };
}

/**
 * Detects the type of a column based on its values
 * 
 * @param {Array<any>} values - Sample values from the column
 * @returns {import('../types/chart.types.js').ColumnType}
 */
function detectColumnType(values) {
    if (values.length === 0) return 'category';
    
    let numericCount = 0;
    let dateCount = 0;
    
    for (const value of values) {
        // Check if numeric
        if (typeof value === 'number') {
            numericCount++;
            continue;
        }
        
        const strValue = String(value);
        
        // Try to parse as number
        const numValue = parseFloat(strValue.replace(/[^0-9.-]/g, ''));
        if (!isNaN(numValue) && strValue.replace(/[^0-9.-]/g, '') === String(numValue)) {
            numericCount++;
            continue;
        }
        
        // Check if date
        if (isDateString(strValue)) {
            dateCount++;
        }
    }
    
    const numericRatio = numericCount / values.length;
    const dateRatio = dateCount / values.length;
    
    // If more than 50% are numeric, consider it numeric
    if (numericRatio > 0.5) {
        return 'numeric';
    }
    
    // If more than 50% are dates, consider it date
    if (dateRatio > 0.5) {
        return 'date';
    }
    
    return 'category';
}

/**
 * Checks if a string represents a date
 * 
 * @param {string} str - String to check
 * @returns {boolean}
 */
function isDateString(str) {
    // ISO date format
    if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
        return !isNaN(Date.parse(str));
    }
    
    // Common date patterns
    const datePatterns = [
        /^\d{1,2}\/\d{1,2}\/\d{2,4}$/,  // MM/DD/YYYY or DD/MM/YYYY
        /^\d{1,2}-\d{1,2}-\d{2,4}$/,    // MM-DD-YYYY or DD-MM-YYYY
        /^\d{4}\/\d{1,2}\/\d{1,2}$/,    // YYYY/MM/DD
    ];
    
    if (datePatterns.some(pattern => pattern.test(str))) {
        return !isNaN(Date.parse(str));
    }
    
    return false;
}

/**
 * Suggests the most appropriate chart type based on data characteristics
 * 
 * @param {import('../types/chart.types.js').ColumnInfo} xColumn - X-axis column
 * @param {import('../types/chart.types.js').ColumnInfo} yColumn - Y-axis column
 * @param {Array} rows - Data rows
 * @returns {import('../types/chart.types.js').ChartType}
 */
function suggestChartType(xColumn, yColumn, rows) {
    // If X-axis is date/time, suggest line chart
    if (xColumn.type === 'date') {
        console.log('[DataAnalyzer] Suggesting line chart (date column detected)');
        return 'line';
    }
    
    // If X-axis is category with 10 or fewer unique values, suggest pie chart
    if (xColumn.type === 'category' && xColumn.uniqueCount <= 10) {
        console.log('[DataAnalyzer] Suggesting pie chart (few categories)');
        return 'pie';
    }
    
    // If X-axis is category with more than 10 unique values, suggest bar chart
    if (xColumn.type === 'category' && xColumn.uniqueCount > 10) {
        console.log('[DataAnalyzer] Suggesting bar chart (many categories)');
        return 'bar';
    }
    
    // Default to bar chart
    console.log('[DataAnalyzer] Suggesting bar chart (default)');
    return 'bar';
}

/**
 * Extracts data for charting from query results
 * 
 * @param {import('../types/chart.types.js').QueryResults} results - Query results
 * @param {import('../types/chart.types.js').ColumnInfo} xColumn - X-axis column
 * @param {import('../types/chart.types.js').ColumnInfo} yColumn - Y-axis column
 * @returns {{labels: Array<string>, values: Array<number>}}
 */
export function extractChartData(results, xColumn, yColumn) {
    const rows = results.data || results.rows || [];
    const labels = [];
    const values = [];
    
    for (const row of rows) {
        let xValue, yValue;
        
        if (Array.isArray(row)) {
            xValue = row[xColumn.index];
            yValue = row[yColumn.index];
        } else {
            xValue = row[xColumn.name];
            yValue = row[yColumn.name];
        }
        
        // Convert x value to string label
        labels.push(xValue !== null && xValue !== undefined ? String(xValue) : 'N/A');
        
        // Convert y value to number
        const numValue = parseFloat(yValue);
        values.push(isNaN(numValue) ? 0 : numValue);
    }
    
    console.log('[DataAnalyzer] Extracted chart data:', { labelCount: labels.length, valueCount: values.length });
    
    return { labels, values };
}
