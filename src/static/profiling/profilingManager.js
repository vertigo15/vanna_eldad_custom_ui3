/**
 * Data Profiling Manager
 * Handles lazy loading and caching of ydata-profiling reports
 */

class ProfilingManager {
    constructor() {
        this.cachedReport = null;
        this.currentQueryId = null;
        this.isExpanded = false;
        this.isGenerating = false;
    }

    /**
     * Initialize profiling section after query results are displayed
     * @param {Object} results - Query results with rows and columns
     */
    initialize(results) {
        const section = document.getElementById('profiling-section');
        if (!section) return;

        // Generate unique ID for this query
        const queryId = this.generateQueryId(results);

        // Clear cache if this is a new query
        if (this.currentQueryId !== queryId) {
            this.cachedReport = null;
            this.currentQueryId = queryId;
            this.isExpanded = false;
        }

        // Show the section
        section.style.display = 'block';

        // Reset to collapsed state
        this.collapse();
    }

    /**
     * Generate unique ID for query results to detect cache invalidation
     * @param {Object} results - Query results
     * @returns {string} Unique query ID
     */
    generateQueryId(results) {
        const str = JSON.stringify({
            columns: results.columns,
            rowCount: results.rows?.length || 0,
            firstRow: results.rows?.[0] || null
        });
        return this.hashCode(str);
    }

    /**
     * Simple hash function for string
     * @param {string} str - String to hash
     * @returns {number} Hash code
     */
    hashCode(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        return hash;
    }

    /**
     * Toggle profiling section (expand/collapse)
     */
    toggle() {
        if (this.isExpanded) {
            this.collapse();
        } else {
            this.expand();
        }
    }

    /**
     * Expand profiling section and generate report if needed
     */
    async expand() {
        this.isExpanded = true;

        const header = document.getElementById('profiling-header');
        const content = document.getElementById('profiling-content');
        const arrow = document.getElementById('profiling-arrow');

        if (arrow) arrow.textContent = '▼';
        if (content) content.style.display = 'block';

        // If report is cached, display it
        if (this.cachedReport) {
            this.displayReport(this.cachedReport);
            return;
        }

        // Otherwise, show generate button
        this.showGenerateButton();
    }

    /**
     * Collapse profiling section
     */
    collapse() {
        this.isExpanded = false;

        const content = document.getElementById('profiling-content');
        const arrow = document.getElementById('profiling-arrow');

        if (arrow) arrow.textContent = '▶';
        if (content) content.style.display = 'none';
    }

    /**
     * Show generate button in content area
     */
    showGenerateButton() {
        const content = document.getElementById('profiling-content');
        if (!content) return;

        content.innerHTML = `
            <div class="profiling-prompt">
                <p>📊 Generate a comprehensive data profile report including:</p>
                <ul>
                    <li>Dataset statistics and variable types</li>
                    <li>Distribution histograms for each column</li>
                    <li>Correlation matrix and heatmap</li>
                    <li>Missing values analysis</li>
                    <li>Common values and outliers</li>
                </ul>
                <button class="profile-generate-btn" onclick="profilingManager.generateReport()">
                    🔍 Generate Profile Report
                </button>
            </div>
        `;
    }

    /**
     * Generate profile report by calling backend API
     */
    async generateReport() {
        if (this.isGenerating) return;

        this.isGenerating = true;
        const content = document.getElementById('profiling-content');
        if (!content) return;

        try {
            // Show loading state
            content.innerHTML = `
                <div class="profiling-loading">
                    <div class="spinner"></div>
                    <p>Generating profile report... This may take a moment.</p>
                </div>
            `;

            // Get current results from global state
            const results = window.currentResults;
            if (!results || !results.rows || !results.columns) {
                throw new Error('No results available to profile');
            }

            // Prepare dataset
            const dataset = {
                rows: results.rows,
                columns: results.columns
            };

            // Call API
            const response = await fetch('/api/generate-profile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ dataset })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to generate profile report');
            }

            const data = await response.json();
            const htmlReport = data.html;

            // Cache the report
            this.cachedReport = htmlReport;

            // Display the report
            this.displayReport(htmlReport);

        } catch (error) {
            console.error('Profile generation error:', error);
            content.innerHTML = `
                <div class="profiling-error">
                    <p>❌ Failed to generate profile report</p>
                    <p class="error-detail">${error.message}</p>
                    <button class="profile-retry-btn" onclick="profilingManager.generateReport()">
                        🔄 Retry
                    </button>
                </div>
            `;
        } finally {
            this.isGenerating = false;
        }
    }

    /**
     * Display profile report in iframe
     * @param {string} htmlReport - HTML content of the report
     */
    displayReport(htmlReport) {
        const content = document.getElementById('profiling-content');
        if (!content) return;

        content.innerHTML = `
            <div class="profiling-report">
                <div class="profiling-actions">
                    <button class="profile-download-btn" onclick="profilingManager.downloadReport()">
                        📥 Download Full Report
                    </button>
                </div>
                <iframe 
                    id="profile-iframe"
                    class="profile-iframe"
                    srcdoc="${this.escapeHtml(htmlReport)}"
                    sandbox="allow-scripts allow-same-origin"
                ></iframe>
            </div>
        `;
    }

    /**
     * Download cached report as HTML file
     */
    downloadReport() {
        if (!this.cachedReport) return;

        const blob = new Blob([this.cachedReport], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `data_profile_report_${Date.now()}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /**
     * Escape HTML for safe insertion into srcdoc
     * @param {string} html - HTML string
     * @returns {string} Escaped HTML
     */
    escapeHtml(html) {
        return html
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /**
     * Hide profiling section (when no results)
     */
    hide() {
        const section = document.getElementById('profiling-section');
        if (section) {
            section.style.display = 'none';
        }
    }

    /**
     * Reset manager state
     */
    reset() {
        this.cachedReport = null;
        this.currentQueryId = null;
        this.isExpanded = false;
        this.isGenerating = false;
        this.hide();
    }
}

// Global instance
const profilingManager = new ProfilingManager();
