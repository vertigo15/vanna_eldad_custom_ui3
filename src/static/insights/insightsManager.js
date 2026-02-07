/**
 * Insights Manager
 * Handles fetching and displaying insights for query results
 */

class InsightsManager {
    constructor() {
        this.state = {
            currentInsights: null,
            isLoading: false
        };
    }

    /**
     * Generate and display insights for query results
     * @param {Object} results - Query results with rows and columns
     * @param {string} question - Original user question
     * @param {string} queryId - Query ID for linking to history (optional)
     */
    async generateInsights(results, question, queryId = null) {
        console.log('[InsightsManager] Generating insights');
        
        const container = document.getElementById('insights-container');
        if (!container) {
            console.error('[InsightsManager] Insights container not found');
            return;
        }

        // Show loading state
        this.showLoading(container);
        this.state.isLoading = true;

        try {
            // Call insights API
            const requestBody = {
                dataset: results,
                question: question
            };
            
            // Add query_id if provided (for history logging)
            if (queryId) {
                requestBody.query_id = queryId;
                console.log('[InsightsManager] Including query_id for history:', queryId);
            }
            
            const response = await fetch('/api/generate-insights', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody),
                signal: AbortSignal.timeout(30000)
            });

            if (!response.ok) {
                throw new Error(`API returned ${response.status}: ${response.statusText}`);
            }

            const insights = await response.json();
            
            if (insights.error) {
                throw new Error(insights.error);
            }

            console.log('[InsightsManager] Insights received:', insights);
            
            this.state.currentInsights = insights;
            this.state.isLoading = false;

            // Display insights
            this.displayInsights(container, insights);
            
            // Display prompt in Insights Prompt tab if available
            if (insights.prompt) {
                this.displayInsightsPrompt(insights);
            }

        } catch (error) {
            console.error('[InsightsManager] Failed to generate insights:', error);
            this.state.isLoading = false;
            this.showError(container, error.message);
        }
    }

    /**
     * Display insights in the container
     */
    displayInsights(container, insights) {
        // Check if insights are empty
        if (!insights.findings || insights.findings.length === 0) {
            container.innerHTML = `
                <div class="insights-section">
                    <div class="insights-header">
                        <h3>💡 Insights</h3>
                    </div>
                    <div class="insights-empty">
                        <p>${insights.summary || 'No significant insights found for this dataset'}</p>
                    </div>
                </div>
            `;
            return;
        }

        // Build HTML for insights
        let html = `
            <div class="insights-section">
                <div class="insights-header">
                    <h3>💡 Insights</h3>
                </div>
                
                <div class="insights-content">
        `;

        // Summary
        if (insights.summary) {
            html += `
                <div class="insights-summary">
                    <strong>Summary:</strong> ${this.escapeHtml(insights.summary)}
                </div>
            `;
        }

        // Key Findings
        if (insights.findings && insights.findings.length > 0) {
            html += `<div class="insights-findings">
                <strong>Key Findings:</strong>
                <ul>`;
            
            insights.findings.forEach(finding => {
                html += `<li>${this.escapeHtml(finding)}</li>`;
            });
            
            html += `</ul></div>`;
        }

        // Suggestions
        if (insights.suggestions && insights.suggestions.length > 0) {
            html += `<div class="insights-suggestions">
                <strong>Suggestions:</strong>
                <ul>`;
            
            insights.suggestions.forEach(suggestion => {
                html += `<li>${this.escapeHtml(suggestion)}</li>`;
            });
            
            html += `</ul></div>`;
        }

        html += `</div></div>`;

        container.innerHTML = html;
    }

    /**
     * Show loading state
     */
    showLoading(container) {
        container.innerHTML = `
            <div class="insights-section">
                <div class="insights-header">
                    <h3>💡 Insights</h3>
                </div>
                <div class="insights-loading">
                    <div class="spinner"></div>
                    <p>Analyzing data...</p>
                </div>
            </div>
        `;
    }

    /**
     * Show error state
     */
    showError(container, message) {
        container.innerHTML = `
            <div class="insights-section">
                <div class="insights-header">
                    <h3>💡 Insights</h3>
                </div>
                <div class="insights-error">
                    <p>⚠️ ${this.escapeHtml(message)}</p>
                </div>
            </div>
        `;
    }

    /**
     * Display insights prompt in the Insights Prompt tab with collapsible sections
     */
    displayInsightsPrompt(insights) {
        const promptContent = document.getElementById('insights-prompt-content');
        if (!promptContent) {
            console.warn('[InsightsManager] Insights prompt content element not found');
            return;
        }
        
        if (!insights.prompt) {
            promptContent.innerHTML = '<p style="color: #999;">No prompt available</p>';
            return;
        }
        
        // Parse the prompt into sections
        const sections = this.parseInsightsPrompt(insights.prompt);
        
        let html = '<div class="structured-prompt">';
        
        // Section 1: Main Instructions (Rules and Thresholds)
        if (sections.mainInstructions) {
            html += this.createPromptSection('insights-main', 'Instructions & Rules', 
                `<pre class="prompt-text">${this.escapeHtml(sections.mainInstructions)}</pre>`, true);
        }
        
        // Section 2: Dataset Summary
        if (sections.datasetSummary) {
            html += this.createPromptSection('insights-dataset', 'Dataset Summary', 
                `<pre class="prompt-text">${this.escapeHtml(sections.datasetSummary)}</pre>`, false);
        }
        
        // Section 3: Column Statistics
        if (sections.columnStats) {
            html += this.createPromptSection('insights-stats', 'Column Statistics', 
                `<pre class="prompt-text">${this.escapeHtml(sections.columnStats)}</pre>`, false);
        }
        
        // Section 4: Output Format
        if (sections.outputFormat) {
            html += this.createPromptSection('insights-format', 'Output Format', 
                `<pre class="prompt-text">${this.escapeHtml(sections.outputFormat)}</pre>`, false);
        }
        
        // Section 5: Full Prompt
        html += this.createPromptSection('insights-full', 'Full Prompt Text', 
            `<pre class="prompt-text">${this.escapeHtml(insights.prompt)}</pre>`, false);
        
        html += '</div>';
        promptContent.innerHTML = html;
        
        console.log('[InsightsManager] Insights prompt displayed in structured format');
    }
    
    /**
     * Parse insights prompt into sections
     */
    parseInsightsPrompt(prompt) {
        const sections = {
            mainInstructions: '',
            datasetSummary: '',
            columnStats: '',
            outputFormat: ''
        };
        
        // Split by section headers
        const datasetSummaryIndex = prompt.indexOf('## DATASET SUMMARY:');
        const columnStatsIndex = prompt.indexOf('## COLUMN STATISTICS:');
        const outputFormatIndex = prompt.indexOf('## OUTPUT FORMAT');
        
        // Extract main instructions (everything before DATASET SUMMARY)
        if (datasetSummaryIndex !== -1) {
            sections.mainInstructions = prompt.substring(0, datasetSummaryIndex).trim();
        } else {
            // Fallback: if no sections found, put everything in main instructions
            sections.mainInstructions = prompt;
            return sections;
        }
        
        // Extract dataset summary (between DATASET SUMMARY and COLUMN STATISTICS)
        if (datasetSummaryIndex !== -1 && columnStatsIndex !== -1) {
            sections.datasetSummary = prompt.substring(datasetSummaryIndex + 19, columnStatsIndex).trim();
        } else if (datasetSummaryIndex !== -1) {
            sections.datasetSummary = prompt.substring(datasetSummaryIndex + 19).trim();
        }
        
        // Extract column statistics (between COLUMN STATISTICS and OUTPUT FORMAT)
        if (columnStatsIndex !== -1 && outputFormatIndex !== -1) {
            sections.columnStats = prompt.substring(columnStatsIndex + 22, outputFormatIndex).trim();
        } else if (columnStatsIndex !== -1) {
            sections.columnStats = prompt.substring(columnStatsIndex + 22).trim();
        }
        
        // Extract output format (from OUTPUT FORMAT to end)
        if (outputFormatIndex !== -1) {
            sections.outputFormat = prompt.substring(outputFormatIndex + 16).trim();
        }
        
        return sections;
    }
    
    /**
     * Create a collapsible prompt section
     */
    createPromptSection(id, title, content, expanded = false) {
        const expandedClass = expanded ? 'expanded' : '';
        const displayStyle = expanded ? 'block' : 'none';
        const arrow = expanded ? '▼' : '▶';
        
        return `
            <div class="prompt-section ${expandedClass}">
                <div class="prompt-section-header" onclick="toggleInsightsPromptSection('${id}')">
                    <span class="section-arrow" id="arrow-${id}">${arrow}</span>
                    <span class="section-title">${title}</span>
                </div>
                <div class="prompt-section-content" id="content-${id}" style="display: ${displayStyle};">
                    ${content}
                </div>
            </div>
        `;
    }
    
    /**
     * Toggle a prompt section
     */
    togglePromptSection(sectionId) {
        const content = document.getElementById(`content-${sectionId}`);
        const arrow = document.getElementById(`arrow-${sectionId}`);
        
        if (content && arrow) {
            if (content.style.display === 'none') {
                content.style.display = 'block';
                arrow.textContent = '▼';
            } else {
                content.style.display = 'none';
                arrow.textContent = '▶';
            }
        }
    }
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for use in script.js
window.InsightsManager = InsightsManager;

// Expose toggle function globally for onclick handlers
window.toggleInsightsPromptSection = function(sectionId) {
    const content = document.getElementById(`content-${sectionId}`);
    const arrow = document.getElementById(`arrow-${sectionId}`);
    
    if (content && arrow) {
        if (content.style.display === 'none') {
            content.style.display = 'block';
            arrow.textContent = '▼';
        } else {
            content.style.display = 'none';
            arrow.textContent = '▶';
        }
    }
};
