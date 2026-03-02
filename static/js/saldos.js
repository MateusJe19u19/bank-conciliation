// saldos.js - Script específico para a página de saldos

// ==================== UTILITÁRIOS ====================

function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(valor);
}

// ==================== FUNÇÕES DE SALDOS ====================

let saldosAtuais = [];

// Obter parâmetros da URL
function getParamsFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    return {
        mes: parseInt(urlParams.get('mes')) || new Date().getMonth() + 1,
        ano: parseInt(urlParams.get('ano')) || new Date().getFullYear()
    };
}

function abrirModalSaldo() {
    document.getElementById('modalSaldo').style.display = 'block';
    document.getElementById('formSaldo').reset();
    document.getElementById('diferenca').value = '';
    
    // Resetar checkboxes
    document.getElementById('saldoSagiNegativo').checked = false;
    document.getElementById('saldoBancoNegativo').checked = false;
    
    // Pré-selecionar mês e ano baseado nos parâmetros da URL
    const params = getParamsFromUrl();
    document.getElementById('saldoMesSelect').value = params.mes;
    document.getElementById('saldoAnoSelect').value = params.ano;
}

function fecharModalSaldo() {
    document.getElementById('modalSaldo').style.display = 'none';
}

// Calcular diferença automaticamente
function calcularDiferencaSaldo() {
    const sagi = document.getElementById('saldoSagi').value;
    const banco = document.getElementById('saldoBanco').value;
    const sagiNegativo = document.getElementById('saldoSagiNegativo').checked;
    const bancoNegativo = document.getElementById('saldoBancoNegativo').checked;
    
    if (sagi && banco) {
        let valorSagi = parseFloat(sagi) || 0;
        let valorBanco = parseFloat(banco) || 0;
        
        if (sagiNegativo) valorSagi = -valorSagi;
        if (bancoNegativo) valorBanco = -valorBanco;
        
        const diferenca = valorBanco - valorSagi;
        document.getElementById('diferenca').value = formatarMoeda(diferenca);
    }
}

// Submeter formulário de saldo
document.getElementById('formSaldo')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    let saldoSagi = parseFloat(document.getElementById('saldoSagi').value) || 0;
    let saldoBanco = parseFloat(document.getElementById('saldoBanco').value) || 0;
    
    // Aplicar negativo se checkbox marcado
    if (document.getElementById('saldoSagiNegativo').checked) {
        saldoSagi = -saldoSagi;
    }
    if (document.getElementById('saldoBancoNegativo').checked) {
        saldoBanco = -saldoBanco;
    }
    
    const saldo = {
        banco: document.getElementById('bancoSelect').value,
        empresa: document.getElementById('empresaSelect').value,
        saldo_sagi: saldoSagi,
        saldo_banco: saldoBanco,
        mes: parseInt(document.getElementById('saldoMesSelect').value),
        ano: parseInt(document.getElementById('saldoAnoSelect').value),
        averbacao: document.getElementById('averbacao').value
    };
    
    try {
        const response = await fetch('/api/saldos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(saldo)
        });
        
        if (response.ok) {
            fecharModalSaldo();
            carregarSaldos();
        }
    } catch (error) {
        console.error('Erro ao salvar:', error);
        alert('Erro ao salvar o saldo. Tente novamente.');
    }
});

async function carregarSaldos() {
    const params = getParamsFromUrl();
    
    try {
        const response = await fetch(`/api/saldos?mes=${params.mes}&ano=${params.ano}`);
        saldosAtuais = await response.json();
        
        const tbody = document.getElementById('saldosBody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        if (saldosAtuais.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="6" style="text-align: center; padding: 20px;">Nenhum saldo encontrado para este período</td>';
            tbody.appendChild(tr);
            return;
        }
        
        saldosAtuais.forEach(saldo => {
            const tr = document.createElement('tr');
            const diferenca = saldo.saldo_banco - saldo.saldo_sagi;
            
            tr.innerHTML = `
                <td>${saldo.banco}</td>
                <td>${saldo.empresa}</td>
                <td>${formatarMoeda(saldo.saldo_sagi)}</td>
                <td>${formatarMoeda(saldo.saldo_banco)}</td>
                <td>${formatarMoeda(diferenca)}</td>
                <td class="action-cell">
                    <button class="delete-btn" onclick="deletarSaldo('${saldo.id}')">Excluir</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (error) {
        console.error('Erro ao carregar saldos:', error);
    }
}

async function deletarSaldo(id) {
    if (!confirm('Tem certeza que deseja excluir este saldo?')) return;
    
    try {
        const response = await fetch(`/api/saldos/${id}`, { method: 'DELETE' });
        if (response.ok) {
            carregarSaldos();
        }
    } catch (error) {
        console.error('Erro ao deletar:', error);
        alert('Erro ao excluir o saldo. Tente novamente.');
    }
}

// ==================== INICIALIZAÇÃO ====================

document.addEventListener('DOMContentLoaded', function() {
    // Carregar dados iniciais
    carregarSaldos();
    
    // Adicionar evento para calcular diferença quando os campos mudarem
    const saldoSagi = document.getElementById('saldoSagi');
    const saldoBanco = document.getElementById('saldoBanco');
    const sagiNegativo = document.getElementById('saldoSagiNegativo');
    const bancoNegativo = document.getElementById('saldoBancoNegativo');
    
    if (saldoSagi && saldoBanco) {
        saldoSagi.addEventListener('input', calcularDiferencaSaldo);
        saldoBanco.addEventListener('input', calcularDiferencaSaldo);
        sagiNegativo.addEventListener('change', calcularDiferencaSaldo);
        bancoNegativo.addEventListener('change', calcularDiferencaSaldo);
    }
});

// Fechar modais ao clicar fora
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
};