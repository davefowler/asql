// ASQL Documentation JavaScript - Dialect Tabs

// Initialize dialect tracking from localStorage
function initDialectTracking() {
    // Get or initialize dialects tracking object
    let dialects = JSON.parse(localStorage.getItem('asql_dialects') || '{}');
    
    // Get user's preferred second tab (asql is always first)
    const preferredDialect = localStorage.getItem('asql_preferred_dialect');
    
    return { dialects, preferredDialect };
}

// Save dialect preference
function saveDialectPreference(dialect) {
    localStorage.setItem('asql_preferred_dialect', dialect);
    
    // Update view count
    let dialects = JSON.parse(localStorage.getItem('asql_dialects') || '{}');
    dialects[dialect] = (dialects[dialect] || 0) + 1;
    localStorage.setItem('asql_dialects', JSON.stringify(dialects));
}

// Get sorted dialects by view count (excluding asql)
function getSortedDialects(compiled) {
    const { dialects } = initDialectTracking();
    
    // Get all dialects except asql
    const allDialects = Object.keys(compiled).filter(d => d !== 'asql');
    
    // Sort by view count (descending), then alphabetically
    return allDialects.sort((a, b) => {
        const countA = dialects[a] || 0;
        const countB = dialects[b] || 0;
        if (countB !== countA) {
            return countB - countA;
        }
        return a.localeCompare(b);
    });
}

// Show dialect in a code block
function showDialect(blockId, dialect) {
    const block = document.querySelector(`[data-block-id="${blockId}"]`);
    if (!block) return;
    
    // Get compiled SQL
    const compiledB64 = block.getAttribute('data-compiled');
    const compiled = JSON.parse(atob(compiledB64));
    
    // Update code content
    const codeElement = document.getElementById(`code-${blockId}`);
    if (codeElement && compiled[dialect]) {
        codeElement.textContent = compiled[dialect];
        
        // Highlight syntax
        if (window.hljs) {
            hljs.highlightElement(codeElement);
        }
    }
    
    // Update active tab
    const tabs = block.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
        if (tab.getAttribute('data-dialect') === dialect) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    // Track view
    if (dialect !== 'asql') {
        saveDialectPreference(dialect);
    }
    
    // Close more dialects menu if open
    const menu = block.querySelector('.more-dialects-menu');
    if (menu) {
        menu.classList.remove('show');
    }
}

// Show more dialects menu
function showMoreDialects(blockId) {
    const block = document.querySelector(`[data-block-id="${blockId}"]`);
    if (!block) return;
    
    // Get compiled SQL
    const compiledB64 = block.getAttribute('data-compiled');
    const compiled = JSON.parse(atob(compiledB64));
    
    // Get top dialects
    const topDialects = ['postgres', 'snowflake', 'bigquery', 'redshift'];
    const otherDialects = Object.keys(compiled).filter(
        d => d !== 'asql' && !topDialects.includes(d)
    );
    
    if (otherDialects.length === 0) return;
    
    // Create or update menu
    let menu = block.querySelector('.more-dialects-menu');
    if (!menu) {
        menu = document.createElement('div');
        menu.className = 'more-dialects-menu';
        block.appendChild(menu);
    }
    
    // Clear and populate menu
    menu.innerHTML = '';
    otherDialects.forEach(dialect => {
        const btn = document.createElement('button');
        btn.textContent = getDialectName(dialect);
        btn.onclick = () => {
            showDialect(blockId, dialect);
            // Reorder tabs based on new view count
            reorderTabs(blockId);
        };
        menu.appendChild(btn);
    });
    
    // Position menu
    const moreTab = block.querySelector('.more-tab');
    const rect = moreTab.getBoundingClientRect();
    menu.style.top = `${rect.bottom}px`;
    menu.style.left = `${rect.left}px`;
    
    // Toggle menu
    menu.classList.toggle('show');
}

// Get dialect display name
function getDialectName(dialect) {
    const names = {
        'postgres': 'PostgreSQL',
        'snowflake': 'Snowflake',
        'bigquery': 'BigQuery',
        'redshift': 'Redshift',
        'mysql': 'MySQL',
        'sqlite': 'SQLite',
        'oracle': 'Oracle',
        'mssql': 'SQL Server',
        'presto': 'Presto',
        'trino': 'Trino',
        'spark': 'Spark',
        'hive': 'Hive',
        'clickhouse': 'ClickHouse',
        'duckdb': 'DuckDB',
        'databricks': 'Databricks',
    };
    return names[dialect] || dialect.charAt(0).toUpperCase() + dialect.slice(1);
}

// Reorder tabs after a dialect is viewed (called from showDialect)
function reorderTabs(blockId) {
    // Just reorder on load, don't dynamically reorder during session
    // This prevents confusion from tabs moving around
    reorderTabsOnLoad(blockId);
}

// Initialize all code blocks on page load
document.addEventListener('DOMContentLoaded', () => {
    const blocks = document.querySelectorAll('.asql-code-block');
    
    blocks.forEach(block => {
        const blockId = block.getAttribute('data-block-id');
        const { preferredDialect } = initDialectTracking();
        
        // Reorder tabs based on view counts
        reorderTabsOnLoad(blockId);
        
        // Show preferred dialect or default to asql
        const initialDialect = preferredDialect && 
            block.getAttribute('data-compiled') && 
            JSON.parse(atob(block.getAttribute('data-compiled')))[preferredDialect]
            ? preferredDialect 
            : 'asql';
        
        showDialect(blockId, initialDialect);
    });
    
    // Close more dialects menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.more-tab') && !e.target.closest('.more-dialects-menu')) {
            document.querySelectorAll('.more-dialects-menu').forEach(menu => {
                menu.classList.remove('show');
            });
        }
    });
});

// Reorder tabs on page load based on view counts
function reorderTabsOnLoad(blockId) {
    const block = document.querySelector(`[data-block-id="${blockId}"]`);
    if (!block) return;
    
    const compiledB64 = block.getAttribute('data-compiled');
    const compiled = JSON.parse(atob(compiledB64));
    
    const { dialects } = initDialectTracking();
    const topDialects = ['postgres', 'snowflake', 'bigquery', 'redshift'];
    const topDialectsAvailable = topDialects.filter(d => d in compiled);
    
    // Sort top dialects by view count
    const sortedTopDialects = topDialectsAvailable.sort((a, b) => {
        const countA = dialects[a] || 0;
        const countB = dialects[b] || 0;
        if (countB !== countA) {
            return countB - countA;
        }
        return a.localeCompare(b);
    });
    
    // Rebuild tabs container
    const tabsContainer = block.querySelector('.dialect-tabs');
    if (!tabsContainer) return;
    
    // Get current active dialect before rebuilding
    const activeTab = tabsContainer.querySelector('.tab-btn.active');
    const activeDialect = activeTab ? activeTab.getAttribute('data-dialect') : 'asql';
    
    // Clear and rebuild
    tabsContainer.innerHTML = '';
    
    // Add ASQL tab first (always)
    const asqlTab = document.createElement('button');
    asqlTab.className = 'tab-btn';
    asqlTab.setAttribute('data-dialect', 'asql');
    asqlTab.textContent = 'ASQL';
    asqlTab.onclick = () => showDialect(blockId, 'asql');
    if (activeDialect === 'asql') {
        asqlTab.classList.add('active');
    }
    tabsContainer.appendChild(asqlTab);
    
    // Add sorted top dialects
    sortedTopDialects.forEach(dialect => {
        const tab = document.createElement('button');
        tab.className = 'tab-btn';
        tab.setAttribute('data-dialect', dialect);
        tab.textContent = getDialectName(dialect);
        tab.onclick = () => showDialect(blockId, dialect);
        if (activeDialect === dialect) {
            tab.classList.add('active');
        }
        tabsContainer.appendChild(tab);
    });
    
    // Add more tab if there are other dialects
    const otherDialects = Object.keys(compiled).filter(
        d => d !== 'asql' && !topDialects.includes(d)
    );
    if (otherDialects.length > 0) {
        const newMoreTab = document.createElement('button');
        newMoreTab.className = 'tab-btn more-tab';
        newMoreTab.textContent = '⋯';
        newMoreTab.onclick = () => showMoreDialects(blockId);
        tabsContainer.appendChild(newMoreTab);
    }
}
