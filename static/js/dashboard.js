document.addEventListener('DOMContentLoaded', () => {
  // --- Elementy DOM ---
  const themeBtn = document.getElementById('themeBtn');
  const sunIcon = document.getElementById('sunIcon');
  const moonIcon = document.getElementById('moonIcon');
  const compareBtn = document.getElementById('compareBtn');
  
  const reportContent = document.getElementById('reportContent');
  const loader = document.getElementById('loader');
  const errorMessage = document.getElementById('errorMessage');
  const errorText = document.getElementById('errorText');
  
  const increasesPctList = document.getElementById('increases-pct-list');
  const increasesAbsList = document.getElementById('increases-abs-list');
  const newProtocolsList = document.getElementById('new-protocols-list');
  
  const reportDates = document.getElementById('reportDates');
  const startDateSelect = document.getElementById('startDate');
  const endDateSelect = document.getElementById('endDate');

  // --- Zarządzanie motywem ---
  const applyTheme = (theme) => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    sunIcon.classList.toggle('hidden', theme !== 'dark');
    moonIcon.classList.toggle('hidden', theme === 'dark');
  };
  const toggleTheme = () => {
    const newTheme = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
    localStorage.setItem('theme', newTheme);
    applyTheme(newTheme);
  };
  themeBtn.addEventListener('click', toggleTheme);
  applyTheme(localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

  // --- Funkcje pomocnicze ---
  const formatUsd = (n) => {
    const sign = n < 0 ? '-' : '+';
    n = Math.abs(n);
    if (n >= 1e9) return `${sign}${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `${sign}${(n / 1e6).toFixed(2)}M`;
    if (n >= 1e3) return `${sign}${(n / 1e3).toFixed(1)}K`;
    return `${sign}$${n.toFixed(0)}`;
  };
  
  const formatTotalUsd = (n) => {
    if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    return `$${n.toFixed(0)}`;
  };

  const formatDate = (isoString) => {
    return new Date(isoString).toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' });
  };

  // --- Tworzenie elementów raportu ---
  const createChangeItem = (item, type) => {
    const isIncrease = type !== 'new';
    const link = `https://defillama.com/protocol/${item.slug}`;
    
    let changeHtml = '';
    if (type === 'pct') {
      changeHtml = `<div class="font-bold text-sky-600 dark:text-sky-400">${item.pct.toFixed(1)}%</div>
                    <div class="text-xs font-mono text-gray-500 dark:text-gray-400">${formatUsd(item.diff)}</div>`;
    } else if (type === 'abs') {
      changeHtml = `<div class="font-bold text-emerald-600 dark:text-emerald-400">${formatUsd(item.diff)}</div>
                    <div class="text-xs font-mono text-gray-500 dark:text-gray-400">(${item.pct > 0 ? '+' : ''}${item.pct.toFixed(1)}%)</div>`;
    } else { // new
      changeHtml = `<div class="font-bold text-amber-600 dark:text-amber-400">${formatTotalUsd(item.tvl)}</div>
                    <div class="text-xs font-mono text-gray-500 dark:text-gray-400">Nowy</div>`;
    }

    return `
      <a href="${link}" target="_blank" rel="noopener noreferrer" class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50 flex items-center gap-4 transition-transform duration-200 hover:scale-[1.02] hover:shadow-md">
        <img src="${item.logo}" alt="${item.name} logo" class="w-10 h-10 rounded-full bg-white dark:bg-gray-800 p-1 object-contain" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
        <div class="w-10 h-10 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center font-bold text-gray-500 text-lg" style="display: none;">${item.name ? item.name.charAt(0) : '?'}</div>
        <div class="flex-1">
          <div class="font-semibold text-gray-800 dark:text-gray-100">${item.name}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400">${item.category}</div>
        </div>
        <div class="text-right font-mono">${changeHtml}</div>
      </a>
    `;
  };
  
  const createPlaceholder = (listElement, message) => {
    listElement.innerHTML = `<div class="p-3 text-center text-sm text-gray-500 dark:text-gray-400">${message}</div>`;
  };

  // --- Ładowanie i renderowanie ---
  const loadReport = async (startFile = null, endFile = null) => {
    loader.classList.remove('hidden');
    reportContent.classList.add('hidden');
    errorMessage.classList.add('hidden');
    compareBtn.disabled = true;
    compareBtn.classList.add('animate-pulse');

    let url = '/api/report';
    if (startFile && endFile) {
      url += `?start_file=${startFile}&end_file=${endFile}`;
    }

    try {
      const res = await fetch(url);
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || `Błąd HTTP: ${res.status}`);
      }
      const data = await res.json();
      renderReport(data);
    } catch (e) {
      console.error('Błąd podczas ładowania raportu:', e);
      renderError(e.message);
    } finally {
      setTimeout(() => {
        loader.classList.add('hidden');
        reportContent.classList.remove('hidden');
        compareBtn.disabled = false;
        compareBtn.classList.remove('animate-pulse');
      }, 300);
    }
  };
  
  const renderReport = (data) => {
    reportDates.textContent = `Porównanie od ${formatDate(data.comparisonDate)} do ${formatDate(data.reportDate)}`;
    
    // Wzrosty %
    if (data.top_increases_pct?.length > 0) {
      increasesPctList.innerHTML = data.top_increases_pct.map(item => createChangeItem(item, 'pct')).join('');
    } else {
      createPlaceholder(increasesPctList, 'Brak znaczących wzrostów procentowych.');
    }
    // Wzrosty $
    if (data.top_increases_abs?.length > 0) {
      increasesAbsList.innerHTML = data.top_increases_abs.map(item => createChangeItem(item, 'abs')).join('');
    } else {
      createPlaceholder(increasesAbsList, 'Brak znaczących wzrostów kwotowych.');
    }
    // Nowe protokoły
    if (data.new_protocols?.length > 0) {
      newProtocolsList.innerHTML = data.new_protocols.map(item => createChangeItem(item, 'new')).join('');
    } else {
      createPlaceholder(newProtocolsList, 'Brak nowych protokołów w tym okresie.');
    }
  };

  const renderError = (message) => {
    errorText.textContent = message;
    errorMessage.classList.remove('hidden');
  };
  
  // --- Inicjalizacja Danych ---
  const initialize = async () => {
    try {
      const res = await fetch('/api/snapshots');
      const snapshots = await res.json();
      
      if (snapshots && snapshots.length > 0) {
        snapshots.forEach(s => {
          const option = new Option(`${formatDate(s.date)}`, s.filename);
          startDateSelect.add(option.cloneNode(true));
          endDateSelect.add(option);
        });
        
        // Ustaw domyślne wartości
        endDateSelect.selectedIndex = 0; // Najnowszy
        // Znajdź plik sprzed ok 7 dni
        const endDate = new Date(snapshots[0].date);
        const targetDate = new Date(endDate.setDate(endDate.getDate() - 7));
        
        let closest = null;
        let closestDiff = Infinity;

        for(let i = 1; i < snapshots.length; i++) {
            let d = new Date(snapshots[i].date);
            let diff = Math.abs(d - targetDate);
            if(diff < closestDiff) {
                closestDiff = diff;
                closest = snapshots[i].filename;
            }
        }
        startDateSelect.value = closest || (snapshots.length > 1 ? snapshots[Math.min(7, snapshots.length - 1)].filename : snapshots[0].filename);

      } else {
         renderError("Nie znaleziono żadnych plików z danymi. Wygeneruj snapshoty.");
      }
    } catch (e) {
      renderError("Nie udało się załadować listy dostępnych dat.");
    }
    
    // Załaduj domyślny raport
    loadReport();
  };
  
  compareBtn.addEventListener('click', () => {
    const startFile = startDateSelect.value;
    const endFile = endDateSelect.value;

    if (new Date(startDateSelect.options[startDateSelect.selectedIndex].text) > new Date(endDateSelect.options[endDateSelect.selectedIndex].text)) {
        renderError("Data początkowa nie może być późniejsza niż data końcowa.");
        return;
    }

    if (startFile && endFile) {
      loadReport(startFile, endFile);
    }
  });

  initialize();
});
