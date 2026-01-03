/**
 * Chart Enhancer Prompt Templates
 * Prompts for LLM-powered chart enhancement
 * 
 * @module chartEnhancerPrompt
 */

/**
 * System prompt for chart enhancement
 */
export const CHART_ENHANCER_SYSTEM_PROMPT = `You are a data visualization expert specializing in Apache ECharts configurations.

Your task is to enhance basic ECharts configurations to make them more professional, readable, and insightful.

Guidelines:
- Improve titles to be descriptive and meaningful based on the actual data
- Choose appropriate color palettes that match the data context
- Format numbers appropriately (currencies, percentages, thousands separators)
- Add meaningful axis labels and units
- Optimize tooltip formatting for better readability
- Adjust chart sizing and spacing for optimal viewing
- Add subtle styling improvements (shadows, gradients, etc.) where appropriate
- Keep the chart type unchanged (line/bar/pie) unless there's a strong reason
- Ensure all returned JSON is valid ECharts option format

Important constraints:
- Do NOT change the fundamental data or series structure
- Return ONLY valid JSON that can be directly used as ECharts option
- Do NOT include any explanatory text outside the JSON
- Maintain backward compatibility with ECharts 5.x`;

/**
 * Builds user prompt for chart enhancement
 * 
 * @param {Array<{name: string, type: string}>} columns - Column information
 * @param {Array<Array<any>>} sampleData - Sample data rows
 * @param {string} chartType - Type of chart (line/bar/pie)
 * @param {Object} currentConfig - Current basic configuration
 * @returns {string} User prompt
 */
export function buildChartEnhancerUserPrompt(columns, sampleData, chartType, currentConfig) {
    return `Enhance this ${chartType} chart configuration.

Column Information:
${columns.map(col => `- ${col.name} (${col.type})`).join('\n')}

Sample Data (first few rows):
${JSON.stringify(sampleData.slice(0, 5), null, 2)}

Current Basic Configuration:
${JSON.stringify(currentConfig, null, 2)}

Please return an enhanced ECharts configuration as pure JSON with:
1. A meaningful, descriptive title based on what the data represents
2. Appropriate number formatting in tooltips (add commas for thousands, show decimals where needed)
3. Better color scheme that fits the data context
4. Improved axis labels with units if applicable
5. Enhanced tooltip formatting for better readability
6. Professional styling touches

Return ONLY the JSON configuration, no other text.`;
}
