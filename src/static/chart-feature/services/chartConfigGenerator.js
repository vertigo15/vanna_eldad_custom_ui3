/**
 * Chart Config Generator Service (Tier 1)
 * Auto-generates basic ECharts configurations from query results
 * 
 * @module chartConfigGenerator
 */

/// <reference path="../types/chart.types.js" />

import { extractChartData } from '../utils/dataAnalyzer.js';

/**
 * Generates a basic ECharts configuration
 * 
 * @param {import('../types/chart.types.js').ChartType} chartType - Type of chart to generate
 * @param {import('../types/chart.types.js').QueryResults} results - Query results
 * @param {import('../types/chart.types.js').DataAnalysis} analysis - Data analysis results
 * @returns {import('../types/chart.types.js').ChartConfig}
 */
export function generateChartConfig(chartType, results, analysis) {
    console.log(`[ChartConfigGenerator] Generating ${chartType} chart config`);
    
    if (!analysis.canChart || !analysis.xAxisColumn || !analysis.yAxisColumn) {
        throw new Error('Data is not suitable for charting');
    }
    
    // Extract data for the chart
    const { labels, values } = extractChartData(results, analysis.xAxisColumn, analysis.yAxisColumn);
    
    let options;
    
    switch (chartType) {
        case 'line':
            options = generateLineChart(labels, values, analysis);
            break;
        case 'bar':
            options = generateBarChart(labels, values, analysis);
            break;
        case 'pie':
            options = generatePieChart(labels, values, analysis);
            break;
        default:
            throw new Error(`Unsupported chart type: ${chartType}`);
    }
    
    console.log('[ChartConfigGenerator] Config generated successfully');
    
    return {
        type: chartType,
        options,
        isEnhanced: false
    };
}

/**
 * Generates a line chart configuration
 * 
 * @param {string[]} labels - X-axis labels
 * @param {number[]} values - Y-axis values
 * @param {import('../types/chart.types.js').DataAnalysis} analysis - Data analysis
 * @returns {import('../types/chart.types.js').EChartsOption}
 */
function generateLineChart(labels, values, analysis) {
    return {
        title: {
            text: `${analysis.yAxisColumn.name} by ${analysis.xAxisColumn.name}`,
            left: 'center',
            textStyle: {
                fontSize: 16,
                fontWeight: 'normal'
            }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'line'
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: labels,
            boundaryGap: false,
            axisLabel: {
                rotate: labels.length > 10 ? 45 : 0,
                interval: labels.length > 20 ? Math.floor(labels.length / 20) : 0
            }
        },
        yAxis: {
            type: 'value',
            name: analysis.yAxisColumn.name,
            nameLocation: 'middle',
            nameGap: 50
        },
        series: [{
            name: analysis.yAxisColumn.name,
            type: 'line',
            data: values,
            smooth: true,
            itemStyle: {
                color: '#5470c6'
            },
            lineStyle: {
                width: 2
            },
            symbol: 'circle',
            symbolSize: 6
        }]
    };
}

/**
 * Generates a bar chart configuration
 * 
 * @param {string[]} labels - X-axis labels
 * @param {number[]} values - Y-axis values
 * @param {import('../types/chart.types.js').DataAnalysis} analysis - Data analysis
 * @returns {import('../types/chart.types.js').EChartsOption}
 */
function generateBarChart(labels, values, analysis) {
    return {
        title: {
            text: `${analysis.yAxisColumn.name} by ${analysis.xAxisColumn.name}`,
            left: 'center',
            textStyle: {
                fontSize: 16,
                fontWeight: 'normal'
            }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow'
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: labels,
            axisLabel: {
                rotate: labels.length > 10 ? 45 : 0,
                interval: labels.length > 20 ? Math.floor(labels.length / 20) : 0
            }
        },
        yAxis: {
            type: 'value',
            name: analysis.yAxisColumn.name,
            nameLocation: 'middle',
            nameGap: 50
        },
        series: [{
            name: analysis.yAxisColumn.name,
            type: 'bar',
            data: values,
            itemStyle: {
                color: '#5470c6'
            },
            barMaxWidth: 50
        }]
    };
}

/**
 * Generates a pie chart configuration
 * 
 * @param {string[]} labels - Category labels
 * @param {number[]} values - Values for each category
 * @param {import('../types/chart.types.js').DataAnalysis} analysis - Data analysis
 * @returns {import('../types/chart.types.js').EChartsOption}
 */
function generatePieChart(labels, values, analysis) {
    // Transform data into pie chart format
    const pieData = labels.map((label, index) => ({
        name: label,
        value: values[index]
    }));
    
    return {
        title: {
            text: `${analysis.yAxisColumn.name} by ${analysis.xAxisColumn.name}`,
            left: 'center',
            textStyle: {
                fontSize: 16,
                fontWeight: 'normal'
            }
        },
        tooltip: {
            trigger: 'item',
            formatter: '{b}: {c} ({d}%)'
        },
        legend: {
            orient: 'vertical',
            left: 'left',
            data: labels,
            type: 'scroll',
            pageButtonItemGap: 5,
            pageIconSize: 10
        },
        series: [{
            name: analysis.yAxisColumn.name,
            type: 'pie',
            radius: '55%',
            center: ['50%', '55%'],
            data: pieData,
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowOffsetX: 0,
                    shadowColor: 'rgba(0, 0, 0, 0.5)'
                }
            },
            label: {
                formatter: '{b}: {d}%'
            }
        }]
    };
}
