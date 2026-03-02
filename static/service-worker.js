const CACHE_NAME = 'betim-conciliacao-v1';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/js/saldos.js',
  '/static/js/rnc.js',
  '/static/manifest.json',
  '/saldos',
  '/rnc'
];

// Instalação do service worker
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Cache aberto');
        return cache.addAll(urlsToCache);
      })
  );
});

// Interceptar requisições
self.addEventListener('fetch', event => {
  // Não cachear requisições de API
  if (event.request.url.includes('/api/')) {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          return caches.match(event.request);
        })
    );
    return;
  }

  // Para outros recursos, tentar cache primeiro
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        
        return fetch(event.request).then(
          response => {
            if(!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            const responseToCache = response.clone();
            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(event.request, responseToCache);
              });

            return response;
          }
        );
      })
  );
});

// Limpar caches antigos
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Sincronização em background para dados offline
self.addEventListener('sync', event => {
  if (event.tag === 'sync-rncs') {
    event.waitUntil(syncRNCs());
  } else if (event.tag === 'sync-saldos') {
    event.waitUntil(syncSaldos());
  }
});

async function syncRNCs() {
  try {
    const db = await openDB();
    const pendingRNCs = await db.getAll('pending-rncs');
    
    for (const rnc of pendingRNCs) {
      const response = await fetch('/api/rncs', {
        method: rnc.id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rnc.data)
      });
      
      if (response.ok) {
        await db.delete('pending-rncs', rnc.id);
      }
    }
  } catch (error) {
    console.error('Erro na sincronização:', error);
  }
}

async function syncSaldos() {
  try {
    const db = await openDB();
    const pendingSaldos = await db.getAll('pending-saldos');
    
    for (const saldo of pendingSaldos) {
      const response = await fetch('/api/saldos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(saldo.data)
      });
      
      if (response.ok) {
        await db.delete('pending-saldos', saldo.id);
      }
    }
  } catch (error) {
    console.error('Erro na sincronização:', error);
  }
}

// IndexedDB helper
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('BetimConciliacaoDB', 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = event => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('pending-rncs')) {
        db.createObjectStore('pending-rncs', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('pending-saldos')) {
        db.createObjectStore('pending-saldos', { keyPath: 'id' });
      }
    };
  });
}