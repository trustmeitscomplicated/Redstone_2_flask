// ==============================================================================
// dashboard.js - Frontend Application Logic
// ==============================================================================
// This file contains all the JavaScript code that runs in the user's browser.
// It's responsible for:
// 1. Fetching data from our Python backend API.
// 2. Dynamically building and updating the HTML to display the data.
// 3. Handling all user interactions like button clicks, form inputs, and sorting.
// 4. Managing the application's state (e.g., current filters, sort order).
// ==============================================================================

// This event listener ensures that our code only runs after the entire HTML
// page has been loaded and is ready.
document.addEventListener('DOMContentLoaded', () => {
    
    // --- 1. Configuration ---
    // These are constant values that control some application behaviors.
    const ITEMS_PER_PAGE = 25; // Number of items to show in the "All Protocols" table per page.
    const DEFAULT_CATEGORIES = ['lending', 'dexes', 'bridge', 'liquid staking', 'cdp', 'yield', 'services', 'yield aggregator', 'derivatives', 'rwa'];

    // --- 2. Application State ---
    // This object holds all the data that can change during the user's session.
    // It's a single source of truth for our application's data.
    const State = {
        snapshots: [], // List of available data files (snapshots).
        reportData: null, // The main report data received from the API.
        allProtocols: [], // A complete list of all protocols from the current report.
        filteredProtocols: [], // A filtered/sorted version of the list above.
        categories: new Set(), // A unique set of all available protocol categories.
        // A set of currently active category filters, loaded from browser's localStorage.
        activeFilters: new Set(JSON.parse(localStorage.getItem('defillama_filters')) || DEFAULT_CATEGORIES),
        currentPage: 1, // The current page number for the "All Protocols" table.
        sort: { key: 'tvl', order: 'desc' } // The current sorting criteria for the table.
    };

    // --- 3. DOM Element References ---
    // We get references to all important HTML elements once and store them here for easy access.
    // The `$` functions are simple shortcuts for `document.querySelector`.
    const $ = (selector) => document.querySelector(selector);
    const $$ = (selector) => document.querySelectorAll(selector);

    const Elements = {
        loader: $('#loader'),
        appContent: $('#app-content'),
        themeBtn: $('#themeBtn'),
        sunIcon: $('#sunIcon'),
        moonIcon: $('#moonIcon'),
        syncBtn: $('#syncBtn'),
        compareBtn: $('#compareBtn'),
        startDateSelect: $('#startDate'),
        endDateSelect: $('#endDate'),
        minTvlInput: $('#min-tvl'),
        maxTvlInput: $('#max-tvl'),
        topNSelect: $('#top-n'),
        reportDates: $('#reportDates'),
        statsKpi: $('#stats-kpi'),
        increasesPctList: $('#increases-pct-list'),
        increasesAbsList: $('#increases-abs-list'),
        newProtocolsList: $('#new-protocols-list'),
        removedProtocolsList: $('#removed-protocols-list'),
        searchInput: $('#searchInput'),
        allProtocolsTableBody: $('#all-protocols-table-body'),
        paginationControls: $('#pagination-controls'),
        categoryFilters: $('#category-filters'),
        toast: $('#toast'),
        tabButtons: $$('.tab-btn'),
        tabPanels: $$('.tab-panel'),
        syncIcon: $('#syncIcon'),
    };

    // --- 4. API Module ---
    // This object centralizes all communication with our Python backend.
    const API = {
        async get(url) {
            try {
                const response = await fetch(url);
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: `Server Error: ${response.status}` }));
                    throw new Error(errorData.error);
                }
                return response.json();
            } catch (error) {
                UI.showToast(error.message, 'error');
                throw error;
            }
        },
        async post(url) {
            try {
                UI.setSyncing(true);
                const response = await fetch(url, { method: 'POST' });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ message: `Server Error: ${response.status}` }));
                    throw new Error(errorData.message);
                }
                const data = await response.json();
                UI.showToast(data.message, 'success');
                return data;
            } catch (error) {
                UI.showToast(error.message, 'error');
                throw error;
            } finally {
                UI.setSyncing(false);
            }
        }
    };

    // --- 5. UI Module ---
    // This object contains all functions that manipulate the HTML page (the DOM).
    const UI = {
        initTheme() {
            const storedTheme = localStorage.getItem('theme');
            // Default to dark theme if no preference is stored.
            const theme = storedTheme || 'dark';
            this.applyTheme(theme);

            Elements.themeBtn.addEventListener('click', () => {
                const newTheme = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
                localStorage.setItem('theme', newTheme);
                this.applyTheme(newTheme);
            });
        },
        applyTheme(theme) {
            // Add or remove the 'dark' class on the main <html> element.
            document.documentElement.classList.toggle('dark', theme === 'dark');
            // Show the correct icon (sun or moon).
            Elements.sunIcon.classList.toggle('hidden', theme === 'dark');
            Elements.moonIcon.classList.toggle('hidden', theme !== 'dark');
        },
        setLoading(isLoading) {
            Elements.loader.classList.toggle('hidden', !isLoading);
            Elements.appContent.classList.toggle('hidden', isLoading);
        },
        setSyncing(isSyncing) {
            Elements.syncBtn.disabled = isSyncing;
            Elements.syncIcon.classList.toggle('animate-spin', isSyncing);
        },
        showToast(message, type = 'success') {
            const colors = {
                success: 'bg-emerald-100 dark:bg-emerald-900 text-emerald-700 dark:text-emerald-200 border-emerald-400',
                error: 'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 border-red-400'
            };
            Elements.toast.innerHTML = `<div class="p-3 rounded-lg border ${colors[type]}">${message}</div>`;
            Elements.toast.classList.remove('translate-y-20', 'opacity-0');
            setTimeout(() => {
                Elements.toast.classList.add('translate-y-20', 'opacity-0');
            }, 4000);
        },
        renderSnapshotsSelect(snapshots) {
            if (!snapshots || snapshots.length === 0) return;
            [Elements.startDateSelect, Elements.endDateSelect].forEach(select => {
                select.innerHTML = snapshots.map(s => `<option value="${s.filename}">${new Date(s.date).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</option>`).join('');
            });
            Elements.endDateSelect.selectedIndex = 0;
            Elements.startDateSelect.selectedIndex = Math.min(7, snapshots.length - 1);
        },
        renderGlobalStats(stats) {
            const formatUsd = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD', notation: 'compact' });
            const formatPercent = (n) => `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
            const changeColor = stats.change24h >= 0 ? 'text-emerald-500' : 'text-red-500';
            Elements.statsKpi.innerHTML = `
                <div class="fade-in glass-panel p-4 rounded-2xl shadow-lg"><p class="text-sm text-gray-500 dark:text-gray-400">Total TVL</p><p class="text-2xl font-bold">${formatUsd(stats.totalTVL)}</p></div>
                <div class="fade-in glass-panel p-4 rounded-2xl shadow-lg"><p class="text-sm text-gray-500 dark:text-gray-400">24h Change</p><p class="text-2xl font-bold ${changeColor}">${formatPercent(stats.change24h)}</p></div>
                <div class="fade-in glass-panel p-4 rounded-2xl shadow-lg"><p class="text-sm text-gray-500 dark:text-gray-400">Tracked Protocols</p><p class="text-2xl font-bold">${stats.protocolCount.toLocaleString('en-US')}</p></div>
            `;
        },
        renderReport(data) {
            const { reportMetadata, topIncreasesPct, topIncreasesAbs, newProtocols, removedProtocols } = data;
            Elements.reportDates.textContent = `Comparing from ${new Date(reportMetadata.comparisonDate).toLocaleDateString('en-GB')} to ${new Date(reportMetadata.reportDate).toLocaleDateString('en-GB')}`;
            
            const createItem = (item, type) => {
                const formatUsd = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD', notation: 'compact', signDisplay: 'always' });
                const formatTotalUsd = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD', notation: 'compact' });
                const formatPercent = (n) => `${n > 0 ? '+' : ''}${n.toFixed(1)}%`;
                
                let changeHtml;
                if (type === 'pct') changeHtml = `<div class="font-bold text-sky-600 dark:text-sky-400">${formatPercent(item.pct)}</div><div class="text-xs font-mono text-gray-500">${formatUsd(item.diff)}</div>`;
                else if (type === 'abs') changeHtml = `<div class="font-bold text-emerald-600 dark:text-emerald-400">${formatUsd(item.diff)}</div><div class="text-xs font-mono text-gray-500">${formatPercent(item.pct)}</div>`;
                else if (type === 'new') changeHtml = `<div class="font-bold text-amber-600 dark:text-amber-400">${formatTotalUsd(item.tvl)}</div>`;
                else if (type === 'removed') changeHtml = `<div class="font-bold text-red-600 dark:text-red-400">${formatTotalUsd(item.tvl)}</div>`;

                return `<a href="https://defillama.com/protocol/${item.slug}" target="_blank" rel="noopener noreferrer" class="p-3 rounded-lg bg-gray-50/50 dark:bg-gray-700/30 flex items-center gap-3 transition-all duration-200 hover:scale-[1.03] hover:shadow-xl hover:bg-white dark:hover:bg-gray-700">
                    <img src="${item.logo}" class="w-8 h-8 rounded-full bg-white p-0.5" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                    <div class="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-600 flex-shrink-0 items-center justify-center font-bold text-gray-500" style="display: none;">${item.name ? item.name.charAt(0) : '?'}</div>
                    <div class="flex-1 min-w-0"><div class="font-semibold truncate">${item.name}</div><div class="text-xs text-gray-500 truncate">${item.category}</div></div>
                    <div class="text-right font-mono text-sm">${changeHtml}</div>
                </a>`;
            };
            
            const renderList = (element, list, type) => {
                element.innerHTML = list.length > 0 ? list.map(item => createItem(item, type)).join('') : `<p class="text-center text-sm text-gray-500 p-4">No data for selected criteria.</p>`;
            };

            renderList(Elements.increasesPctList, topIncreasesPct, 'pct');
            renderList(Elements.increasesAbsList, topIncreasesAbs, 'abs');
            renderList(Elements.newProtocolsList, newProtocols, 'new');
            renderList(Elements.removedProtocolsList, removedProtocols, 'removed');
        },
        renderAllProtocols() {
            const { filteredProtocols, currentPage } = State;
            const start = (currentPage - 1) * ITEMS_PER_PAGE;
            const end = start + ITEMS_PER_PAGE;
            const pageItems = filteredProtocols.slice(start, end);

            const formatUsd = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD', notation: 'compact' });
            const formatPercent = (n) => n ? `${n > 0 ? '+' : ''}${n.toFixed(2)}%` : 'N/A';
            const formatDiff = (n) => n ? n.toLocaleString('en-US', { style: 'currency', currency: 'USD', notation: 'compact', signDisplay: 'always' }) : 'N/A';

            Elements.allProtocolsTableBody.innerHTML = pageItems.map(p => `
                <tr class="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors duration-200">
                    <td class="px-6 py-4 whitespace-nowrap"><div class="flex items-center gap-3"><img src="${p.logo}" class="w-6 h-6 rounded-full" onerror="this.style.display='none'"><div class="font-medium">${p.name}</div></div></td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">${p.category}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right font-mono text-sm">${formatUsd(p.tvl)}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right font-mono text-sm ${p.diff > 0 ? 'text-emerald-500' : 'text-red-500'}">${formatDiff(p.diff)}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-right font-mono text-sm ${p.pct > 0 ? 'text-emerald-500' : 'text-red-500'}">${formatPercent(p.pct)}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-center">
                        <div class="flex items-center justify-center gap-3">
                            <a href="${p.url}" target="_blank" rel="noopener noreferrer" title="Official Website" class="text-gray-400 hover:text-emerald-500 transition-colors">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                            </a>
                            <a href="https://defillama.com/protocol/${p.slug}" target="_blank" rel="noopener noreferrer" title="View on DeFiLlama" class="text-gray-400 hover:text-emerald-500 transition-colors">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" /><path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" /></svg>
                            </a>
                        </div>
                    </td>
                </tr>
            `).join('');
        },
        renderPagination() {
            const totalPages = Math.ceil(State.filteredProtocols.length / ITEMS_PER_PAGE);
            if (totalPages <= 1) {
                Elements.paginationControls.innerHTML = ''; return;
            }
            const { currentPage } = State;
            let html = `<div class="flex-1 flex justify-between sm:hidden">
                <button ${currentPage === 1 ? 'disabled' : ''} data-page="${currentPage - 1}" class="page-btn relative inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50">Previous</button>
                <button ${currentPage === totalPages ? 'disabled' : ''} data-page="${currentPage + 1}" class="page-btn relative inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50">Next</button>
            </div>
            <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                <div><p class="text-sm text-gray-700 dark:text-gray-400">Showing <span class="font-medium">${(currentPage - 1) * ITEMS_PER_PAGE + 1}</span> to <span class="font-medium">${Math.min(currentPage * ITEMS_PER_PAGE, State.filteredProtocols.length)}</span> of <span class="font-medium">${State.filteredProtocols.length}</span> results</p></div>
                <div><nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">`;
            
            const pages = Array.from({length: totalPages}, (_, i) => i + 1);
            const visiblePages = pages.filter(p => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1);
            
            let lastPage = 0;
            visiblePages.forEach(p => {
                if(lastPage !== 0 && p > lastPage + 1) {
                    html += `<span class="relative inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm font-medium text-gray-700 dark:text-gray-400">...</span>`;
                }
                html += `<button data-page="${p}" class="page-btn ${p === currentPage ? 'z-10 bg-emerald-50 border-emerald-500 text-emerald-600' : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700'} relative inline-flex items-center px-4 py-2 border text-sm font-medium">${p}</button>`;
                lastPage = p;
            });
            html += `</nav></div></div>`;
            Elements.paginationControls.innerHTML = html;
        },
        renderCategoryFilters() {
            Elements.categoryFilters.innerHTML = [...State.categories].sort().map(cat => `
                <label class="flex items-center space-x-3 cursor-pointer">
                    <input type="checkbox" data-category="${cat}" class="form-checkbox h-5 w-5 rounded text-emerald-600 bg-gray-200 dark:bg-gray-600 border-gray-300 dark:border-gray-500 focus:ring-emerald-500" ${State.activeFilters.has(cat) ? 'checked' : ''}>
                    <span class="text-gray-700 dark:text-gray-300 capitalize">${cat}</span>
                </label>
            `).join('');
        },
        updateSortUI() {
            $$('.sortable').forEach(th => {
                th.classList.remove('sort-asc', 'sort-desc');
                if (th.dataset.sort === State.sort.key) {
                    th.classList.add(State.sort.order === 'asc' ? 'sort-asc' : 'sort-desc');
                }
            });
        }
    };

    // --- 6. Main Application Logic ---
    // This object orchestrates the entire application flow.
    const App = {
        async init() {
            UI.initTheme();
            UI.setLoading(true);
            this.bindEvents();
            
            try {
                const snapshots = await API.get('/api/snapshots');
                State.snapshots = snapshots;
                UI.renderSnapshotsSelect(snapshots);

                if (snapshots.length > 0) {
                    await this.loadStats();
                    await this.loadReport();
                } else {
                    UI.showToast("No data found. Click 'Sync' to download.", 'error');
                }
            } catch (e) {
                console.error("Initialization failed", e);
            } finally {
                UI.setLoading(false);
            }
        },
        bindEvents() {
            Elements.syncBtn.addEventListener('click', () => this.syncData());
            Elements.compareBtn.addEventListener('click', () => this.loadReport());
            Elements.searchInput.addEventListener('input', (e) => this.filterProtocols(e.target.value));
            
            Elements.tabButtons.forEach(btn => btn.addEventListener('click', (e) => this.switchTab(e.currentTarget.dataset.tab)));

            Elements.paginationControls.addEventListener('click', (e) => {
                const pageBtn = e.target.closest('.page-btn');
                if (pageBtn && pageBtn.dataset.page) {
                    State.currentPage = parseInt(pageBtn.dataset.page);
                    UI.renderAllProtocols();
                    UI.renderPagination();
                }
            });

            Elements.categoryFilters.addEventListener('change', (e) => {
                if(e.target.matches('input[type="checkbox"]')) {
                    this.updateCategoryFilter(e.target.dataset.category, e.target.checked);
                }
            });
            
            $$('.sortable').forEach(th => th.addEventListener('click', (e) => {
                this.sortProtocols(e.currentTarget.dataset.sort);
            }));
        },
        async syncData() {
            await API.post('/api/sync');
            const snapshots = await API.get('/api/snapshots');
            State.snapshots = snapshots;
            UI.renderSnapshotsSelect(snapshots);
            await this.loadStats();
            await this.loadReport();
        },
        async loadStats() {
            const stats = await API.get('/api/stats');
            UI.renderGlobalStats(stats);
        },
        async loadReport() {
            Elements.compareBtn.disabled = true;
            Elements.compareBtn.textContent = 'Generating...';
            try {
                const params = new URLSearchParams({
                    start_file: Elements.startDateSelect.value,
                    end_file: Elements.endDateSelect.value,
                    min_tvl: Elements.minTvlInput.value || '0',
                    top_n: Elements.topNSelect.value
                });
                if(Elements.maxTvlInput.value) {
                    params.append('max_tvl', Elements.maxTvlInput.value);
                }

                const data = await API.get(`/api/report?${params.toString()}`);
                if(!data) return;

                State.reportData = data;
                State.allProtocols = data.allProtocols;
                
                data.allProtocols.forEach(p => {
                    if(p.category) State.categories.add(p.category.toLowerCase())
                });
                
                this.applyAllFilters();
                UI.renderReport(data);
                UI.renderCategoryFilters();
            } finally {
                Elements.compareBtn.disabled = false;
                Elements.compareBtn.textContent = 'Generate Report';
            }
        },
        switchTab(tabId) {
            Elements.tabButtons.forEach(btn => btn.classList.toggle('tab-active', btn.dataset.tab === tabId));
            Elements.tabPanels.forEach(panel => panel.classList.toggle('hidden', panel.id !== `tab-panel-${tabId}`));
        },
        updateCategoryFilter(category, isChecked) {
            isChecked ? State.activeFilters.add(category) : State.activeFilters.delete(category);
            localStorage.setItem('defillama_filters', JSON.stringify([...State.activeFilters]));
            this.applyAllFilters();
        },
        filterProtocols(searchTerm) {
            this.applyAllFilters(searchTerm);
        },
        sortProtocols(key) {
            if (State.sort.key === key) {
                State.sort.order = State.sort.order === 'asc' ? 'desc' : 'asc';
            } else {
                State.sort.key = key;
                State.sort.order = 'desc';
            }
            this.applyAllFilters();
            UI.updateSortUI();
        },
        applyAllFilters(searchTerm = Elements.searchInput.value.toLowerCase()) {
            if (!State.allProtocols) return;

            State.filteredProtocols = State.allProtocols
                .filter(p => p.category && State.activeFilters.has(p.category.toLowerCase()))
                .filter(p => p.name && p.name.toLowerCase().includes(searchTerm));
            
            const { key, order } = State.sort;
            State.filteredProtocols.sort((a, b) => {
                let valA = a[key] ?? -Infinity;
                let valB = b[key] ?? -Infinity;
                if (typeof valA === 'string') {
                    return order === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
                }
                return order === 'asc' ? valA - valB : valB - valA;
            });

            State.currentPage = 1;
            UI.renderAllProtocols();
            UI.renderPagination();
        }
    };

    // Start the application!
    App.init();
});
