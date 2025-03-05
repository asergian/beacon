/**
 * @fileoverview Analytics dashboard functionality for monitoring system performance.
 * Handles fetching, displaying, and updating analytical data across multiple sections.
 * @author Beacon Team
 * @license Copyright 2025 Beacon
 */

/**
 * @type {Object|null} Stores the most recent analytics data from the server
 */
let currentStats = null;

/**
 * @type {boolean} Flag to track if an analytics request is in progress
 */
let isLoading = false;

/**
 * Section visibility state object to track which dashboard sections are visible
 * @type {Object<string, boolean>}
 */
const sectionVisibility = {
    overview: true,
    llm: true,
    email: true,
    nlp: true,
    activity: true
};

/**
 * Fetches analytics data from the server and updates the dashboard.
 * Shows loading indicators during fetch and handles errors.
 * 
 * @return {Promise<void>} A promise that resolves when analytics are fetched and displayed
 */
async function fetchAnalytics() {
    if (isLoading) return;
    
    try {
        isLoading = true;
        updateLoadingState(true);
        
        const response = await fetch('/user/api/analytics');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        
        currentStats = data;
        updateDashboard(data);
        updateLoadingState(false);
    } catch (error) {
        console.error('Failed to fetch analytics:', error);
        updateLoadingState(false);
    } finally {
        isLoading = false;
    }
}

/**
 * Updates the loading state of a refresh button.
 * Adds loading spinner and disables the button during loading.
 * 
 * @param {boolean} loading - Whether the button should show loading state
 * @param {Element} button - The button element to update (defaults to the main refresh button)
 * @return {void}
 */
function updateLoadingState(loading, button = document.querySelector('.refresh-button')) {
    if (!button) return;
    
    if (loading) {
        button.classList.add('loading');
        button.disabled = true;
        button.innerHTML = '<span class="loading-spinner"></span>';
    } else {
        button.classList.remove('loading');
        button.disabled = false;
        button.innerHTML = '';
    }
}

/**
 * Updates the dashboard with the latest analytics data.
 * Populates statistics in various dashboard sections including system overview,
 * LLM usage, email processing, NLP analytics, and user activity.
 * 
 * @param {Object} data - The analytics data from the server
 * @param {Object} data.user_stats - User-related statistics
 * @param {Object} data.email_stats - Email processing statistics
 * @param {Object} data.nlp_stats - Natural language processing statistics
 * @param {Object} data.llm_stats - Language model usage statistics
 * @param {Array} data.recent_activities - Recent system activities
 * @return {void}
 */
function updateDashboard(data) {
    console.log('Received analytics data:', data);
    
    // Update system overview stats
    const userStats = data.user_stats || {};
    const emailStats = data.email_stats || {};
    const nlpStats = data.nlp_stats || {};
    const llmStats = data.llm_stats || {};
    
    // User stats in overview
    document.getElementById('total-users').textContent = 
        (userStats.total_users || 0).toLocaleString();
    document.getElementById('active-today').textContent = 
        (userStats.active_today || 0).toLocaleString();
    
    // Total emails processed in overview
    document.getElementById('total-emails-processed').textContent = 
        (emailStats.total_fetched || 0).toLocaleString();
    
    // Overall system success rate (combine email and LLM success rates)
    const emailSuccessRate = emailStats.total_fetched ? 
        ((emailStats.successfully_analyzed || 0) / emailStats.total_fetched * 100) : 0;
    const llmSuccessRate = llmStats.success_rate || 0;
    const systemSuccessRate = (emailSuccessRate + llmSuccessRate) / 2;
    document.getElementById('system-success-rate').textContent = 
        `${systemSuccessRate.toFixed(1)}%`;
    
    // Total processing time (NLP + LLM)
    const totalProcessingTime = 
        (nlpStats.avg_processing_time || 0) * 1000 + 
        (llmStats.avg_processing_time_ms || 0);
    document.getElementById('total-processing-time').textContent = 
        `${Math.round(totalProcessingTime)}ms`;
    
    // Total cost in overview
    document.getElementById('total-cost').textContent = 
        `$${((llmStats.total_cost_cents || 0) / 100).toFixed(2)}`;
    
    // Update LLM stats section
    document.getElementById('total-tokens').textContent = 
        (llmStats.total_tokens || 0).toLocaleString();
    document.getElementById('total-requests').textContent = 
        (llmStats.total_requests || 0).toLocaleString();
    document.getElementById('llm-total-cost').textContent = 
        `$${((llmStats.total_cost_cents || 0) / 100).toFixed(2)}`;
    document.getElementById('success-rate').textContent = 
        `${(llmStats.success_rate || 0).toFixed(1)}%`;
    
    // Per-request averages for LLM
    document.getElementById('avg-tokens-per-req').textContent = 
        Math.round(llmStats.avg_tokens_per_request || 0).toLocaleString();
    document.getElementById('avg-cost-per-req').textContent = 
        `$${((llmStats.avg_cost_cents_per_request || 0) / 100).toFixed(3)}`;
    document.getElementById('llm-avg-processing-time').textContent = 
        Math.round(llmStats.avg_processing_time_ms || 0).toLocaleString();
    
    // Update email stats section
    document.getElementById('total-fetched').textContent = 
        (emailStats.total_fetched || 0).toLocaleString();
    
    // Cache hit rate (inverse of new emails rate)
    const totalFetched = emailStats.total_fetched || 0;
    const newEmails = emailStats.new_emails || 0;
    const cacheHitRate = totalFetched > 0 ? 
        ((totalFetched - newEmails) / totalFetched * 100) : 0;
    document.getElementById('cache-hit-rate').textContent = 
        `${cacheHitRate.toFixed(1)}%`;
    
    // Analysis failure rate
    const totalAnalyzed = (emailStats.successfully_analyzed || 0) + 
                        (emailStats.failed_parsing || 0) + 
                        (emailStats.failed_analysis || 0);
    const failureRate = totalAnalyzed > 0 ? 
        (((emailStats.failed_parsing || 0) + (emailStats.failed_analysis || 0)) / totalAnalyzed * 100) : 0;
    document.getElementById('analysis-failure-rate').textContent = 
        `${failureRate.toFixed(1)}%`;
    
    // Action required (combine needs_action and has_deadline)
    const actionRequired = Math.max(
        emailStats.needs_action || 0,
        emailStats.has_deadline || 0
    );
    document.getElementById('action-required').textContent = 
        actionRequired.toLocaleString();
    
    // Update user activity section with user stats
    document.getElementById('activity-total-users').textContent = 
        (userStats.total_users || 0).toLocaleString();
    document.getElementById('activity-active-users').textContent = 
        (userStats.active_users || 0).toLocaleString();
    document.getElementById('activity-active-today').textContent = 
        (userStats.active_today || 0).toLocaleString();
    
    // Update NLP stats
    console.log('Updating NLP stats:', data.nlp_stats);
    document.getElementById('entities-extracted').textContent = (data.nlp_stats.total_entities || 0).toLocaleString();
    
    const urgencyRate = data.nlp_stats.total_emails ? 
        ((data.nlp_stats.urgent_emails / data.nlp_stats.total_emails) * 100) : 0;
    document.getElementById('urgent-emails').textContent = `${urgencyRate.toFixed(1)}%`;
    
    document.getElementById('avg-complexity').textContent = 
        Math.round(data.nlp_stats.avg_sentences_per_email || 0).toLocaleString();
    document.getElementById('avg-processing-time').textContent = 
        Math.round((data.nlp_stats.avg_processing_time || 0) * 1000);
    
    // Update activity stats
    const activityList = document.getElementById('activity-list');
    const newActivities = data.recent_activities.map(activity => {
        const activityType = getActivityType(activity.type);
        const metadata = activity.metadata ? formatMetadata(activity.metadata) : '';
        
        return `
        <li class="activity-item">
                <div class="activity-meta">
            <div class="activity-time">${new Date(activity.created_at).toLocaleString()}</div>
                    <div class="activity-type ${activityType.class}">${activityType.label}</div>
                </div>
                <div class="activity-content">
                    <div class="activity-description">${activity.description}</div>
                    ${metadata ? `<div class="activity-metadata">${metadata}</div>` : ''}
                </div>
        </li>
        `;
    }).join('');
    
    if (activityList.innerHTML !== newActivities) {
        activityList.style.opacity = '0';
        setTimeout(() => {
            activityList.innerHTML = newActivities;
            activityList.style.opacity = '1';
        }, 300);
    }
    
    // Create charts with responsive layout
    createLLMChart(data.llm_stats);
    createModelDistributionChart(data.llm_stats);
    createEmailChart(data.email_stats);
    createNLPChart(data.nlp_stats);
}

/**
 * Creates a chart displaying LLM performance metrics.
 * Visualizes total tokens, requests, average tokens per request,
 * and average processing time in a bar chart.
 * 
 * @param {Object} stats - LLM statistics from the analytics data
 * @param {number} stats.total_tokens - Total tokens processed by LLMs
 * @param {number} stats.total_requests - Total number of LLM API requests
 * @param {number} stats.avg_tokens_per_request - Average tokens per request
 * @param {number} stats.avg_processing_time_ms - Average processing time in milliseconds
 * @return {void}
 */
function createLLMChart(stats) {
    const trace = {
        x: ['Total Tokens', 'Total Requests', 'Avg. Tokens/Req', 'Avg. Time (ms)'],
        y: [
            stats.total_tokens || 0,
            stats.total_requests || 0,
            stats.avg_tokens_per_request || 0,
            stats.avg_processing_time_ms || 0
        ],
        type: 'bar',
        marker: {
            color: [
                '#2563EB',  // Deep blue for Tokens
                '#16A34A',  // Forest green for Requests
                '#F97316',  // Vibrant orange for Avg Tokens
                '#6366F1'   // Indigo for Avg Time
            ]
        },
        text: [
            (stats.total_tokens || 0).toLocaleString(),
            (stats.total_requests || 0).toLocaleString(),
            Math.round(stats.avg_tokens_per_request || 0).toLocaleString(),
            Math.round(stats.avg_processing_time_ms || 0).toLocaleString()
        ],
        textposition: 'auto',
    };
    
    const layout = {
        title: {
            text: 'Performance Metrics',
            font: { size: 16 },
            y: 0.98
        },
        height: 400,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { 
            t: 40,
            r: 20, 
            b: 100,
            l: 60 
        },
        yaxis: {
            type: 'log',
            title: 'Value (log scale)'
        }
    };
    
    const config = { 
        responsive: true,
        displayModeBar: false
    };
    
    Plotly.newPlot('llm-usage-chart', [trace], layout, config);
}

/**
 * Creates a chart displaying the distribution of usage across different LLM models.
 * Shows both total tokens and request counts for each model in a combination
 * bar and line chart.
 * 
 * @param {Object} stats - LLM statistics from the analytics data
 * @param {Object} stats.requests_by_model - Map of model names to request counts
 * @param {Object} stats.tokens_by_model - Map of model names to token usage data
 * @return {void}
 */
function createModelDistributionChart(stats) {
    const models = Object.keys(stats.requests_by_model || {});
    const tokensByModel = models.map(model => (stats.tokens_by_model || {})[model]?.total_tokens || 0);
    const requestsByModel = models.map(model => (stats.requests_by_model || {})[model] || 0);
    
    const tokenTrace = {
        x: models,
        y: tokensByModel,
        name: 'Total Tokens',
        type: 'bar',
        marker: { color: '#3B82F6' }  // Blue for tokens
    };
    
    const requestTrace = {
        x: models,
        y: requestsByModel,
        name: 'Total Requests',
        yaxis: 'y2',
        type: 'scatter',
        mode: 'lines+markers',
        marker: { color: '#10B981' }  // Green for requests
    };
    
    const layout = {
        title: {
            text: 'Model Usage Distribution',
            font: { size: 16 },
            y: 0.98
        },
        height: 400,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { 
            t: 40,
            r: 70,
            b: 100,
            l: 60 
        },
        yaxis: { 
            title: 'Total Tokens',
            titlefont: { color: '#3B82F6' },
            tickfont: { color: '#3B82F6' }
        },
        yaxis2: {
            title: 'Total Requests',
            titlefont: { color: '#10B981' },
            tickfont: { color: '#10B981' },
            overlaying: 'y',
            side: 'right'
        },
        showlegend: true,
        legend: {
            orientation: 'h',
            y: -0.2,
            xanchor: 'center',
            x: 0.5
        },
        bargap: 0.3
    };
    
    const config = { 
        responsive: true,
        displayModeBar: false
    };
    
    Plotly.newPlot('llm-model-distribution', [tokenTrace, requestTrace], layout, config);
}

/**
 * Creates charts displaying email categorization and priority statistics.
 * Generates two pie charts: one for email categories and one for priority levels.
 * 
 * @param {Object} stats - Email processing statistics
 * @param {Object} stats.categories - Map of category names to email counts
 * @param {Object} stats.priority_levels - Map of priority levels to email counts
 * @return {void}
 */
function createEmailChart(stats) {
    // Create category distribution chart
    const categoryTrace = {
        labels: Object.keys(stats.categories || {}),
        values: Object.values(stats.categories || {}),
        type: 'pie',
        name: 'Categories',
        marker: {
            colors: [
                '#2563EB',  // Work - Professional deep blue
                '#16A34A',  // Personal - Forest green
                '#F97316',  // Promotions - Vibrant orange
                '#6366F1'   // Informational - Indigo
            ]
        },
        hole: 0.25
    };
    
    // Create priority distribution chart
    const priorityTrace = {
        labels: ['High', 'Medium', 'Low'].filter(level => (stats.priority_levels || {})[level.toUpperCase()] !== undefined),
        values: ['HIGH', 'MEDIUM', 'LOW'].map(level => (stats.priority_levels || {})[level] || 0),
        type: 'pie',
        name: 'Priorities',
        marker: {
            colors: [
                '#FF4B4B',  // HIGH - Bright red
                '#FF8C42',  // MEDIUM - Orange
                '#66BB6A'   // LOW - Green
            ]
        },
        hole: 0.25
    };
    
    const baseLayout = {
        height: 400,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { 
            t: 40,
            r: 20, 
            b: 100,
            l: 20 
        },
        showlegend: true,
        legend: {
            orientation: 'h',
            y: -0.2,
            xanchor: 'center',
            x: 0.5
        }
    };
    
    const config = { 
        responsive: true,
        displayModeBar: false
    };
    
    // Create separate charts with titles
    Plotly.newPlot('email-category-chart', [categoryTrace], {
        ...baseLayout,
        title: {
            text: 'Categories',
            font: { size: 16 },
            y: 0.98
        }
    }, config);
    
    Plotly.newPlot('email-priority-chart', [priorityTrace], {
        ...baseLayout,
        title: {
            text: 'Priorities',
            font: { size: 16 },
            y: 0.98
        }
    }, config);
}

/**
 * Creates charts displaying NLP analysis results.
 * Generates an entity distribution bar chart and an urgency distribution pie chart.
 * 
 * @param {Object} stats - NLP statistics from the analytics data
 * @param {Object} stats.entity_types - Counts of different entity types extracted
 * @param {number} stats.total_emails - Total number of emails analyzed
 * @param {number} stats.urgent_emails - Number of emails classified as urgent
 * @return {void}
 */
function createNLPChart(stats) {
    // Entity Types Bar Chart
    const entityTrace = {
        x: ['People', 'Organizations', 'Dates', 'Locations', 'Other'],
        y: [
            (stats.entity_types?.PERSON || 0),
            (stats.entity_types?.ORG || 0),
            (stats.entity_types?.DATE || 0),
            (stats.entity_types?.LOC || 0),
            (stats.entity_types?.MISC || 0)
        ],
        name: 'Entity Types',
        type: 'bar',
        marker: {
            color: [
                '#3B82F6',  // Blue for People
                '#10B981',  // Green for Organizations
                '#F59E0B',  // Amber for Dates
                '#6366F1',  // Indigo for Locations
                '#8B5CF6'   // Purple for Other
            ]
        }
    };
    
    const entityLayout = {
        title: {
            text: 'Entity Distribution',
            font: { size: 16 },
            y: 0.98
        },
        height: 400,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { 
            t: 40,
            r: 20, 
            b: 100,
            l: 60 
        },
        showlegend: false,
        yaxis: {
            title: 'Count'
        }
    };

    // Urgency Distribution Pie Chart
    const totalEmails = stats.total_emails || 0;
    const urgentEmails = stats.urgent_emails || 0;
    
    const urgencyTrace = {
        labels: ['Urgent', 'Normal'],
        values: [urgentEmails, totalEmails - urgentEmails],
        name: 'Urgency Distribution',
        type: 'pie',
        marker: {
            colors: [
                '#EF4444',  // Red for Urgent
                '#6B7280'   // Gray for Normal
            ]
        },
        hole: 0.25
    };
    
    const urgencyLayout = {
        title: {
            text: 'Urgency Distribution',
            font: { size: 16 },
            y: 0.98
        },
        height: 400,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { 
            t: 40,
            r: 20, 
            b: 100,
            l: 20 
        },
        showlegend: true,
        legend: {
            orientation: 'h',
            y: -0.2,
            xanchor: 'center',
            x: 0.5
        }
    };
    
    const config = { 
        responsive: true,
        displayModeBar: false
    };
    
    // Create separate charts
    Plotly.newPlot('nlp-entities-chart', [entityTrace], entityLayout, config);
    Plotly.newPlot('nlp-urgency-chart', [urgencyTrace], urgencyLayout, config);
}

/**
 * Refreshes a specific dashboard section with the latest analytics data.
 * Fetches fresh data from the server and updates only the specified section.
 * 
 * @param {string} section - The name of the section to refresh (e.g., 'System Overview')
 * @return {Promise<void>} A promise that resolves when the section is refreshed
 */
async function refreshSection(section) {
    if (isLoading) return;
    
    const header = Array.from(document.querySelectorAll('.stats-header'))
        .find(header => header.querySelector('h2').textContent === section);
    const button = header ? header.querySelector('.refresh-button') : null;
    
    if (!button) return;
    
    try {
        isLoading = true;
        updateLoadingState(true, button);
        
        const response = await fetch('/user/api/analytics');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Update only the specific section
        switch(section) {
            case 'System Overview':
                updateOverviewStats(data);
                break;
            case 'LLM Usage Statistics':
                updateLLMStats(data);
                createLLMChart(data.llm_stats);
                createModelDistributionChart(data.llm_stats);
                break;
            case 'Email Processing Statistics':
                updateEmailStats(data);
                createEmailChart(data.email_stats);
                break;
            case 'NLP Analytics':
                updateNLPStats(data);
                createNLPChart(data.nlp_stats);
                break;
            case 'User Activity & Analytics':
                updateActivityStats(data);
                break;
        }
    } catch (error) {
        console.error(`Failed to refresh ${section} section:`, error);
    } finally {
        updateLoadingState(false, button);
        isLoading = false;
    }
}

/**
 * Updates the System Overview section with the latest analytics data.
 * Refreshes user counts, email processing stats, system success rate,
 * processing time, and total cost.
 * 
 * @param {Object} data - The analytics data from the server
 * @return {void}
 */
function updateOverviewStats(data) {
    const userStats = data.user_stats || {};
    const emailStats = data.email_stats || {};
    const nlpStats = data.nlp_stats || {};
    const llmStats = data.llm_stats || {};
    
    document.getElementById('total-users').textContent = 
        (userStats.total_users || 0).toLocaleString();
    document.getElementById('active-today').textContent = 
        (userStats.active_today || 0).toLocaleString();
    document.getElementById('total-emails-processed').textContent = 
        (emailStats.total_fetched || 0).toLocaleString();
    
    const emailSuccessRate = emailStats.total_fetched ? 
        ((emailStats.successfully_analyzed || 0) / emailStats.total_fetched * 100) : 0;
    const llmSuccessRate = llmStats.success_rate || 0;
    const systemSuccessRate = (emailSuccessRate + llmSuccessRate) / 2;
    document.getElementById('system-success-rate').textContent = 
        `${systemSuccessRate.toFixed(1)}%`;
    
    const totalProcessingTime = 
        (nlpStats.avg_processing_time || 0) * 1000 + 
        (llmStats.avg_processing_time_ms || 0);
    document.getElementById('total-processing-time').textContent = 
        `${Math.round(totalProcessingTime)}ms`;
    
    document.getElementById('total-cost').textContent = 
        `$${((llmStats.total_cost_cents || 0) / 100).toFixed(2)}`;
}

/**
 * Updates the LLM Usage Statistics section with the latest analytics data.
 * Refreshes token counts, request counts, costs, success rate, and performance metrics.
 * 
 * @param {Object} data - The analytics data from the server
 * @return {void}
 */
function updateLLMStats(data) {
    const llmStats = data.llm_stats || {};
    
    document.getElementById('total-tokens').textContent = 
        (llmStats.total_tokens || 0).toLocaleString();
    document.getElementById('total-requests').textContent = 
        (llmStats.total_requests || 0).toLocaleString();
    document.getElementById('llm-total-cost').textContent = 
        `$${((llmStats.total_cost_cents || 0) / 100).toFixed(2)}`;
    document.getElementById('success-rate').textContent = 
        `${(llmStats.success_rate || 0).toFixed(1)}%`;
    
    document.getElementById('avg-tokens-per-req').textContent = 
        Math.round(llmStats.avg_tokens_per_request || 0).toLocaleString();
    document.getElementById('avg-cost-per-req').textContent = 
        `$${((llmStats.avg_cost_cents_per_request || 0) / 100).toFixed(3)}`;
    document.getElementById('llm-avg-processing-time').textContent = 
        Math.round(llmStats.avg_processing_time_ms || 0).toLocaleString();
}

/**
 * Updates the Email Processing Statistics section with the latest analytics data.
 * Refreshes email counts, cache hit rate, failure rate, and action requirements.
 * 
 * @param {Object} data - The analytics data from the server
 * @return {void}
 */
function updateEmailStats(data) {
    const emailStats = data.email_stats || {};
    const totalFetched = emailStats.total_fetched || 0;
    const newEmails = emailStats.new_emails || 0;
    const failedParsing = emailStats.failed_parsing || 0;
    const failedAnalysis = emailStats.failed_analysis || 0;
    
    document.getElementById('total-fetched').textContent = 
        totalFetched.toLocaleString();
    
    // Fix cache hit rate calculation and rounding
    const cacheHitRate = totalFetched > 0 ? 
        ((totalFetched - newEmails) / totalFetched * 100) : 0;
    document.getElementById('cache-hit-rate').textContent = 
        `${cacheHitRate.toFixed(1)}%`;
    
    // Fix analysis failure rate calculation and rounding
    const totalAnalyzed = totalFetched;
    const failureRate = totalAnalyzed > 0 ? 
        ((failedParsing + failedAnalysis) / totalAnalyzed * 100) : 0;
    document.getElementById('analysis-failure-rate').textContent = 
        `${failureRate.toFixed(1)}%`;
    
    document.getElementById('action-required').textContent = 
        Math.max(emailStats.needs_action || 0, emailStats.has_deadline || 0).toLocaleString();
}

/**
 * Updates the NLP Analytics section with the latest analytics data.
 * Refreshes entity extraction counts, urgency metrics, complexity metrics,
 * and processing time.
 * 
 * @param {Object} data - The analytics data from the server
 * @return {void}
 */
function updateNLPStats(data) {
    const nlpStats = data.nlp_stats || {};
    const totalEmails = nlpStats.total_emails || 0;
    const urgentEmails = nlpStats.urgent_emails || 0;
    
    document.getElementById('entities-extracted').textContent = 
        (nlpStats.total_entities || 0).toLocaleString();
    
    // Fix urgent emails percentage calculation and rounding
    const urgentRate = totalEmails > 0 ? (urgentEmails / totalEmails * 100) : 0;
    document.getElementById('urgent-emails').textContent = 
        `${urgentRate.toFixed(1)}%`;
    
    document.getElementById('avg-complexity').textContent = 
        Math.round(nlpStats.avg_sentences_per_email || 0).toLocaleString();
    document.getElementById('avg-processing-time').textContent = 
        Math.round((nlpStats.avg_processing_time || 0) * 1000).toLocaleString();
}

/**
 * Updates the User Activity & Analytics section with the latest analytics data.
 * Refreshes total user count, active user count, and users active today.
 * 
 * @param {Object} data - The analytics data from the server
 * @return {void}
 */
function updateActivityStats(data) {
    const userStats = data.user_stats || {};
    
    document.getElementById('activity-total-users').textContent = 
        (userStats.total_users || 0).toLocaleString();
    document.getElementById('activity-active-users').textContent = 
        (userStats.active_users || 0).toLocaleString();
    document.getElementById('activity-active-today').textContent = 
        (userStats.active_today || 0).toLocaleString();
}

/**
 * Gets the display style information for an activity type.
 * Maps activity types to their corresponding CSS classes and display labels.
 * 
 * @param {string} type - The activity type from the server
 * @return {Object} Object containing class and label properties
 * @return {string} return.class - CSS class to apply to the activity
 * @return {string} return.label - Display label for the activity type
 */
function getActivityType(type) {
    switch (type.toLowerCase()) {
        case 'email_processing':
        case 'email_analysis':
            return { class: 'email', label: 'Email' };
        case 'pipeline_processing':
        case 'nlp_analysis':
            return { class: 'analysis', label: 'Analysis' };
        case 'error':
        case 'failure':
            return { class: 'error', label: 'Error' };
        default:
            return { class: 'default-activity', label: 'Activity' };
    }
}

/**
 * Formats activity metadata into a readable string for display.
 * Handles different types of metadata including email stats, entity analysis,
 * LLM processing, and user information.
 * 
 * @param {Object} metadata - The metadata object from an activity
 * @return {string} Formatted metadata string for display
 */
function formatMetadata(metadata) {
    if (!metadata || typeof metadata !== 'object') return '';
    
    const formattedParts = [];
    
    // Handle email processing stats
    if (metadata.stats) {
        const stats = metadata.stats;
        const parts = [];
        if (stats.total_fetched || stats.emails_fetched) {
            parts.push(`${stats.total_fetched || stats.emails_fetched} fetched`);
        }
        if (stats.successfully_analyzed) {
            parts.push(`${stats.successfully_analyzed} analyzed`);
        }
        if (stats.failed_parsing || stats.failed_analysis) {
            const failed = (stats.failed_parsing || 0) + (stats.failed_analysis || 0);
            if (failed > 0) parts.push(`${failed} failed`);
        }
        if (parts.length > 0) {
            formattedParts.push(parts.join(' • '));
        }
    }
    
    // Handle NLP analysis
    if (metadata.entities) {
        const entityCount = Object.keys(metadata.entities).length;
        const entityTypes = Object.entries(metadata.entities)
            .map(([type, count]) => `${count} ${type.toLowerCase()}`)
            .join(', ');
        formattedParts.push(`Entities: ${entityTypes}`);
    }
    
    // Handle LLM requests
    if (metadata.model) {
        const parts = [`Model: ${metadata.model}`];
        if (metadata.total_tokens) {
            parts.push(`${metadata.total_tokens.toLocaleString()} tokens`);
        }
        if (metadata.processing_time_ms || metadata.processing_time) {
            const time = metadata.processing_time_ms || (metadata.processing_time * 1000);
            parts.push(`${Math.round(time)}ms`);
        }
        formattedParts.push(parts.join(' • '));
    }
    
    // Handle email metadata
    if (metadata.category || metadata.priority || metadata.is_urgent) {
        const parts = [];
        if (metadata.category) parts.push(`Category: ${metadata.category}`);
        if (metadata.priority) parts.push(`Priority: ${metadata.priority}`);
        if (metadata.is_urgent) parts.push('Urgent');
        formattedParts.push(parts.join(' • '));
    }
    
    // Handle user info
    if (metadata.user_email || metadata.user_name) {
        const parts = [];
        if (metadata.user_name) parts.push(metadata.user_name);
        if (metadata.user_email) parts.push(metadata.user_email);
        formattedParts.push(parts.join(' - '));
    }
    
    return formattedParts.filter(part => part).join(' • ');
}

// Initialize section toggles
/**
 * Initializes toggle switches for showing/hiding dashboard sections.
 * Sets up event listeners on toggle elements and manages section visibility state.
 * Each toggle controls the display of a corresponding dashboard section.
 * 
 * @return {void}
 */
function initializeSectionToggles() {
    const sections = {
        overview: document.querySelector('.stats-card:nth-child(1)'),
        email: document.querySelector('.stats-card:nth-child(2)'),
        nlp: document.querySelector('.stats-card:nth-child(3)'),
        llm: document.querySelector('.stats-card:nth-child(4)'),
        activity: document.querySelector('.stats-card:nth-child(5)')
    };
    
    Object.entries(sections).forEach(([key, section]) => {
        const toggle = document.getElementById(`toggle-${key}`);
        if (toggle && section) {
            toggle.addEventListener('change', (e) => {
                sectionVisibility[key] = e.target.checked;
                section.style.display = e.target.checked ? 'block' : 'none';
                // Trigger resize event to redraw charts if section becomes visible
                if (e.target.checked && currentStats) {
                    window.dispatchEvent(new Event('resize'));
                }
            });
        }
    });
}

// Add to DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    fetchAnalytics();
    initializeSectionToggles();
});

// Add window resize handler for charts
window.addEventListener('resize', () => {
    if (currentStats) {
        createLLMChart(currentStats.llm_stats);
        createModelDistributionChart(currentStats.llm_stats);
        createEmailChart(currentStats.email_stats);
        createNLPChart(currentStats.nlp_stats);
    }
});

// Refresh every 5 minutes
setInterval(fetchAnalytics, 5 * 60 * 1000);

/**
 * Refreshes all dashboard sections with the latest analytics data.
 * Fetches fresh data from the server and updates all statistics and charts.
 * 
 * @return {Promise<void>} A promise that resolves when all sections are refreshed
 */
async function refreshAll() {
    if (isLoading) return;
    
    const button = document.querySelector('.stats-card:first-child .refresh-button');
    if (!button) return;
    
    try {
        isLoading = true;
        updateLoadingState(true, button);
        
        const response = await fetch('/user/api/analytics');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Update all sections
        updateOverviewStats(data);
        updateLLMStats(data);
        updateEmailStats(data);
        updateNLPStats(data);
        updateActivityStats(data);
        
        // Update all charts
        createLLMChart(data.llm_stats);
        createModelDistributionChart(data.llm_stats);
        createEmailChart(data.email_stats);
        createNLPChart(data.nlp_stats);
        
    } catch (error) {
        console.error('Failed to refresh all sections:', error);
    } finally {
        updateLoadingState(false, button);
        isLoading = false;
    }
} 