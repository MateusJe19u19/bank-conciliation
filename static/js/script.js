// script.js - Script principal para o index.html

// ==================== NAVEGAÇÃO ENTRE PÁGINAS ====================

function showPage(page) {
    // Atualizar botões
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Mostrar página
    document.querySelectorAll('.page').forEach(p => {
        p.classList.remove('active');
    });
    document.getElementById(page + 'Page').classList.add('active');
}

// ==================== CONTROLE DE FILTRO ====================

function getFiltroAtual() {
    const mes = document.getElementById('mesSelect')?.value || new Date().getMonth() + 1;
    const ano = document.getElementById('anoSelect')?.value || new Date().getFullYear();
    return { mes: parseInt(mes), ano: parseInt(ano) };
}

function filtrar() {
    const filtro = getFiltroAtual();
    
    // Atualizar iframes com os novos parâmetros
    const saldosFrame = document.getElementById('saldosFrame');
    const rncFrame = document.getElementById('rncFrame');
    
    if (saldosFrame) {
        saldosFrame.src = `/saldos?mes=${filtro.mes}&ano=${filtro.ano}`;
    }
    
    if (rncFrame) {
        rncFrame.src = `/rnc?mes=${filtro.mes}&ano=${filtro.ano}`;
    }
}

// ==================== FUNÇÕES DE EXTRATOS ====================

async function importarExtratos() {
    const filtro = getFiltroAtual();
    
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.accept = '.pdf';
    
    input.onchange = async function(e) {
        const files = Array.from(e.target.files);
        const formData = new FormData();
        
        files.forEach(file => {
            formData.append('files[]', file);
        });
        
        // CORREÇÃO: Enviar o mês como número, não como nome
        formData.append('mes', filtro.mes);
        formData.append('ano', filtro.ano);
        
        try {
            const response = await fetch('/api/extratos/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.erros.length > 0) {
                alert('Alguns arquivos não foram importados:\n' + result.erros.join('\n'));
            } else {
                alert(`${result.arquivos.length} arquivo(s) importado(s) com sucesso!`);
            }
        } catch (error) {
            console.error('Erro ao importar:', error);
            alert('Erro ao importar arquivos');
        }
    };
    
    input.click();
}

async function gerarPDF() {
    const filtro = getFiltroAtual();
    window.open(`/api/gerar-pdf?mes=${filtro.mes}&ano=${filtro.ano}`, '_blank');
}

async function gerarZip() {
    const filtro = getFiltroAtual();
    window.open(`/api/gerar-zip?mes=${filtro.mes}&ano=${filtro.ano}`, '_blank');
}

// ==================== INICIALIZAÇÃO ====================

document.addEventListener('DOMContentLoaded', function() {
    // Configurar mês e ano atual
    const hoje = new Date();
    const mesSelect = document.getElementById('mesSelect');
    const anoSelect = document.getElementById('anoSelect');
    
    if (mesSelect) mesSelect.value = hoje.getMonth() + 1;
    if (anoSelect) anoSelect.value = hoje.getFullYear();
    
    // Aplicar filtro inicial
    filtrar();
});