/**
 * Chart Enhancer Service (Tier 2)
 * Calls API to enhance charts with LLM
 * 
 * @module chartEnhancerService
 */

/// <reference path="../types/chart.types.js" />

import { validateEnhancementResponse, sanitizeEChartsConfig } from '../utils/echartsValidator.js';

/**
 * Enhances a chart configuration using LLM
 * 
 * @param {import('../types/chart.types.js').EnhanceChartRequest} request - Enhancement request
 * @returns {Promise<import('../types/chart.types.js').ChartConfig>} Enhanced chart config
 */
export async function enhanceChart(request) {
    console.log('[ChartEnhancerService] Starting chart enhancement');
    console.log('[ChartEnhancerService] Request:', {
        chartType: request.chart_type,
        columnCount: request.columns.length,
        sampleDataRows: request.sample_data.length
    });
    
    try {
        const response = await fetch('/api/enhance-chart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
            signal: AbortSignal.timeout(30000) // 30 second timeout
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP error ${response.status}`);
        }
        
        const data = await response.json();
        console.log('[ChartEnhancerService] Received response from API');
        
        // Validate the response
        const validation = validateEnhancementResponse(data);
        
        if (!validation.valid) {
            console.error('[ChartEnhancerService] Invalid response:', validation.error);
            throw new Error(`Invalid enhancement response: ${validation.error}`);
        }
        
        // Sanitize the config
        const sanitized = sanitizeEChartsConfig(validation.config);
        
        console.log('[ChartEnhancerService] Enhancement successful');
        
        return {
            type: request.chart_type,
            options: sanitized,
            isEnhanced: true
        };
        
    } catch (error) {
        console.error('[ChartEnhancerService] Enhancement failed:', error);
        
        // Re-throw with more context
        if (error.name === 'AbortError' || error.name === 'TimeoutError') {
            throw new Error('Enhancement request timed out');
        }
        
        throw error;
    }
}

/**
 * Prepares sample data for enhancement request
 * 
 * @param {import('../types/chart.types.js').QueryResults} results - Query results
 * @param {number} maxRows - Maximum number of rows to include
 * @returns {Array<Array<any>>} Sample data
 */
export function prepareSampleData(results, maxRows = 10) {
    const rows = results.data || results.rows || [];
    const sampleRows = rows.slice(0, maxRows);
    
    // Convert to array format if needed
    if (sampleRows.length > 0 && !Array.isArray(sampleRows[0])) {
        // Object format, convert to arrays
        return sampleRows.map(row => 
            results.columns.map(col => row[col])
        );
    }
    
    return sampleRows;
}

/**
 * Prepares column information for enhancement request
 * 
 * @param {import('../types/chart.types.js').DataAnalysis} analysis - Data analysis
 * @returns {Array<{name: string, type: string}>} Column info
 */
export function prepareColumnInfo(analysis) {
    return analysis.columns.map(col => ({
        name: col.name,
        type: col.type
    }));
}
