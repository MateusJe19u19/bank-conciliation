// db-offline.js - Gerenciamento de dados offline

// Abrir banco de dados IndexedDB
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
            
            if (!db.objectStoreNames.contains('cached-rncs')) {
                db.createObjectStore('cached-rncs', { keyPath: 'id' });
            }
            
            if (!db.objectStoreNames.contains('cached-saldos')) {
                db.createObjectStore('cached-saldos', { keyPath: 'id' });
            }
        };
    });
}

// Salvar dados pendentes quando offline
async function savePendingData(storeName, data) {
    const db = await openDB();
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    
    const pendingItem = {
        id: Date.now().toString(),
        data: data,
        timestamp: new Date().toISOString()
    };
    
    await store.add(pendingItem);
    
    // Registrar para sincronização quando online
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
        const registration = await navigator.serviceWorker.ready;
        await registration.sync.register(`sync-${storeName.replace('pending-', '')}`);
    }
}

// Verificar status da conexão
function isOnline() {
    return navigator.onLine;
}

// Monitorar mudanças de conexão
window.addEventListener('online', () => {
    console.log('Conexão restabelecida');
    // Disparar sincronização
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.ready.then(registration => {
            registration.sync.register('sync-rncs');
            registration.sync.register('sync-saldos');
        });
    }
    
    // Mostrar notificação
    showNotification('Conexão restabelecida', 'Os dados serão sincronizados automaticamente.');
});

window.addEventListener('offline', () => {
    console.log('Conexão perdida');
    showNotification('Você está offline', 'Os dados serão salvos localmente e sincronizados quando a conexão for restabelecida.');
});

// Mostrar notificação
function showNotification(title, message) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body: message });
    }
    
    // Mostrar toast na interface
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: ${title.includes('offline') ? '#e74c3c' : '#27ae60'};
        color: white;
        padding: 15px 20px;
        border-radius: 5px;
        z-index: 9999;
        animation: slideIn 0.3s;
    `;
    toast.innerHTML = `<strong>${title}</strong><br>${message}`;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Adicionar estilos para animações
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// Solicitar permissão para notificações
if ('Notification' in window) {
    Notification.requestPermission();
}