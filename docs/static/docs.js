// ASQL Documentation JavaScript - Dialect Tabs

const ASQL_TO_DIALECT_STORAGE_KEY = 'asql_to_dialect';
const ASQL_TO_DIALECT_LEGACY_STORAGE_KEY = 'asql_preferred_dialect';
const ASQL_DEFAULT_TO_DIALECT = 'postgres';

function getPlaygroundBaseUrl() {
    const fromWindow =
        (typeof window !== 'undefined' && window.__ASQL_PLAYGROUND_URL__)
            ? String(window.__ASQL_PLAYGROUND_URL__)
            : 'https://play.analyticsql.com';
    return fromWindow.replace(/\/+$/, '');
}

function getGlobalToDialect() {
    const stored = localStorage.getItem(ASQL_TO_DIALECT_STORAGE_KEY);
    if (stored) return stored;
    const legacy = localStorage.getItem(ASQL_TO_DIALECT_LEGACY_STORAGE_KEY);
    if (legacy) return legacy;
    return ASQL_DEFAULT_TO_DIALECT;
}

function setGlobalToDialect(dialect, shouldDispatch = true) {
    localStorage.setItem(ASQL_TO_DIALECT_STORAGE_KEY, dialect);
    // keep legacy key for backward compatibility
    localStorage.setItem(ASQL_TO_DIALECT_LEGACY_STORAGE_KEY, dialect);

    if (shouldDispatch) {
        window.dispatchEvent(new CustomEvent('asql:to-dialect-changed', { detail: { dialect } }));
    }
}

function getCompiledFromBlock(block) {
    const compiledB64 = block.getAttribute('data-compiled');
    if (!compiledB64) return null;
    return JSON.parse(atob(compiledB64));
}

function highlightIntoCodeElement(codeElement, code, language) {
    if (!codeElement) return;

    // Don't overwrite if already highlighted (unless code content changed)
    const currentText = codeElement.textContent || codeElement.innerText || '';
    if (codeElement.classList.contains('hljs') && currentText.trim() === code.trim()) {
        // Already highlighted with same content, don't overwrite
        return;
    }

    if (window.hljs) {
        try {
            if (language === 'asql' && (!window.hljs.getLanguage || !window.hljs.getLanguage('asql'))) {
                if (window.registerASQLLanguage) {
                    window.registerASQLLanguage();
                }
            }

            const langAvailable = window.hljs.getLanguage && window.hljs.getLanguage(language);
            if (langAvailable) {
                const result = hljs.highlight(code, { language, ignoreIllegals: true });
                codeElement.innerHTML = result.value;
                codeElement.className = `hljs language-${language}`;
                return;
            }
        } catch (e) {
            console.warn('Highlight.js error:', e);
        }
    }

    // Fallback if highlight.js isn't available or failed - but preserve existing highlighting if present
    if (!codeElement.classList.contains('hljs')) {
        codeElement.textContent = code;
        codeElement.className = `language-${language}`;
    }
}

function updateMiniPlaygroundBlock(block, toDialect) {
    const blockId = block.getAttribute('data-block-id');
    if (!blockId) return;

    const compiled = getCompiledFromBlock(block);
    if (!compiled) return;

    const select = block.querySelector('.asql-mp-to-select');
    if (select) {
        // If this dialect isn't available in this block, fall back to default.
        const hasOption = !!select.querySelector(`option[value="${CSS.escape(toDialect)}"]`);
        const nextDialect = hasOption ? toDialect : ASQL_DEFAULT_TO_DIALECT;
        if (select.value !== nextDialect) {
            select.value = nextDialect;
        }
        toDialect = nextDialect;
    }

    const asqlElement = document.getElementById(`asql-${blockId}`);
    const toElement = document.getElementById(`to-${blockId}`);

    // Only update if hljs is ready and language is available
    if (asqlElement && window.hljs) {
        const asqlCode = compiled.asql || asqlElement.textContent || '';
        // Check if ASQL language is available before highlighting
        if (window.hljs.getLanguage && window.hljs.getLanguage('asql')) {
            highlightIntoCodeElement(asqlElement, asqlCode, 'asql');
        } else if (window.registerASQLLanguage) {
            // Try to register and highlight
            window.registerASQLLanguage();
            setTimeout(() => {
                highlightIntoCodeElement(asqlElement, asqlCode, 'asql');
            }, 50);
        }
    }

    if (toElement && window.hljs) {
        const sqlCode = compiled[toDialect] || compiled[ASQL_DEFAULT_TO_DIALECT] || '';
        highlightIntoCodeElement(toElement, sqlCode, 'sql');
    }
}

function initMiniPlaygrounds() {
    const blocks = document.querySelectorAll('.asql-mini-playground');
    const globalDialect = getGlobalToDialect();

    blocks.forEach((block) => {
        if (block.getAttribute('data-asql-mp-initialized') === '1') {
            updateMiniPlaygroundBlock(block, globalDialect);
            return;
        }

        const select = block.querySelector('.asql-mp-to-select');
        if (select) {
            select.addEventListener('change', (e) => {
                const nextDialect = e.target.value;
                setGlobalToDialect(nextDialect, true);
            });
        }

        block.setAttribute('data-asql-mp-initialized', '1');
        updateMiniPlaygroundBlock(block, globalDialect);
    });
}

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

    // Mini playground: always open from ASQL to selected dialect
    const toSelect = block.querySelector('.asql-mp-to-select');
    if (toSelect) {
        const toDialect = toSelect.value || getGlobalToDialect();
        const encodedQuery = encodeURIComponent(compiled.asql || '');
        const url = `${getPlaygroundBaseUrl()}?d_f=ASQL&d_t=${toDialect}&sql_f=${encodedQuery}`;
        window.open(url, '_blank');
        return;
    }
    
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
    const url = `${getPlaygroundBaseUrl()}?d_f=${fromDialect}&d_t=${toDialect}&sql_f=${encodedQuery}`;
    
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
                    const result = hljs.highlight(compiled[dialect], { language: language, ignoreIllegals: true });
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
        'tsql': 'SQL Server',
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

// Make header title clickable
function makeHeaderTitleClickable() {
    // Make the header title text clickable (not just the icon)
    const headerTitle = document.querySelector('.md-header__title');
    const headerTopic = document.querySelector('.md-header__topic');
    
    // Function to make an element clickable
    const makeClickable = (element) => {
        if (!element) return;
        
        // Add click handler that navigates to home
        // Only navigate if not clicking on an existing link
        element.addEventListener('click', (e) => {
            // Don't navigate if clicking on an existing link (like the icon)
            if (e.target.closest('a')) {
                return;
            }
            // Navigate to home
            window.location.href = '/';
        });
    };
    
    makeClickable(headerTitle);
    makeClickable(headerTopic);
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
    btn.href = getPlaygroundBaseUrl();
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
    
    // Highlight code blocks (including those in mini-playgrounds)
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
                
                // Ensure ASQL language is registered before highlighting
                if (language === 'asql' && (!window.hljs.getLanguage || !window.hljs.getLanguage('asql'))) {
                    if (window.registerASQLLanguage) {
                        window.registerASQLLanguage();
                    }
                }
                
                // Only highlight if not already highlighted
                if (!block.classList.contains('hljs')) {
                    const langAvailable = window.hljs.getLanguage && window.hljs.getLanguage(language);
                    if (langAvailable) {
                        const result = hljs.highlight(code, { language: language, ignoreIllegals: true });
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
    
    // Also handle ASQL blocks
    const blocks = document.querySelectorAll('.asql-code-block');
    blocks.forEach(block => {
        const blockId = block.getAttribute('data-block-id');
        if (!blockId) return;
        if (block.classList.contains('asql-mini-playground')) return;
        reorderTabsOnLoad(blockId);
        showDialect(blockId, 'asql');
    });

    // Initialize split-pane mini playgrounds (after highlighting is done)
    // This ensures highlighting isn't overwritten
    setTimeout(() => {
        initMiniPlaygrounds();
    }, 100);
}

function initDocsPage() {
    // Add WIP warning banner
    addWIPBanner();

    // Sync banner/header height vars (used for sticky sidebar offsets)
    syncBannerHeightVar();
    syncHeaderHeightVar();

    // Make header title clickable
    makeHeaderTitleClickable();

    // Add playground button to header
    addPlaygroundButton();

    // Attach global listeners once (instant navigation re-runs init)
    if (!window.__asql_docs_global_listeners_attached) {
        window.__asql_docs_global_listeners_attached = true;
        window.addEventListener('resize', syncBannerHeightVar);
        window.addEventListener('resize', syncHeaderHeightVar);

        // Close more dialects menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.more-tab') && !e.target.closest('.more-dialects-menu')) {
                document.querySelectorAll('.more-dialects-menu').forEach(menu => {
                    menu.classList.remove('show');
                });
            }
        });
    }

    // Wait a bit for highlight.js and ASQL language to be fully loaded
    const initHighlighting = () => {
        if (!window.hljs) {
            setTimeout(initHighlighting, 100);
            return;
        }

        if (!window.hljs.getLanguage || !window.hljs.getLanguage('asql')) {
            if (window.registerASQLLanguage) {
                window.registerASQLLanguage();
            }
            setTimeout(initHighlighting, 50);
            return;
        }

        // Use the dedicated highlightAllCodeBlocks function which handles all cases
        highlightAllCodeBlocks();
    };
    
    initHighlighting();
}

function subscribeToInstantNavigation() {
    if (window.__asql_docs_instant_subscribed) return;
    if (!window.document$ || typeof window.document$.subscribe !== 'function') {
        // Material may attach document$ after our script runs
        if (!window.__asql_docs_instant_retry_scheduled) {
            window.__asql_docs_instant_retry_scheduled = true;
            setTimeout(() => {
                window.__asql_docs_instant_retry_scheduled = false;
                subscribeToInstantNavigation();
            }, 250);
        }
        return;
    }
    window.__asql_docs_instant_subscribed = true;
    window.document$.subscribe(() => {
        initDocsPage();
    });
}

// Initialize on first load
document.addEventListener('DOMContentLoaded', () => {
    initDocsPage();
    subscribeToInstantNavigation();
});

// Keep all mini-playground dropdowns in sync
window.addEventListener('asql:to-dialect-changed', (e) => {
    const dialect = e && e.detail ? e.detail.dialect : getGlobalToDialect();
    document.querySelectorAll('.asql-mini-playground').forEach((block) => {
        updateMiniPlaygroundBlock(block, dialect);
    });
});

// Cross-tab / cross-window sync
window.addEventListener('storage', (e) => {
    if (!e) return;
    if (e.key !== ASQL_TO_DIALECT_STORAGE_KEY && e.key !== ASQL_TO_DIALECT_LEGACY_STORAGE_KEY) return;
    const nextDialect = getGlobalToDialect();
    document.querySelectorAll('.asql-mini-playground').forEach((block) => {
        updateMiniPlaygroundBlock(block, nextDialect);
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
