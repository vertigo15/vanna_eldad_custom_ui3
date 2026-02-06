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
     * Display insights prompt in the Insights Prompt tab
     */
    displayInsightsPrompt(insights) {
        const promptContent = document.getElementById('insights-prompt-content');
        if (!promptContent) {
            console.warn('[InsightsManager] Insights prompt content element not found');
            return;
        }
        
        let html = '<div class="insights-prompt-view">';
        
        // System message
        if (insights.system_message) {
            html += `
                <div class="prompt-section">
                    <h4>System Message</h4>
                    <pre class="prompt-text">${this.escapeHtml(insights.system_message)}</pre>
                </div>
            `;
        }
        
        // User prompt
        if (insights.prompt) {
            html += `
                <div class="prompt-section">
                    <h4>Insights Generation Prompt</h4>
                    <pre class="prompt-text">${this.escapeHtml(insights.prompt)}</pre>
                </div>
            `;
        }
        
        html += '</div>';
        promptContent.innerHTML = html;
        
        console.log('[InsightsManager] Insights prompt displayed in tab');
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
