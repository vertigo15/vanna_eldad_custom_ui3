// Import chart manager
import { ChartManager } from './chart-feature/chartManager.js';

// Global state
let currentQuestion = '';
let currentSql = '';
let currentPrompt = '';
let currentResults = null;
let currentQueryId = null;  // For conversation history tracking
let currentSessionId = null;  // For conversation continuity
let allTables = [];
let promptExpanded = false;
let sqlExpanded = false;
let sortColumn = null;
let sortDirection = 'asc';
let filterText = '';
let chartManager = null;
let insightsManager = null;

// Ask question
async function askQuestion() {
    const questionInput = document.getElementById('question-input');
    const question = questionInput.value.trim();
    
    if (!question) {
        showError('Please enter a question');
        return;
    }
    
    // Save to history
    saveToHistory(question);
    
    // Show loading state
    hideError();
    hideResults();
    showLoading();
    
    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question }),
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to process question');
        }
        
        hideLoading();
        displayResults(data);
        
    } catch (error) {
        hideLoading();
        showError(`Error: ${error.message}`);
        console.error('Error:', error);
    }
}

// Display results
function displayResults(data) {
    // Reset toggle states
    sqlExpanded = false;
    promptExpanded = false;
    
    // Store current question and IDs for history tracking
    currentQuestion = data.question;
    currentQueryId = data.query_id || null;
    currentSessionId = data.session_id || null;
    
    // Log conversation IDs
    if (currentQueryId) {
        console.log('[History] Query ID:', currentQueryId);
    }
    if (currentSessionId) {
        console.log('[History] Session ID:', currentSessionId);
    }
    
    // Show results section
    const resultsSection = document.getElementById('results-section');
    resultsSection.style.display = 'flex';
    
    // Display question
    document.getElementById('question-display').textContent = data.question;
    
    // Display SQL
    if (data.sql) {
        currentSql = data.sql;
        document.getElementById('sql-display').textContent = data.sql;
    } else {
        document.getElementById('sql-display').textContent = 'No SQL generated';
    }
    
    // Display explanation
    const explanationCard = document.getElementById('explanation-card');
    if (data.explanation) {
        document.getElementById('explanation-display').textContent = data.explanation;
        explanationCard.style.display = 'block';
    } else {
        explanationCard.style.display = 'none';
    }
    
    // Display results
    const resultsDisplay = document.getElementById('results-display');
    const exportBtn = document.getElementById('export-btn');
    const copyResultsBtn = document.getElementById('copy-results-btn');
    
    const describeBtn = document.getElementById('describe-btn');
    
    if (data.error) {
        resultsDisplay.innerHTML = `<div class="error-message">${data.error}</div>`;
        exportBtn.style.display = 'none';
        copyResultsBtn.style.display = 'none';
        describeBtn.style.display = 'none';
        currentResults = null;
        window.currentResults = null;
        if (typeof profilingManager !== 'undefined') {
            profilingManager.hide();
        }
    } else if (data.results && data.results.columns && (data.results.data || data.results.rows)) {
        currentResults = data.results;
        resultsDisplay.innerHTML = formatResultsAsTable(data.results);
        exportBtn.style.display = 'inline-block';
        copyResultsBtn.style.display = 'inline-block';
        describeBtn.style.display = 'inline-block';
        
        // Store results globally for profiling manager
        window.currentResults = data.results;
        
        // Initialize chart feature
        initializeChartFeature(data.results);
        
        // Generate insights in parallel (non-blocking) with query_id
        generateInsights(data.results, currentQuestion, currentQueryId);
        
        // Initialize profiling section (collapsed by default)
        if (typeof profilingManager !== 'undefined') {
            profilingManager.initialize(data.results);
        }
    } else {
        resultsDisplay.innerHTML = '<div class="no-results">No results to display</div>';
        exportBtn.style.display = 'none';
        copyResultsBtn.style.display = 'none';
        describeBtn.style.display = 'none';
        currentResults = null;
        window.currentResults = null;
        if (typeof profilingManager !== 'undefined') {
            profilingManager.hide();
        }
    }
    
    // Handle prompt if available - always show if SQL was generated
    console.log('Prompt data:', data.prompt ? 'Available' : 'Not available');
    console.log('Prompt length:', data.prompt ? data.prompt.length : 0);
    const promptSection = document.getElementById('prompt-section');
    if (data.sql) {
        // If we have SQL, we should have a prompt - show the section
        currentPrompt = data.prompt || 'Prompt not available';
        promptSection.style.display = 'block';
        console.log('Showing prompt section (SQL was generated)');
    } else {
        promptSection.style.display = 'none';
        currentPrompt = '';
        console.log('Hiding prompt section - no SQL generated');
    }
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Format results as HTML table with sorting and filtering
function formatResultsAsTable(results) {
    // Handle both 'data' and 'rows' field names
    let rows = results.data || results.rows;
    if (!rows || rows.length === 0) {
        return '<div class="no-results">No data found</div>';
    }
    
    // Reset sort/filter on new results
    sortColumn = null;
    sortDirection = 'asc';
    filterText = '';
    
    // Add filter input
    let html = '<div class="table-controls">';
    html += '<input type="text" id="result-filter" class="result-filter-input" placeholder="Filter results..." onkeyup="filterResults()" />';
    html += '</div>';
    
    html += '<div id="table-container">';
    html += renderTable(results, rows);
    html += '</div>';
    
    return html;
}

// Render the actual table
function renderTable(results, rows) {
    let html = '<table id="results-table"><thead><tr>';
    
    // Table headers with sort buttons
    results.columns.forEach((column, index) => {
        const sortIcon = sortColumn === index ? (sortDirection === 'asc' ? ' ▲' : ' ▼') : '';
        html += `<th onclick="sortTable(${index})" style="cursor: pointer;" title="Click to sort">${escapeHtml(column)}${sortIcon}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    // Table rows
    rows.forEach(row => {
        html += '<tr class="data-row">';
        // Handle both array format [val1, val2, ...] and object format {col1: val1, col2: val2, ...}
        if (Array.isArray(row)) {
            row.forEach(cell => {
                const value = cell === null ? '<em>NULL</em>' : escapeHtml(String(cell));
                html += `<td>${value}</td>`;
            });
        } else {
            // Row is an object, extract values in column order
            results.columns.forEach(column => {
                const cell = row[column];
                const value = cell === null || cell === undefined ? '<em>NULL</em>' : escapeHtml(String(cell));
                html += `<td>${value}</td>`;
            });
        }
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    
    // Add row count
    html += `<p style="margin-top: 15px; color: #666; font-size: 0.9rem;" id="row-count">
        ${rows.length} row${rows.length !== 1 ? 's' : ''} returned
    </p>`;
    
    return html;
}

// Sort table by column
function sortTable(columnIndex) {
    if (!currentResults) return;
    
    let rows = currentResults.data || currentResults.rows;
    const column = currentResults.columns[columnIndex];
    
    // Toggle sort direction if clicking same column
    if (sortColumn === columnIndex) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortColumn = columnIndex;
        sortDirection = 'asc';
    }
    
    // Sort rows
    rows.sort((a, b) => {
        let valA, valB;
        
        if (Array.isArray(a)) {
            valA = a[columnIndex];
            valB = b[columnIndex];
        } else {
            valA = a[column];
            valB = b[column];
        }
        
        // Handle nulls
        if (valA === null || valA === undefined) return 1;
        if (valB === null || valB === undefined) return -1;
        
        // Try numeric comparison first
        const numA = parseFloat(String(valA).replace(/[^0-9.-]/g, ''));
        const numB = parseFloat(String(valB).replace(/[^0-9.-]/g, ''));
        
        if (!isNaN(numA) && !isNaN(numB)) {
            return sortDirection === 'asc' ? numA - numB : numB - numA;
        }
        
        // String comparison
        const strA = String(valA).toLowerCase();
        const strB = String(valB).toLowerCase();
        
        if (sortDirection === 'asc') {
            return strA < strB ? -1 : strA > strB ? 1 : 0;
        } else {
            return strA > strB ? -1 : strA < strB ? 1 : 0;
        }
    });
    
    // Update display
    document.getElementById('table-container').innerHTML = renderTable(currentResults, rows);
}

// Filter results
function filterResults() {
    if (!currentResults) return;
    
    filterText = document.getElementById('result-filter').value.toLowerCase();
    let rows = currentResults.data || currentResults.rows;
    
    if (!filterText) {
        // No filter, show all
        document.getElementById('table-container').innerHTML = renderTable(currentResults, rows);
        return;
    }
    
    // Filter rows
    const filtered = rows.filter(row => {
        // Check if any cell matches the filter
        if (Array.isArray(row)) {
            return row.some(cell => 
                cell !== null && cell !== undefined && 
                String(cell).toLowerCase().includes(filterText)
            );
        } else {
            return currentResults.columns.some(col => {
                const cell = row[col];
                return cell !== null && cell !== undefined && 
                    String(cell).toLowerCase().includes(filterText);
            });
        }
    });
    
    // Update display
    document.getElementById('table-container').innerHTML = renderTable(currentResults, filtered);
    
    // Update count
    document.getElementById('row-count').textContent = 
        `${filtered.length} of ${rows.length} row${rows.length !== 1 ? 's' : ''}`;
}

// Copy SQL to clipboard
function copySql() {
    if (!currentSql) return;
    
    navigator.clipboard.writeText(currentSql).then(() => {
        const button = document.querySelector('.copy-button');
        const originalText = button.textContent;
        button.textContent = '✓ Copied!';
        button.style.background = '#28a745';
        
        setTimeout(() => {
            button.textContent = originalText;
            button.style.background = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

// Copy Results to clipboard
function copyResults() {
    if (!currentResults) return;
    
    const rows = currentResults.data || currentResults.rows;
    if (!rows || rows.length === 0) return;
    
    // Create tab-separated text (better for pasting into Excel/Sheets)
    let text = '';
    
    // Add headers
    text += currentResults.columns.join('\t') + '\n';
    
    // Add data rows
    rows.forEach(row => {
        if (Array.isArray(row)) {
            text += row.join('\t') + '\n';
        } else {
            text += currentResults.columns.map(col => row[col] || '').join('\t') + '\n';
        }
    });
    
    navigator.clipboard.writeText(text).then(() => {
        const button = document.getElementById('copy-results-btn');
        const originalText = button.textContent;
        button.textContent = '✓ Copied!';
        button.style.background = '#28a745';
        
        setTimeout(() => {
            button.textContent = originalText;
            button.style.background = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

// Toggle SQL display
function toggleSql() {
    const sqlContent = document.getElementById('sql-content');
    const toggleBtn = document.getElementById('toggle-sql-btn');
    
    sqlExpanded = !sqlExpanded;
    
    if (sqlExpanded) {
        sqlContent.style.display = 'block';
        toggleBtn.textContent = '▲ Hide SQL';
    } else {
        sqlContent.style.display = 'none';
        toggleBtn.textContent = '▼ View SQL';
    }
}

// Toggle prompt display
function togglePrompt() {
    const promptContent = document.getElementById('prompt-content');
    const toggleBtn = document.getElementById('toggle-prompt-btn');
    const promptDisplay = document.getElementById('prompt-display');
    
    promptExpanded = !promptExpanded;
    
    if (promptExpanded) {
        promptContent.style.display = 'block';
        toggleBtn.textContent = '▲ Hide Prompt';
        if (currentPrompt) {
            promptDisplay.textContent = currentPrompt;
        } else {
            promptDisplay.textContent = 'No prompt information available';
        }
    } else {
        promptContent.style.display = 'none';
        toggleBtn.textContent = '▼ View Prompt';
    }
}

// Load tables
async function loadTables() {
    const tablesList = document.getElementById('tables-list');
    const searchInput = document.getElementById('table-search');
    tablesList.innerHTML = '<p style="color: #999; font-size: 0.9rem;">Loading...</p>';
    
    try {
        const response = await fetch('/api/tables');
        const data = await response.json();
        
        if (data.tables && data.tables.length > 0) {
            allTables = data.tables;
            searchInput.style.display = 'block';
            displayFilteredTables(allTables);
        } else {
            tablesList.innerHTML = '<p style="color: #999; font-size: 0.9rem;">No tables found</p>';
        }
    } catch (error) {
        tablesList.innerHTML = '<p style="color: #c33; font-size: 0.9rem;">Failed to load tables</p>';
        console.error('Error loading tables:', error);
    }
}

// Filter tables based on search
function filterTables() {
    const searchTerm = document.getElementById('table-search').value.toLowerCase();
    const filtered = allTables.filter(table => table.toLowerCase().includes(searchTerm));
    displayFilteredTables(filtered);
}

// Display filtered tables
function displayFilteredTables(tables) {
    const tablesList = document.getElementById('tables-list');
    if (tables.length > 0) {
        tablesList.innerHTML = tables.map(table => 
            `<div class="table-item" onclick="fillQuestion('Show me data from ${table}')">${escapeHtml(table)}</div>`
        ).join('');
    } else {
        tablesList.innerHTML = '<p style="color: #999; font-size: 0.9rem;">No matching tables</p>';
    }
}

// Export to Excel
function exportToExcel() {
    if (!currentResults) return;
    
    const rows = currentResults.data || currentResults.rows;
    if (!rows || rows.length === 0) return;
    
    // Create CSV content
    let csv = '';
    
    // Add headers
    csv += currentResults.columns.join(',') + '\n';
    
    // Add data rows
    rows.forEach(row => {
        if (Array.isArray(row)) {
            csv += row.map(cell => escapeCSV(cell)).join(',') + '\n';
        } else {
            csv += currentResults.columns.map(col => escapeCSV(row[col])).join(',') + '\n';
        }
    });
    
    // Create download link
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', 'vanna_results_' + new Date().getTime() + '.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Escape CSV values
function escapeCSV(value) {
    if (value === null || value === undefined) return '';
    const str = String(value);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
}

// Fill question input
function fillQuestion(question) {
    document.getElementById('question-input').value = question;
    document.getElementById('question-input').focus();
}

// Show/hide UI elements
function showLoading() {
    document.getElementById('loading').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

function showError(message) {
    const errorEl = document.getElementById('error-message');
    errorEl.textContent = message;
    errorEl.style.display = 'block';
}

function hideError() {
    document.getElementById('error-message').style.display = 'none';
}

function hideResults() {
    document.getElementById('results-section').style.display = 'none';
}

// Utility: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Question History Management
function saveToHistory(question) {
    let history = JSON.parse(localStorage.getItem('questionHistory') || '[]');
    
    // Remove if already exists (to move to top)
    history = history.filter(q => q !== question);
    
    // Add to beginning
    history.unshift(question);
    
    // Keep only last 20
    history = history.slice(0, 20);
    
    localStorage.setItem('questionHistory', JSON.stringify(history));
    displayHistory();
}

function displayHistory() {
    const historyDiv = document.getElementById('question-history');
    const clearBtn = document.getElementById('clear-history-btn');
    const history = JSON.parse(localStorage.getItem('questionHistory') || '[]');
    
    if (history.length === 0) {
        historyDiv.innerHTML = '<p style="color: #999; font-size: 0.9rem; padding: 10px 0;">No recent questions</p>';
        clearBtn.style.display = 'none';
        return;
    }
    
    clearBtn.style.display = 'block';
    historyDiv.innerHTML = history.map((q, index) => 
        `<div class="history-item" onclick="fillQuestion('${escapeHtml(q).replace(/'/g, "\\'")}')"
              title="${escapeHtml(q)}">${escapeHtml(q)}</div>`
    ).join('');
}

function clearHistory() {
    if (confirm('Clear all question history?')) {
        localStorage.removeItem('questionHistory');
        displayHistory();
    }
}

// Chart Feature Initialization
function initializeChartFeature(results) {
    // Dispose previous chart manager if exists
    if (chartManager) {
        chartManager.dispose();
    }
    
    // Create new chart manager
    chartManager = new ChartManager();
    chartManager.initialize(results);
}

// Insights Feature
function generateInsights(results, question, queryId = null) {
    // Initialize insights manager if needed
    if (!insightsManager) {
        insightsManager = new window.InsightsManager();
    }
    
    // Show insights container
    const insightsContainer = document.getElementById('insights-container');
    if (insightsContainer) {
        insightsContainer.style.display = 'block';
    }
    
    // Generate insights asynchronously (non-blocking) with query_id for history
    setTimeout(() => {
        insightsManager.generateInsights(results, question, queryId);
    }, 0);
}

// Describe Feature - Statistical Summary
let describeExpanded = false;

function toggleDescribe() {
    const describeSection = document.getElementById('describe-section');
    const describeBtn = document.getElementById('describe-btn');
    
    if (!currentResults) return;
    
    if (describeExpanded) {
        // Hide describe section
        describeSection.style.display = 'none';
        describeBtn.textContent = '📊 Describe';
        describeExpanded = false;
    } else {
        // Generate and show statistics
        const stats = calculateStatistics(currentResults);
        describeSection.innerHTML = formatStatistics(stats);
        describeSection.style.display = 'block';
        describeBtn.textContent = '📊 Hide Description';
        describeExpanded = true;
    }
}

// Calculate statistics similar to pandas df.describe()
function calculateStatistics(results) {
    const rows = results.data || results.rows;
    const columns = results.columns;
    const stats = {};
    
    columns.forEach((column, colIndex) => {
        const values = [];
        
        // Extract column values
        rows.forEach(row => {
            const value = Array.isArray(row) ? row[colIndex] : row[column];
            if (value !== null && value !== undefined && value !== '') {
                values.push(value);
            }
        });
        
        // Determine if numeric
        const numericValues = values.filter(v => !isNaN(parseFloat(v))).map(v => parseFloat(v));
        const isNumeric = numericValues.length > values.length * 0.5;
        
        if (isNumeric && numericValues.length > 0) {
            // Calculate numeric statistics
            const sorted = numericValues.slice().sort((a, b) => a - b);
            const sum = numericValues.reduce((a, b) => a + b, 0);
            const mean = sum / numericValues.length;
            const median = sorted.length % 2 === 0
                ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
                : sorted[Math.floor(sorted.length / 2)];
            
            // Calculate standard deviation
            const variance = numericValues.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / numericValues.length;
            const std = Math.sqrt(variance);
            
            // Calculate quartiles
            const q1 = sorted[Math.floor(sorted.length * 0.25)];
            const q3 = sorted[Math.floor(sorted.length * 0.75)];
            
            stats[column] = {
                type: 'numeric',
                count: numericValues.length,
                mean: mean,
                std: std,
                min: sorted[0],
                q25: q1,
                median: median,
                q75: q3,
                max: sorted[sorted.length - 1]
            };
        } else {
            // Calculate categorical statistics
            const uniqueValues = new Set(values);
            const valueCounts = {};
            values.forEach(v => {
                valueCounts[v] = (valueCounts[v] || 0) + 1;
            });
            const topValue = Object.entries(valueCounts).sort((a, b) => b[1] - a[1])[0];
            
            stats[column] = {
                type: 'categorical',
                count: values.length,
                unique: uniqueValues.size,
                top: topValue ? topValue[0] : null,
                freq: topValue ? topValue[1] : null
            };
        }
    });
    
    return stats;
}

// Format statistics as HTML
function formatStatistics(stats) {
    let html = '<h3 style="margin-bottom: 15px;">📊 Statistical Summary</h3>';
    html += '<div class="stats-container">';
    
    Object.entries(stats).forEach(([column, stat]) => {
        html += '<div class="stat-column">';
        html += `<h4>${escapeHtml(column)}</h4>`;
        
        if (stat.type === 'numeric') {
            html += '<table class="stats-table">';
            html += `<tr><td>Count</td><td>${stat.count}</td></tr>`;
            html += `<tr><td>Mean</td><td>${stat.mean.toFixed(2)}</td></tr>`;
            html += `<tr><td>Std</td><td>${stat.std.toFixed(2)}</td></tr>`;
            html += `<tr><td>Min</td><td>${stat.min.toFixed(2)}</td></tr>`;
            html += `<tr><td>25%</td><td>${stat.q25.toFixed(2)}</td></tr>`;
            html += `<tr><td>50% (Median)</td><td>${stat.median.toFixed(2)}</td></tr>`;
            html += `<tr><td>75%</td><td>${stat.q75.toFixed(2)}</td></tr>`;
            html += `<tr><td>Max</td><td>${stat.max.toFixed(2)}</td></tr>`;
            html += '</table>';
        } else {
            html += '<table class="stats-table">';
            html += `<tr><td>Count</td><td>${stat.count}</td></tr>`;
            html += `<tr><td>Unique</td><td>${stat.unique}</td></tr>`;
            html += `<tr><td>Top</td><td>${escapeHtml(String(stat.top))}</td></tr>`;
            html += `<tr><td>Freq</td><td>${stat.freq}</td></tr>`;
            html += '</table>';
        }
        
        html += '</div>';
    });
    
    html += '</div>';
    return html;
}

// Make functions globally accessible for onclick handlers
window.askQuestion = askQuestion;
window.toggleSql = toggleSql;
window.togglePrompt = togglePrompt;
window.copySql = copySql;
window.copyResults = copyResults;
window.exportToExcel = exportToExcel;
window.loadTables = loadTables;
window.filterTables = filterTables;
window.fillQuestion = fillQuestion;
window.clearHistory = clearHistory;
window.toggleDescribe = toggleDescribe;

// Enter key to submit
document.addEventListener('DOMContentLoaded', () => {
    const questionInput = document.getElementById('question-input');
    questionInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Prevent newline
            askQuestion();
        }
    });
    
    // Load history on page load
    displayHistory();
});
