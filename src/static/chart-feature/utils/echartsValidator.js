/**
 * ECharts Validator Utility
 * Validates ECharts configuration objects
 * 
 * @module echartsValidator
 */

/// <reference path="../types/chart.types.js" />

/**
 * Validates an ECharts configuration object
 * 
 * @param {any} config - Configuration to validate
 * @returns {{valid: boolean, error: string|null, config: import('../types/chart.types.js').EChartsOption|null}}
 */
export function validateEChartsConfig(config) {
    console.log('[EChartsValidator] Validating config:', config);
    
    // Check if config exists and is an object
    if (!config || typeof config !== 'object') {
        return {
            valid: false,
            error: 'Config is not an object',
            config: null
        };
    }
    
    // Check for series (required for any chart)
    if (!config.series || !Array.isArray(config.series) || config.series.length === 0) {
        return {
            valid: false,
            error: 'Config must have at least one series',
            config: null
        };
    }
    
    // Validate each series
    for (let i = 0; i < config.series.length; i++) {
        const series = config.series[i];
        
        if (!series.type) {
            return {
                valid: false,
                error: `Series ${i} missing required 'type' field`,
                config: null
            };
        }
        
        if (!series.data && !series.encode) {
            return {
                valid: false,
                error: `Series ${i} missing 'data' field`,
                config: null
            };
        }
    }
    
    // For bar and line charts, validate axes
    const hasBarOrLine = config.series.some(s => s.type === 'bar' || s.type === 'line');
    if (hasBarOrLine) {
        if (!config.xAxis && !config.radiusAxis) {
            console.warn('[EChartsValidator] Warning: bar/line chart without xAxis');
        }
        if (!config.yAxis && !config.angleAxis) {
            console.warn('[EChartsValidator] Warning: bar/line chart without yAxis');
        }
    }
    
    // Validation passed
    console.log('[EChartsValidator] Config is valid');
    return {
        valid: true,
        error: null,
        config: config
    };
}

/**
 * Sanitizes an ECharts config to ensure it's safe and valid
 * 
 * @param {any} config - Config to sanitize
 * @returns {import('../types/chart.types.js').EChartsOption}
 */
export function sanitizeEChartsConfig(config) {
    console.log('[EChartsValidator] Sanitizing config');
    
    // Deep clone to avoid modifying original
    const sanitized = JSON.parse(JSON.stringify(config));
    
    // Remove any potentially dangerous function references
    removeNonSerializableFields(sanitized);
    
    // Ensure basic structure
    if (!sanitized.series) {
        sanitized.series = [];
    }
    
    // Add default tooltip if not present
    if (!sanitized.tooltip) {
        sanitized.tooltip = {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow'
            }
        };
    }
    
    // Add default grid for spacing if not present
    if (!sanitized.grid && (sanitized.xAxis || sanitized.yAxis)) {
        sanitized.grid = {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        };
    }
    
    console.log('[EChartsValidator] Config sanitized');
    return sanitized;
}

/**
 * Recursively removes non-serializable fields from an object
 * 
 * @param {Object} obj - Object to clean
 */
function removeNonSerializableFields(obj) {
    for (const key in obj) {
        if (typeof obj[key] === 'function') {
            delete obj[key];
        } else if (typeof obj[key] === 'object' && obj[key] !== null) {
            removeNonSerializableFields(obj[key]);
        }
    }
}

/**
 * Validates LLM response for chart enhancement
 * 
 * @param {any} response - Response from LLM API
 * @returns {{valid: boolean, error: string|null, config: import('../types/chart.types.js').EChartsOption|null}}
 */
export function validateEnhancementResponse(response) {
    console.log('[EChartsValidator] Validating enhancement response');
    
    if (!response) {
        return {
            valid: false,
            error: 'Empty response from enhancement API',
            config: null
        };
    }
    
    if (response.error) {
        return {
            valid: false,
            error: response.error,
            config: null
        };
    }
    
    if (!response.enhanced_config) {
        return {
            valid: false,
            error: 'No enhanced_config in response',
            config: null
        };
    }
    
    // Validate the enhanced config
    return validateEChartsConfig(response.enhanced_config);
}
