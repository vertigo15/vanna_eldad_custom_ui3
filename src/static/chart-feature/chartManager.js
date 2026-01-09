/**
 * Chart Manager
 * Main orchestrator for chart feature
 * 
 * @module chartManager
 */

/// <reference path="./types/chart.types.js" />

import { analyzeData } from './utils/dataAnalyzer.js';
import { ChartContainer } from './components/ChartContainer.js';
import { ChartToggle } from './components/ChartToggle.js';
import { ChartTypeSelector } from './components/ChartTypeSelector.js';

/**
 * Main chart manager class
 */
export class ChartManager {
    constructor() {
        /** @type {import('./types/chart.types.js').ChartState} */
        this.state = {
            currentView: 'table',
            currentChartType: 'bar',
            currentConfig: null,
            chartInstance: null,
            isEChartsLoaded: false,
            currentData: null
        };
        
        this.dataAnalysis = null;
        this.chartContainer = null;
        this.chartToggle = null;
        this.chartTypeSelector = null;
        this.llmRecommendedType = null;
        
        console.log('[ChartManager] Initialized');
    }
    
    /**
     * Initializes chart feature for given query results
     * 
     * @param {import('./types/chart.types.js').QueryResults} results - Query results
     */
    async initialize(results) {
        console.log('[ChartManager] Initializing with results');
        
        this.state.currentData = results;
        
        // Analyze data (for type detection only)
        this.dataAnalysis = analyzeData(results);
        console.log('[ChartManager] Data analysis complete:', this.dataAnalysis);
        
        // Initialize UI components
        this.initializeComponents();
        
        // Check if data can be charted
        if (!this.dataAnalysis.canChart) {
            console.log('[ChartManager] Data cannot be charted:', this.dataAnalysis.reason);
            this.chartToggle.disableChartButton();
            this.showNotChartableMessage(this.dataAnalysis.reason);
            return;
        }
        
        // Always default to table view (no auto-switch to chart)
        console.log('[ChartManager] Initialization complete - defaulting to table view');
    }
    
    /**
     * Initializes UI components
     */
    initializeComponents() {
        // Chart toggle
        this.chartToggle = new ChartToggle('chart-toggle-container', (viewMode) => {
            this.handleViewChange(viewMode);
        });
        this.chartToggle.render();
        
        // Chart type selector
        this.chartTypeSelector = new ChartTypeSelector('chart-type-selector-container', (chartType) => {
            this.handleChartTypeChange(chartType);
        });
        this.chartTypeSelector.render();
        
        // Chart container
        this.chartContainer = new ChartContainer('chart-display-container');
        
        console.log('[ChartManager] Components initialized');
    }
    
    /**
     * Handles view mode change (table/chart)
     * 
     * @param {import('./types/chart.types.js').ViewMode} viewMode - New view mode
     */
    async handleViewChange(viewMode) {
        console.log('[ChartManager] View changed to:', viewMode);
        
        this.state.currentView = viewMode;
        this.saveViewPreference(viewMode);
        
        const tableContainer = document.getElementById('results-display');
        const chartViewContainer = document.getElementById('chart-view-container');
        
        if (viewMode === 'table') {
            // Show table, hide chart
            if (tableContainer) tableContainer.style.display = 'block';
            if (chartViewContainer) chartViewContainer.style.display = 'none';
            
            // Hide chart type selector
            const selectorContainer = document.getElementById('chart-type-selector-container');
            if (selectorContainer) selectorContainer.style.display = 'none';
        } else {
            // Show chart, hide table
            if (tableContainer) tableContainer.style.display = 'none';
            if (chartViewContainer) chartViewContainer.style.display = 'flex';
            
            // Show chart type selector
            const selectorContainer = document.getElementById('chart-type-selector-container');
            if (selectorContainer) selectorContainer.style.display = 'block';
            
            // Load ECharts if not loaded
            if (!this.state.isEChartsLoaded) {
                await this.loadECharts();
            }
            
            // Get selected chart type
            const selectedType = this.chartTypeSelector.getSelectedType();
            
            // Call LLM to generate chart
            this.generateChartWithLLM(selectedType);
        }
    }
    
    /**
     * Handles chart type selection change
     * 
     * @param {string} chartType - Selected chart type
     */
    async handleChartTypeChange(chartType) {
        console.log('[ChartManager] Chart type changed to:', chartType);
        
        // Regenerate chart with new type
        await this.generateChartWithLLM(chartType);
    }
    
    /**
     * Generates chart using LLM
     * 
     * @param {string} chartType - Chart type ("auto" for LLM choice, or specific type)
     */
    async generateChartWithLLM(chartType = 'auto') {
        console.log('[ChartManager] Generating chart with LLM, type:', chartType);
        
        // Show loading state
        this.chartContainer.showLoading();
        
        try {
            // Prepare data for LLM
            const columns = this.dataAnalysis.columns.map(col => ({
                name: col.name,
                type: col.type
            }));
            
            // Get sample data (first 10 rows) - convert to array format
            const rows = this.state.currentData.data || this.state.currentData.rows || [];
            const sampleData = rows.slice(0, 10).map(row => {
                if (Array.isArray(row)) {
                    return row;
                } else {
                    // Convert object to array using column order
                    return this.state.currentData.columns.map(col => row[col]);
                }
            });
            
            // Convert all_data to array format too
            const allData = rows.length <= 100 ? rows.map(row => {
                if (Array.isArray(row)) {
                    return row;
                } else {
                    return this.state.currentData.columns.map(col => row[col]);
                }
            }) : sampleData;
            
            // Check cache first (include chart type in cache key)
            const cacheKey = this.getLLMCacheKey(chartType);
            const cached = sessionStorage.getItem(cacheKey);
            if (cached) {
                console.log('[ChartManager] Using cached LLM response for type:', chartType);
                const config = JSON.parse(cached);
                await this.renderChart(config);
                return;
            }
            
            console.log('[ChartManager] Calling LLM API for type:', chartType);
            
            // Call LLM API
            const response = await fetch('/api/generate-chart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    columns: columns,
                    column_names: this.state.currentData.columns,
                    sample_data: sampleData,
                    all_data: allData,
                    chart_type: chartType // Include chart type parameter
                }),
                signal: AbortSignal.timeout(30000)
            });
            
            if (!response.ok) {
                throw new Error(`API returned ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            if (!data.chart_config) {
                throw new Error('No chart configuration returned from API');
            }
            
            console.log('[ChartManager] LLM response received');
            console.log('[ChartManager] Chart type:', data.chart_type);
            
            // Store LLM recommendation (when chart_type is auto)
            if (chartType === 'auto' && data.chart_type) {
                this.llmRecommendedType = data.chart_type;
                this.chartTypeSelector.setRecommendation(data.chart_type);
                console.log('[ChartManager] LLM recommended type:', data.chart_type);
            }
            
            // Cache the response
            sessionStorage.setItem(cacheKey, JSON.stringify(data.chart_config));
            
            // Render the chart
            await this.renderChart(data.chart_config);
            
        } catch (error) {
            console.error('[ChartManager] Failed to generate chart with LLM:', error);
            this.chartContainer.showError(
                'Failed to generate chart: ' + error.message + 
                '<br><br>The backend /api/generate-chart endpoint needs to be implemented. See CHART_BACKEND_TODO.md for details.'
            );
        }
    }
    
    /**
     * Renders chart with given config
     */
    async renderChart(echartsConfig) {
        console.log('[ChartManager] Rendering chart with LLM config');
        
        const chartConfig = {
            type: echartsConfig.series?.[0]?.type || 'bar',
            options: echartsConfig,
            isEnhanced: true
        };
        
        this.state.currentConfig = chartConfig;
        
        try {
            // Only initialize if not already initialized
            if (!this.chartContainer.chartInstance) {
                await this.chartContainer.init();
            }
            this.chartContainer.render(chartConfig);
            console.log('[ChartManager] Chart rendered successfully');
        } catch (error) {
            console.error('[ChartManager] Failed to render chart:', error);
            this.chartContainer.showError('Failed to render chart: ' + error.message);
        }
    }
    
    
    /**
     * Loads ECharts library
     */
    async loadECharts() {
        if (this.state.isEChartsLoaded) return;
        
        console.log('[ChartManager] Loading ECharts library');
        
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js';
            script.async = true;
            script.onload = () => {
                this.state.isEChartsLoaded = true;
                console.log('[ChartManager] ECharts loaded successfully');
                resolve();
            };
            script.onerror = () => {
                console.error('[ChartManager] Failed to load ECharts');
                reject(new Error('Failed to load ECharts library'));
            };
            document.head.appendChild(script);
        });
    }
    
    /**
     * Shows a message when data can't be charted
     * 
     * @param {string} reason - Reason why data can't be charted
     */
    showNotChartableMessage(reason) {
        const container = document.getElementById('chart-display-container');
        if (container) {
            container.innerHTML = `
                <div class="chart-not-available">
                    <p>📊 Chart view not available</p>
                    <p class="reason">${reason}</p>
                </div>
            `;
        }
    }
    
    /**
     * Shows a toast message
     * 
     * @param {string} message - Toast message
     * @param {string} type - Toast type (success/error/info)
     */
    showToast(message, type = 'info') {
        // Simple toast implementation
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    // Cache and preferences methods
    
    loadViewPreference() {
        return localStorage.getItem('chartViewPreference') || 'table';
    }
    
    saveViewPreference(viewMode) {
        localStorage.setItem('chartViewPreference', viewMode);
    }
    
    saveChartTypePreference(chartType) {
        localStorage.setItem('chartTypePreference', chartType);
    }
    
    loadCachedConfig(chartType) {
        const cacheKey = this.getCacheKey(chartType);
        const cached = sessionStorage.getItem(cacheKey);
        if (cached) {
            console.log('[ChartManager] Cache hit for', chartType);
            try {
                const parsed = JSON.parse(cached);
                return parsed;
            } catch (e) {
                console.error('[ChartManager] Failed to parse cached config');
                return null;
            }
        }
        console.log('[ChartManager] Cache miss for', chartType);
        return null;
    }
    
    cacheEnhancedConfig(chartType, config) {
        const cacheKey = this.getCacheKey(chartType);
        sessionStorage.setItem(cacheKey, JSON.stringify(config));
        console.log('[ChartManager] Cached config for', chartType);
    }
    
    getCacheKey(chartType) {
        // Use SQL as part of cache key (hash it for shorter key)
        const sqlHash = this.simpleHash(window.currentSql || JSON.stringify(this.state.currentData));
        return `chart_${sqlHash}_${chartType}`;
    }
    
    getLLMCacheKey(chartType = 'auto') {
        // Cache key for LLM-generated charts (include chart type)
        // Use stringified data as cache key since we don't have access to SQL here
        const dataHash = this.simpleHash(JSON.stringify(this.state.currentData));
        return `chart_llm_${dataHash}_${chartType}`;
    }
    
    simpleHash(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(36);
    }
    
    /**
     * Cleanup method
     */
    dispose() {
        if (this.chartContainer) {
            this.chartContainer.dispose();
        }
        console.log('[ChartManager] Disposed');
    }
}
