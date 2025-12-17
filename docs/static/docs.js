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

// Open code block in playground
function openInPlayground(blockId) {
    const block = document.querySelector(`[data-block-id="${blockId}"]`);
    if (!block) return;
    
    // Get compiled SQL
    const compiledB64 = block.getAttribute('data-compiled');
    const compiled = JSON.parse(atob(compiledB64));
    
    // Get current active dialect (or default to asql)
    const activeTab = block.querySelector('.tab-btn.active');
    const currentDialect = activeTab ? activeTab.getAttribute('data-dialect') : 'asql';
    
    // Get the current code (either ASQL or SQL)
    const codeElement = document.getElementById(`code-${blockId}`);
    const currentCode = codeElement ? codeElement.textContent : compiled.get('asql', '');
    
    // Determine from dialect
    const fromDialect = currentDialect === 'asql' ? 'ASQL' : currentDialect;
    
    // Determine to dialect (default to bigquery if ASQL, otherwise keep current)
    const toDialect = currentDialect === 'asql' ? 'bigquery' : currentDialect;
    
    // Encode the query
    const encodedQuery = encodeURIComponent(currentCode);
    
    // Build URL
    const url = `https://play.analyticsql.com?d_f=${fromDialect}&d_t=${toDialect}&sql_f=${encodedQuery}`;
    
    // Open in new tab
    window.open(url, '_blank');
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
        // Determine language based on dialect
        const language = dialect === 'asql' ? 'asql' : 'sql';
        
        // Highlight syntax - ensure highlight.js is available
        if (window.hljs) {
            try {
                // Ensure ASQL language is registered if needed
                if (language === 'asql' && (!window.hljs.getLanguage || !window.hljs.getLanguage('asql'))) {
                    if (window.registerASQLLanguage) {
                        window.registerASQLLanguage();
                    }
                }
                
                // Check if language is available
                const langAvailable = window.hljs.getLanguage && window.hljs.getLanguage(language);
                if (langAvailable) {
                    // Use highlight() directly for more control
                    const result = hljs.highlight(compiled[dialect], { language: language });
                    codeElement.innerHTML = result.value;
                    codeElement.className = `hljs language-${language}`;
                } else {
                    // Fallback: just set text content
                    codeElement.textContent = compiled[dialect];
                    codeElement.className = `language-${language}`;
                }
            } catch (e) {
                console.warn('Highlight.js error:', e);
                // Fallback: just set text content
                codeElement.textContent = compiled[dialect];
                codeElement.className = `language-${language}`;
            }
        } else {
            // Fallback if highlight.js isn't loaded
            codeElement.textContent = compiled[dialect];
            codeElement.className = `language-${language}`;
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
    const topDialects = ['postgres', 'snowflake', 'bigquery', 'databricks'];
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
            // Reorder tabs to include this dialect as visible and active
            reorderTabs(blockId, dialect);
            // Show the dialect content
            showDialect(blockId, dialect);
        };
        menu.appendChild(btn);
    });
    
    // Position menu relative to the more tab
    const moreTab = block.querySelector('.more-tab');
    if (moreTab) {
        const rect = moreTab.getBoundingClientRect();
        const blockRect = block.getBoundingClientRect();
        // Position relative to the code block container
        menu.style.top = `${rect.bottom - blockRect.top}px`;
        menu.style.left = `${rect.left - blockRect.left}px`;
    }
    
    // Toggle menu
    menu.classList.toggle('show');
    
    // Close menu when clicking outside
    if (menu.classList.contains('show')) {
        const closeMenu = (e) => {
            if (!block.contains(e.target)) {
                menu.classList.remove('show');
                document.removeEventListener('click', closeMenu);
            }
        };
        // Use setTimeout to avoid immediate close
        setTimeout(() => {
            document.addEventListener('click', closeMenu);
        }, 0);
    }
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
function reorderTabs(blockId, activeDialect = null) {
    // Rebuild tabs with the active dialect visible
    reorderTabsOnLoad(blockId, activeDialect);
}

// Add WIP warning banner
function addWIPBanner() {
    // Check if banner already exists
    if (document.querySelector('.wip-banner')) return;
    
    // Create banner element
    const banner = document.createElement('div');
    banner.className = 'wip-banner';
    banner.innerHTML = `
        <span class="wip-icon">🚧</span>
        <strong>Work in Progress:</strong> ASQL is under active development. Syntax and features may change. 
        <a href="https://github.com/davefowler/asql" target="_blank">Contribute on GitHub</a>
    `;
    
    // Insert at the very top of the body
    document.body.insertBefore(banner, document.body.firstChild);
}

// Keep CSS variable in sync with banner height (used for sticky sidebar offsets)
function syncBannerHeightVar() {
    const banner = document.querySelector('.wip-banner');
    const height = banner ? Math.ceil(banner.getBoundingClientRect().height) : 0;
    document.documentElement.style.setProperty('--asql-banner-height', `${height}px`);
}

// Keep CSS variable in sync with header height (Material's header height variable isn't always exposed)
function syncHeaderHeightVar() {
    const header = document.querySelector('.md-header');
    const height = header ? Math.ceil(header.getBoundingClientRect().height) : 0;
    document.documentElement.style.setProperty('--asql-header-height', `${height}px`);
}

// Add playground button to header
function addPlaygroundButton() {
    // Check if button already exists
    if (document.querySelector('.playground-btn')) return;
    
    // Find the header inner container and title
    const headerInner = document.querySelector('.md-header__inner');
    const headerTitle = document.querySelector('.md-header__title');
    
    if (!headerInner || !headerTitle) return;
    
    // Create playground button
    const btn = document.createElement('a');
    btn.href = 'https://play.analyticsql.com';
    btn.target = '_blank';
    btn.className = 'playground-btn';
    btn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z"/>
        </svg>
        Playground
    `;
    
    // Insert after the header title within the header inner container
    // This ensures it's in the correct flex container
    if (headerTitle.nextSibling) {
        headerInner.insertBefore(btn, headerTitle.nextSibling);
    } else {
        // If no next sibling, insert right after title
        headerTitle.insertAdjacentElement('afterend', btn);
    }
}

// Highlight all code blocks on the page
function highlightAllCodeBlocks() {
    if (!window.hljs) {
        // Retry if highlight.js isn't loaded yet
        setTimeout(highlightAllCodeBlocks, 100);
        return;
    }
    
    // Ensure ASQL language is registered
    if (!window.hljs.getLanguage || !window.hljs.getLanguage('asql')) {
        // Try to register if function is available
        if (window.registerASQLLanguage) {
            window.registerASQLLanguage();
        }
        // Wait a bit more for registration
        setTimeout(highlightAllCodeBlocks, 50);
        return;
    }
    
    // Highlight code blocks
    document.querySelectorAll('pre code[class*="language-"], pre code:not([class])').forEach((block) => {
        if (block.textContent && block.textContent.trim()) {
            try {
                const code = block.textContent;
                // Determine language from class name
                let language = null;
                const langMatch = block.className.match(/language-(\w+)/);
                if (langMatch) {
                    language = langMatch[1];
                } else {
                    // Check if parent pre has a class
                    const parentPre = block.parentElement;
                    if (parentPre && parentPre.className) {
                        const parentLangMatch = parentPre.className.match(/language-(\w+)/);
                        if (parentLangMatch) {
                            language = parentLangMatch[1];
                        }
                    }
                }
                
                // Default to sql if no language detected
                if (!language) {
                    language = 'sql';
                }
                
                // Only highlight if not already highlighted
                if (!block.classList.contains('hljs')) {
                    const langAvailable = window.hljs.getLanguage && window.hljs.getLanguage(language);
                    if (langAvailable) {
                        const result = hljs.highlight(code, { language: language });
                        block.innerHTML = result.value;
                        block.classList.add('hljs', `language-${language}`);
                    } else {
                        block.classList.add(`language-${language}`);
                    }
                }
            } catch (e) {
                console.warn('Highlight.js error on block:', e);
            }
        }
    });
    
    // Also handle ASQL dialect blocks
    const blocks = document.querySelectorAll('.asql-code-block');
    blocks.forEach(block => {
        const blockId = block.getAttribute('data-block-id');
        reorderTabsOnLoad(blockId);
        showDialect(blockId, 'asql');
    });
}

// Initialize all code blocks on page load
document.addEventListener('DOMContentLoaded', () => {
    // Add WIP warning banner
    addWIPBanner();
    // Sync banner height CSS variable (and keep it updated on resize)
    syncBannerHeightVar();
    syncHeaderHeightVar();
    window.addEventListener('resize', syncBannerHeightVar);
    window.addEventListener('resize', syncHeaderHeightVar);
    // Add playground button to header
    addPlaygroundButton();
    // Wait a bit for highlight.js and ASQL language to be fully loaded
    const initHighlighting = () => {
        if (!window.hljs) {
            // Retry if highlight.js isn't loaded yet
            setTimeout(initHighlighting, 100);
            return;
        }
        
        // Ensure ASQL language is registered
        if (!window.hljs.getLanguage || !window.hljs.getLanguage('asql')) {
            // Try to register if function is available
            if (window.registerASQLLanguage) {
                window.registerASQLLanguage();
            }
            // Wait a bit more for registration
            setTimeout(initHighlighting, 50);
            return;
        }
        
        // First, highlight any existing code blocks (from server-side HTML)
        // This includes both standalone code blocks and code blocks in tabs
        document.querySelectorAll('pre code[class*="language-"], pre code:not([class])').forEach((block) => {
            if (block.textContent && block.textContent.trim()) {
                try {
                    const code = block.textContent;
                    // Determine language from class name, or try to detect from parent
                    let language = null;
                    const langMatch = block.className.match(/language-(\w+)/);
                    if (langMatch) {
                        language = langMatch[1];
                    } else {
                        // Check if parent pre has a class
                        const parentPre = block.parentElement;
                        if (parentPre && parentPre.className) {
                            const parentLangMatch = parentPre.className.match(/language-(\w+)/);
                            if (parentLangMatch) {
                                language = parentLangMatch[1];
                            }
                        }
                    }
                    
                    // Default to sql if no language detected
                    if (!language) {
                        language = 'sql';
                    }
                    
                    // Only highlight if not already highlighted (check for hljs class)
                    if (!block.classList.contains('hljs')) {
                        // Check if language is available
                        const langAvailable = window.hljs.getLanguage && window.hljs.getLanguage(language);
                        if (langAvailable) {
                            const result = hljs.highlight(code, { language: language });
                            block.innerHTML = result.value;
                            // Add classes without removing existing ones
                            block.classList.add('hljs', `language-${language}`);
                        } else {
                            // Fallback: just add language class
                            block.classList.add(`language-${language}`);
                        }
                    }
                } catch (e) {
                    console.warn('Highlight.js error on initial block:', e);
                    // Ensure it still has the background even if highlighting fails
                    if (!block.classList.contains('hljs')) {
                        block.className = block.className || 'language-sql';
                    }
                }
            }
        });
        
        const blocks = document.querySelectorAll('.asql-code-block');
        
        blocks.forEach(block => {
            const blockId = block.getAttribute('data-block-id');
            
            // Reorder tabs based on view counts
            reorderTabsOnLoad(blockId);
            
            // Always default to ASQL
            showDialect(blockId, 'asql');
        });
    };
    
    // Start initialization
    initHighlighting();
    
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
function reorderTabsOnLoad(blockId, forceActiveDialect = null) {
    const block = document.querySelector(`[data-block-id="${blockId}"]`);
    if (!block) return;
    
    const compiledB64 = block.getAttribute('data-compiled');
    const compiled = JSON.parse(atob(compiledB64));
    
    const { dialects } = initDialectTracking();
    const topDialects = ['postgres', 'snowflake', 'bigquery', 'databricks'];
    let topDialectsAvailable = topDialects.filter(d => d in compiled);
    
    // Sort top dialects by view count
    topDialectsAvailable = topDialectsAvailable.sort((a, b) => {
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
    let activeDialect = forceActiveDialect || (activeTab ? activeTab.getAttribute('data-dialect') : 'asql');
    
    // If active dialect is not in top dialects (and not asql), add it to the visible tabs
    const dialectsToShow = [...topDialectsAvailable];
    if (activeDialect !== 'asql' && !topDialects.includes(activeDialect) && activeDialect in compiled) {
        // Add the active dialect to the beginning of visible dialects
        dialectsToShow.unshift(activeDialect);
        // Limit to 4 visible SQL dialects (plus ASQL)
        if (dialectsToShow.length > 4) {
            dialectsToShow.pop();
        }
    }
    
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
    
    // Add visible dialects
    dialectsToShow.forEach(dialect => {
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
    
    // Add more tab if there are other dialects not shown
    const shownDialects = new Set(['asql', ...dialectsToShow]);
    const otherDialects = Object.keys(compiled).filter(d => !shownDialects.has(d));
    if (otherDialects.length > 0) {
        const newMoreTab = document.createElement('button');
        newMoreTab.className = 'tab-btn more-tab';
        newMoreTab.textContent = '⋯';
        newMoreTab.onclick = () => showMoreDialects(blockId);
        tabsContainer.appendChild(newMoreTab);
    }
}
