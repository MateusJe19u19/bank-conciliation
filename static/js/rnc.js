// rnc.js - Script específico para a página de RNC

// ==================== UTILITÁRIOS ====================

function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(valor);
}

// ==================== FUNÇÕES DE RNC ====================

let rncsAtuais = [];
let rncEditandoId = null;

// Obter parâmetros da URL
function getParamsFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    return {
        mes: parseInt(urlParams.get('mes')) || new Date().getMonth() + 1,
        ano: parseInt(urlParams.get('ano')) || new Date().getFullYear()
    };
}

// CORREÇÃO: Função para ajustar o fuso horário da data
function ajustarDataParaISO(dataString) {
    if (!dataString) return '';
    // Adiciona o horário meio-dia para evitar problemas de fuso
    return dataString + 'T12:00:00';
}

function abrirModalRNC() {
    rncEditandoId = null;
    document.getElementById('modalRNC').style.display = 'block';
    document.getElementById('formRNC').reset();
    document.getElementById('modalRNCtitulo').textContent = 'Nova Não Conformidade';
    document.getElementById('rncSubmitBtn').textContent = 'Registrar';
    document.getElementById('rncId').value = '';
    
    // Resetar checkbox
    document.getElementById('rncValorNegativo').checked = false;
    
    // Preencher data atual
    const hoje = new Date().toISOString().split('T')[0];
    document.getElementById('rncData').value = hoje;
    
    // Pré-selecionar mês e ano baseado nos parâmetros da URL
    const params = getParamsFromUrl();
    document.getElementById('rncMesSelect').value = params.mes;
    document.getElementById('rncAnoSelect').value = params.ano;
}

function editarRNC(id) {
    event.stopPropagation();
    const rnc = rncsAtuais.find(r => r.id === id);
    if (!rnc) return;
    
    rncEditandoId = id;
    document.getElementById('modalRNC').style.display = 'block';
    document.getElementById('modalRNCtitulo').textContent = 'Editar Não Conformidade';
    document.getElementById('rncSubmitBtn').textContent = 'Atualizar';
    document.getElementById('rncId').value = rnc.id;
    
    // Preencher campos
    document.getElementById('rncBancoSelect').value = rnc.banco;
    document.getElementById('rncEmpresaSelect').value = rnc.empresa || 'MDR';
    document.getElementById('rncMesSelect').value = rnc.mes;
    document.getElementById('rncAnoSelect').value = rnc.ano;
    
    // CORREÇÃO: Extrair apenas a data (YYYY-MM-DD) da data ISO
    const dataPartes = rnc.data_rnc.split('T')[0];
    document.getElementById('rncData').value = dataPartes;
    
    document.getElementById('rncDocumento').value = rnc.documento;
    
    // Valor e negativo
    const valorAbs = Math.abs(rnc.valor);
    document.getElementById('rncValor').value = valorAbs;
    document.getElementById('rncValorNegativo').checked = rnc.valor < 0;
    
    document.getElementById('rncPessoa').value = rnc.pessoa;
    document.getElementById('rncTipo').value = rnc.tipo;
    document.getElementById('rncMotivo').value = rnc.motivo;
    document.getElementById('rncCorrecao').value = rnc.correcao;
}

function fecharModalRNC() {
    document.getElementById('modalRNC').style.display = 'none';
    rncEditandoId = null;
}

// Submeter formulário de RNC (criar ou atualizar)
document.getElementById('formRNC')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    let valor = parseFloat(document.getElementById('rncValor').value) || 0;
    
    // Aplicar negativo se checkbox marcado
    if (document.getElementById('rncValorNegativo').checked) {
        valor = -valor;
    }
    
    // CORREÇÃO: Ajustar a data para evitar problema de fuso
    const dataSelecionada = document.getElementById('rncData').value;
    const dataAjustada = ajustarDataParaISO(dataSelecionada);
    
    const rncData = {
        banco: document.getElementById('rncBancoSelect').value,
        empresa: document.getElementById('rncEmpresaSelect').value,
        data_rnc: dataAjustada,  // Usar data ajustada
        documento: document.getElementById('rncDocumento').value,
        valor: valor,
        pessoa: document.getElementById('rncPessoa').value,
        tipo: document.getElementById('rncTipo').value,
        motivo: document.getElementById('rncMotivo').value,
        correcao: document.getElementById('rncCorrecao').value,
        mes: parseInt(document.getElementById('rncMesSelect').value),
        ano: parseInt(document.getElementById('rncAnoSelect').value)
    };
    
    console.log('Enviando dados:', rncData);
    
    try {
        let response;
        
        if (rncEditandoId) {
            // Atualizar RNC existente - NÃO incluir o ID no corpo
            console.log('Atualizando RNC ID:', rncEditandoId);
            
            response = await fetch(`/api/rncs/${rncEditandoId}`, {
                method: 'PUT',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(rncData)  // Não inclui o ID
            });
        } else {
            // Criar nova RNC
            console.log('Criando nova RNC');
            
            response = await fetch('/api/rncs', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(rncData)
            });
        }
        
        const responseText = await response.text();
        console.log('Resposta do servidor:', response.status, responseText);
        
        if (response.ok) {
            fecharModalRNC();
            carregarRNCs();
        } else {
            let errorData;
            try {
                errorData = JSON.parse(responseText);
            } catch (e) {
                errorData = { error: responseText };
            }
            alert('Erro ao salvar: ' + (errorData.error || 'Erro desconhecido'));
        }
    } catch (error) {
        console.error('Erro ao salvar RNC:', error);
        alert('Erro ao salvar a RNC. Verifique o console para mais detalhes.');
    }
});

async function carregarRNCs() {
    const params = getParamsFromUrl();
    
    try {
        const response = await fetch(`/api/rncs?mes=${params.mes}&ano=${params.ano}`);
        rncsAtuais = await response.json();
        
        const tbody = document.getElementById('rncBody');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        if (rncsAtuais.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="10" style="text-align: center; padding: 20px;">Nenhuma RNC encontrada para este período</td>';
            tbody.appendChild(tr);
            return;
        }
        
        rncsAtuais.forEach((rnc, index) => {
            const tr = document.createElement('tr');
            tr.className = 'expansivel';
            tr.onclick = () => toggleExpansao(index);
            
            // CORREÇÃO: Extrair a data corretamente
            let dataFormatada = '';
            if (rnc.data_rnc) {
                const dataPartes = rnc.data_rnc.split('T')[0].split('-');
                if (dataPartes.length === 3) {
                    dataFormatada = `${dataPartes[2]}/${dataPartes[1]}/${dataPartes[0]}`;
                }
            }
            
            tr.innerHTML = `
                <td>${rnc.banco}</td>
                <td>${rnc.empresa || ''}</td>
                <td>${dataFormatada}</td>
                <td>${rnc.documento}</td>
                <td>${formatarMoeda(rnc.valor)}</td>
                <td>${rnc.pessoa}</td>
                <td>${rnc.tipo}</td>
                <td>${rnc.motivo}</td>
                <td>${rnc.correcao}</td>
                <td class="action-cell">
                    <button class="edit-btn" onclick="event.stopPropagation(); editarRNC('${rnc.id}')">✏️ Editar</button>
                    <button class="expand-btn" onclick="event.stopPropagation(); abrirModalExpansao('${rnc.id}')">📋 Expansões</button>
                    <button class="delete-btn" onclick="event.stopPropagation(); deletarRNC('${rnc.id}')">🗑️ Excluir</button>
                </td>
            `;
            tbody.appendChild(tr);
            
            // Linha de expansão (inicialmente oculta)
            const trExp = document.createElement('tr');
            trExp.id = `expansao-${index}`;
            trExp.className = 'expansao-row';
            trExp.style.display = 'none';
            trExp.innerHTML = `
                <td colspan="10">
                    <div id="expansao-content-${index}"></div>
                </td>
            `;
            tbody.appendChild(trExp);
        });
    } catch (error) {
        console.error('Erro ao carregar RNCs:', error);
    }
}

function toggleExpansao(index) {
    const tr = document.getElementById(`expansao-${index}`);
    if (tr.style.display === 'none') {
        tr.style.display = 'table-row';
        carregarExpansoes(rncsAtuais[index].id, index);
    } else {
        tr.style.display = 'none';
    }
}

// ==================== FUNÇÕES DE EXPANSÃO ====================

let rncSelecionada = null;

async function abrirModalExpansao(rncId) {
    event.stopPropagation();
    rncSelecionada = rncsAtuais.find(r => r.id === rncId);
    document.getElementById('modalExpansao').style.display = 'block';
    await carregarExpansoes(rncId);
}

function fecharModalExpansao() {
    document.getElementById('modalExpansao').style.display = 'none';
    rncSelecionada = null;
}

async function carregarExpansoes(rncId) {
    const rnc = rncsAtuais.find(r => r.id === rncId);
    if (!rnc) return;
    
    const tbody = document.getElementById('expansoesBody');
    tbody.innerHTML = '';
    
    (rnc.expansoes || []).forEach(exp => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><input type="text" value="${exp.solicitacao || ''}" onchange="atualizarExpansao('${rnc.id}', '${exp.id}', 'solicitacao', this.value)"></td>
            <td><input type="date" value="${exp.data_sol || ''}" onchange="atualizarExpansao('${rnc.id}', '${exp.id}', 'data_sol', this.value)"></td>
            <td><input type="text" value="${exp.setor || ''}" onchange="atualizarExpansao('${rnc.id}', '${exp.id}', 'setor', this.value)"></td>
            <td><input type="date" value="${exp.data_dev || ''}" onchange="atualizarExpansao('${rnc.id}', '${exp.id}', 'data_dev', this.value)"></td>
            <td><input type="text" value="${exp.devolutiva || ''}" onchange="atualizarExpansao('${rnc.id}', '${exp.id}', 'devolutiva', this.value)"></td>
            <td>
                <select onchange="atualizarExpansao('${rnc.id}', '${exp.id}', 'status', this.value)">
                    <option value="Pendente" ${exp.status === 'Pendente' ? 'selected' : ''}>Pendente</option>
                    <option value="Concluído" ${exp.status === 'Concluído' ? 'selected' : ''}>Concluído</option>
                </select>
            </td>
            <td><button class="delete-btn" onclick="deletarExpansao('${rnc.id}', '${exp.id}')">🗑️</button></td>
        `;
        tbody.appendChild(tr);
    });
}

async function adicionarExpansao() {
    if (!rncSelecionada) return;
    
    const novaExpansao = {
        solicitacao: '',
        data_sol: new Date().toISOString().split('T')[0],
        setor: '',
        data_dev: '',
        devolutiva: '',
        status: 'Pendente'
    };
    
    try {
        const response = await fetch(`/api/rncs/${rncSelecionada.id}/expansoes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(novaExpansao)
        });
        
        if (response.ok) {
            // Recarregar dados
            const params = getParamsFromUrl();
            const resp = await fetch(`/api/rncs?mes=${params.mes}&ano=${params.ano}`);
            rncsAtuais = await resp.json();
            rncSelecionada = rncsAtuais.find(r => r.id === rncSelecionada.id);
            await carregarExpansoes(rncSelecionada.id);
        }
    } catch (error) {
        console.error('Erro ao adicionar expansão:', error);
        alert('Erro ao adicionar registro. Tente novamente.');
    }
}

async function atualizarExpansao(rncId, expId, campo, valor) {
    const rnc = rncsAtuais.find(r => r.id === rncId);
    const exp = (rnc.expansoes || []).find(e => e.id === expId);
    if (exp) {
        exp[campo] = valor;
        
        try {
            await fetch(`/api/rncs/${rncId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(rnc)
            });
        } catch (error) {
            console.error('Erro ao atualizar expansão:', error);
        }
    }
}

async function deletarExpansao(rncId, expId) {
    if (!confirm('Tem certeza que deseja excluir este registro?')) return;
    
    const rnc = rncsAtuais.find(r => r.id === rncId);
    rnc.expansoes = (rnc.expansoes || []).filter(e => e.id !== expId);
    
    try {
        await fetch(`/api/rncs/${rncId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(rnc)
        });
        
        await carregarExpansoes(rncId);
    } catch (error) {
        console.error('Erro ao deletar expansão:', error);
        alert('Erro ao excluir registro. Tente novamente.');
    }
}

// Função para deletar RNC
async function deletarRNC(id) {
    if (!confirm('Tem certeza que deseja excluir esta RNC?')) return;
    
    try {
        const response = await fetch(`/api/rncs/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            alert('RNC excluída com sucesso!');
            carregarRNCs(); // Recarrega a lista
        } else {
            alert('Erro ao excluir RNC');
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao excluir RNC');
    }
}

// ==================== INICIALIZAÇÃO ====================

document.addEventListener('DOMContentLoaded', function() {
    // Carregar dados iniciais
    carregarRNCs();
});

// Fechar modais ao clicar fora
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
        rncEditandoId = null;
    }
};
