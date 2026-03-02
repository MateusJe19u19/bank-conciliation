from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime
import zipfile
import io
import traceback
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.utils import ImageReader
import shutil
from werkzeug.utils import secure_filename
import sys

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
CORS(app)

# ==================== CONFIGURAÇÃO DE CAMINHOS ====================
# Usar caminhos relativos para funcionar no Netlify
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
EXTRATOS_FOLDER = os.path.join(BASE_DIR, 'extratos')
ALLOWED_EXTENSIONS = {'pdf'}

print("="*60)
print("🔍 INFORMAÇÕES DO SISTEMA")
print("="*60)
print(f"📁 Diretório atual: {os.getcwd()}")
print(f"📁 Local do app.py: {os.path.dirname(os.path.abspath(__file__))}")
print(f"📄 DATA_FILE: {DATA_FILE}")
print(f"📁 EXTRATOS_FOLDER: {EXTRATOS_FOLDER}")
print(f"📁 O arquivo existe? {os.path.exists(DATA_FILE)}")
print("="*60)

# Garantir que as pastas existam
os.makedirs(EXTRATOS_FOLDER, exist_ok=True)

# ==================== FUNÇÕES AUXILIARES ====================

def load_data():
    """Carrega dados do JSON com verificação de existência"""
    try:
        if os.path.exists(DATA_FILE):
            print(f"📂 Arquivo data.json encontrado")
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ Dados carregados: {len(data.get('saldos', []))} saldos, {len(data.get('rncs', []))} RNCs")
                return data
        else:
            print(f"⚠️ Arquivo data.json NÃO encontrado!")
            print(f"📝 Criando novo arquivo data.json...")
            
            # Garantir que o diretório existe
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            
            # Cria um arquivo vazio
            initial_data = {'saldos': [], 'rncs': []}
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Arquivo criado em: {DATA_FILE}")
            return initial_data
    except Exception as e:
        print(f"❌ Erro ao carregar dados: {e}")
        traceback.print_exc()
        return {'saldos': [], 'rncs': []}

def save_data(data):
    """Salva dados no JSON com verificação"""
    try:
        print(f"💾 Salvando dados...")
        
        # Garantir que o diretório existe
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        # Verifica se o arquivo foi realmente criado
        if os.path.exists(DATA_FILE):
            file_size = os.path.getsize(DATA_FILE)
            print(f"✅ Dados salvos com sucesso! ({file_size} bytes)")
        else:
            print(f"❌ Arquivo NÃO foi criado!")
            
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar dados: {e}")
        traceback.print_exc()
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== FUNÇÕES DE FORMATAÇÃO PARA PDF ====================

def formatar_valor_pdf(valor):
    """Formata valor para exibição no PDF com sinal de menos para valores negativos"""
    if valor < 0:
        return f"-R$ {abs(valor):,.2f}".replace('.', ',')
    else:
        return f"R$ {valor:,.2f}".replace('.', ',')

def criar_estilos_pdf():
    """Cria os estilos personalizados para o PDF"""
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='TituloPrincipal',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#002060'),
        alignment=1,  # Centralizado
        spaceAfter=10,
        spaceBefore=10
    ))
    
    styles.add(ParagraphStyle(
        name='TituloSecao',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor('#002060'),
        alignment=1,  # Centralizado
        spaceAfter=15,
        spaceBefore=20
    ))
    
    styles.add(ParagraphStyle(
        name='TextoNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#002060'),
        alignment=0,  # Esquerda
        spaceAfter=3,
        leftIndent=2,
        wordWrap='CJK'
    ))
    
    styles.add(ParagraphStyle(
        name='TextoCentralizado',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#002060'),
        alignment=1,  # Centralizado
        spaceAfter=5
    ))
    
    return styles

def criar_tabela_saldos(saldos, styles):
    """Cria a tabela de saldos com larguras adequadas"""
    if not saldos:
        return Paragraph("Nenhum saldo registrado para este período.", styles['TextoCentralizado'])
    
    dados = [['Banco', 'Empresa', 'Saldo SAGI', 'Saldo Banco', 'Diferença']]
    
    for s in saldos:
        diferenca = s['saldo_banco'] - s['saldo_sagi']
        
        linha = [
            Paragraph(s['banco'], styles['TextoNormal']),
            Paragraph(s['empresa'], styles['TextoNormal']),
            Paragraph(formatar_valor_pdf(s['saldo_sagi']), styles['TextoNormal']),
            Paragraph(formatar_valor_pdf(s['saldo_banco']), styles['TextoNormal']),
            Paragraph(formatar_valor_pdf(diferenca), styles['TextoNormal'])
        ]
        dados.append(linha)
    
    # Larguras das colunas para landscape
    col_widths = [50*mm, 40*mm, 50*mm, 50*mm, 50*mm]  # Total: 240mm
    
    tabela = Table(dados, colWidths=col_widths, repeatRows=1)
    
    estilo_tabela = [
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#002060')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#002060')),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ('BOX', (0, 0), (-1, -1), 0, colors.white),
        ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
    ]
    
    tabela.setStyle(TableStyle(estilo_tabela))
    
    return tabela

def criar_tabela_rncs(rncs, styles):
    """Cria a tabela de RNCs com larguras adequadas"""
    if not rncs:
        return Paragraph("Nenhuma não conformidade registrada para este período.", styles['TextoCentralizado'])
    
    dados = [['Banco', 'Empresa', 'Data', 'Documento', 'Valor', 'Tipo', 'Motivo', 'Correção']]
    
    for r in rncs:
        try:
            # CORREÇÃO: Lidar com ambos os formatos de data
            data_rnc = r['data_rnc']
            if 'T' in data_rnc:
                data_obj = datetime.fromisoformat(data_rnc.split('T')[0])
            else:
                data_obj = datetime.fromisoformat(data_rnc)
            data = data_obj.strftime('%d/%m/%Y')
        except:
            data = r['data_rnc'][:10] if r['data_rnc'] else ''
        
        linha = [
            Paragraph(r['banco'], styles['TextoNormal']),
            Paragraph(r.get('empresa', ''), styles['TextoNormal']),
            Paragraph(data, styles['TextoNormal']),
            Paragraph(r['documento'], styles['TextoNormal']),
            Paragraph(formatar_valor_pdf(r['valor']), styles['TextoNormal']),
            Paragraph(r['tipo'], styles['TextoNormal']),
            Paragraph(r['motivo'], styles['TextoNormal']),
            Paragraph(r['correcao'], styles['TextoNormal'])
        ]
        dados.append(linha)
    
    # Larguras das colunas para landscape
    col_widths = [30*mm, 25*mm, 22*mm, 30*mm, 30*mm, 25*mm, 40*mm, 40*mm]  # Total: 242mm
    
    tabela = Table(dados, colWidths=col_widths, repeatRows=1)
    
    estilo_tabela = [
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#002060')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#002060')),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ('BOX', (0, 0), (-1, -1), 0, colors.white),
        ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
    ]
    
    tabela.setStyle(TableStyle(estilo_tabela))
    
    return tabela

# ==================== ROTAS PRINCIPAIS ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/saldos')
def saldos():
    return render_template('saldos.html')

@app.route('/rnc')
def rnc():
    return render_template('rnc.html')

@app.route('/offline')
def offline():
    return render_template('offline.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# ==================== ROTAS DE SALDOS ====================

@app.route('/api/saldos', methods=['GET', 'POST'])
def handle_saldos():
    if request.method == 'POST':
        try:
            print("\n" + "="*50)
            print("📝 REQUISIÇÃO POST - NOVO SALDO")
            data = request.json
            print(f"Dados recebidos: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            db = load_data()
            
            novo_saldo = {
                'id': str(int(datetime.now().timestamp() * 1000)),
                'banco': data['banco'],
                'empresa': data['empresa'],
                'saldo_sagi': float(data['saldo_sagi']),
                'saldo_banco': float(data['saldo_banco']),
                'mes': int(data['mes']),
                'ano': int(data['ano']),
                'averbacao': data.get('averbacao', ''),
                'data_registro': datetime.now().isoformat()
            }
            
            if 'saldos' not in db:
                db['saldos'] = []
            db['saldos'].append(novo_saldo)
            
            if save_data(db):
                print("✅ Saldo salvo com sucesso!")
                return jsonify(novo_saldo)
            else:
                return jsonify({'error': 'Erro ao salvar dados'}), 500
                
        except Exception as e:
            print(f"❌ Erro ao criar saldo: {e}")
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    else:  # GET
        try:
            mes = request.args.get('mes', type=int)
            ano = request.args.get('ano', type=int)
            print(f"\n📋 Buscando saldos para mês={mes}, ano={ano}")
            
            db = load_data()
            
            saldos_filtrados = [s for s in db.get('saldos', []) 
                              if s['mes'] == mes and s['ano'] == ano]
            print(f"✅ Encontrados {len(saldos_filtrados)} saldos")
            
            return jsonify(saldos_filtrados)
        except Exception as e:
            print(f"❌ Erro ao buscar saldos: {e}")
            return jsonify([]), 200

@app.route('/api/saldos/<id>', methods=['DELETE'])
def delete_saldo(id):
    try:
        print(f"\n🗑️ Deletando saldo ID: {id}")
        db = load_data()
        db['saldos'] = [s for s in db.get('saldos', []) if s['id'] != id]
        save_data(db)
        print("✅ Saldo deletado com sucesso!")
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Erro ao deletar saldo: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== ROTAS DE RNC ====================

@app.route('/api/rncs', methods=['GET', 'POST'])
def handle_rncs():
    if request.method == 'POST':
        try:
            print("\n" + "="*50)
            print("📝 REQUISIÇÃO POST - NOVA RNC")
            data = request.json
            print(f"Dados recebidos: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            db = load_data()
            
            # CORREÇÃO: Processar a data corretamente
            data_rnc = data['data_rnc']
            if 'T' in data_rnc:
                data_rnc = data_rnc.split('T')[0]
            
            # Extrair mês e ano da data
            data_parts = data_rnc.split('-')
            mes = int(data_parts[1])
            ano = int(data_parts[0])
            
            nova_rnc = {
                'id': str(int(datetime.now().timestamp() * 1000)),
                'banco': data['banco'],
                'empresa': data.get('empresa', ''),
                'data_rnc': data_rnc,  # Formato YYYY-MM-DD
                'documento': data['documento'],
                'valor': float(data['valor']),
                'pessoa': data['pessoa'],
                'tipo': data['tipo'],
                'motivo': data['motivo'],
                'correcao': data['correcao'],
                'mes': mes,
                'ano': ano,
                'expansoes': [],
                'data_registro': datetime.now().isoformat()
            }
            
            print(f"Nova RNC criada: ID={nova_rnc['id']}")
            
            if 'rncs' not in db:
                db['rncs'] = []
            db['rncs'].append(nova_rnc)
            
            if save_data(db):
                print("✅ RNC salva com sucesso!")
                return jsonify(nova_rnc)
            else:
                return jsonify({'error': 'Erro ao salvar dados'}), 500
                
        except Exception as e:
            print(f"❌ Erro ao criar RNC: {e}")
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    else:  # GET
        try:
            mes = request.args.get('mes', type=int)
            ano = request.args.get('ano', type=int)
            print(f"\n📋 Buscando RNCs para mês={mes}, ano={ano}")
            
            db = load_data()
            
            rncs_filtradas = [r for r in db.get('rncs', []) 
                             if r['mes'] == mes and r['ano'] == ano]
            print(f"✅ Encontradas {len(rncs_filtradas)} RNCs")
            
            return jsonify(rncs_filtradas)
        except Exception as e:
            print(f"❌ Erro ao buscar RNCs: {e}")
            traceback.print_exc()
            return jsonify([]), 200

@app.route('/api/rncs/<id>', methods=['PUT'])
def update_rnc(id):
    try:
        print("\n" + "="*50)
        print(f"📝 REQUISIÇÃO PUT - ATUALIZAR RNC ID: {id}")
        data = request.json
        print(f"Dados recebidos: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        db = load_data()
        print(f"Banco de dados carregado. Total RNCs: {len(db.get('rncs', []))}")
        
        encontrou = False
        for i, rnc in enumerate(db.get('rncs', [])):
            # CORREÇÃO: Usar .get() para evitar KeyError
            rnc_id = rnc.get('id')
            print(f"Comparando ID: {rnc_id} com {id}")
            
            if rnc_id == id:
                print(f"✅ RNC encontrada no índice {i}")
                
                # CORREÇÃO: Processar a data corretamente
                data_rnc = data['data_rnc']
                if 'T' in data_rnc:
                    data_rnc = data_rnc.split('T')[0]
                
                # Extrair mês e ano da data se não fornecidos
                if 'mes' not in data or 'ano' not in data:
                    data_parts = data_rnc.split('-')
                    mes = int(data_parts[1])
                    ano = int(data_parts[0])
                else:
                    mes = int(data['mes'])
                    ano = int(data['ano'])
                
                # CORREÇÃO: Criar nova RNC mantendo o ID e expansões
                nova_rnc = {
                    'id': rnc['id'],  # Manter o ID original
                    'banco': data['banco'],
                    'empresa': data.get('empresa', ''),
                    'data_rnc': data_rnc,  # Data processada
                    'documento': data['documento'],
                    'valor': float(data['valor']),
                    'pessoa': data['pessoa'],
                    'tipo': data['tipo'],
                    'motivo': data['motivo'],
                    'correcao': data['correcao'],
                    'mes': mes,
                    'ano': ano,
                    'expansoes': rnc.get('expansoes', []),  # Preservar expansões
                    'data_registro': rnc.get('data_registro', datetime.now().isoformat())
                }
                
                db['rncs'][i] = nova_rnc
                encontrou = True
                print("✅ RNC atualizada em memória")
                break
        
        if not encontrou:
            print(f"❌ RNC com ID {id} não encontrada")
            return jsonify({'error': 'RNC não encontrada'}), 404
        
        if save_data(db):
            print("✅ Dados salvos com sucesso!")
            return jsonify({'success': True, 'id': id})
        else:
            print("❌ Erro ao salvar dados")
            return jsonify({'error': 'Erro ao salvar dados'}), 500
            
    except Exception as e:
        print(f"❌ Erro ao atualizar RNC: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/rncs/<id>/expansoes', methods=['POST'])
def add_expansao(id):
    try:
        print(f"\n📝 Adicionando expansão à RNC ID: {id}")
        data = request.json
        db = load_data()
        
        encontrou = False
        for rnc in db.get('rncs', []):
            if rnc.get('id') == id:
                if 'expansoes' not in rnc:
                    rnc['expansoes'] = []
                
                nova_expansao = {
                    'id': str(int(datetime.now().timestamp() * 1000)),
                    'solicitacao': data.get('solicitacao', ''),
                    'data_sol': data.get('data_sol'),
                    'setor': data.get('setor', ''),
                    'data_dev': data.get('data_dev'),
                    'devolutiva': data.get('devolutiva', ''),
                    'status': data.get('status', 'Pendente')
                }
                rnc['expansoes'].append(nova_expansao)
                encontrou = True
                print(f"✅ Expansão adicionada: {nova_expansao['id']}")
                break
        
        if not encontrou:
            return jsonify({'error': 'RNC não encontrada'}), 404
        
        if save_data(db):
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Erro ao salvar dados'}), 500
            
    except Exception as e:
        print(f"❌ Erro ao adicionar expansão: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ==================== ROTAS DE EXTRATOS ====================

@app.route('/api/extratos/upload', methods=['POST'])
def upload_extratos():
    try:
        if 'files[]' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        files = request.files.getlist('files[]')
        mes = request.form.get('mes')
        ano = request.form.get('ano')
        
        # Usar o mês com dois dígitos para a pasta
        mes_pasta = f"{int(mes):02d}"
        pasta_destino = os.path.join(EXTRATOS_FOLDER, ano, mes_pasta)
        os.makedirs(pasta_destino, exist_ok=True)
        
        arquivos_salvos = []
        erros = []
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(pasta_destino, filename)
                
                if os.path.exists(filepath):
                    erros.append(f'{filename} já existe')
                else:
                    file.save(filepath)
                    arquivos_salvos.append(filename)
        
        return jsonify({
            'success': True,
            'arquivos': arquivos_salvos,
            'erros': erros
        })
    except Exception as e:
        print(f"❌ Erro ao upload extratos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/extratos/listar', methods=['GET'])
def listar_extratos():
    try:
        mes = request.args.get('mes')
        ano = request.args.get('ano')
        
        mes_pasta = f"{int(mes):02d}" if mes else None
        pasta = os.path.join(EXTRATOS_FOLDER, ano, mes_pasta) if mes_pasta else None
        
        arquivos = []
        
        if pasta and os.path.exists(pasta):
            arquivos = [f for f in os.listdir(pasta) if f.endswith('.pdf')]
        
        return jsonify(arquivos)
    except Exception as e:
        print(f"❌ Erro ao listar extratos: {e}")
        return jsonify([]), 200

# ==================== ROTA DE PDF ====================

@app.route('/api/gerar-pdf', methods=['GET'])
def gerar_pdf():
    try:
        mes = request.args.get('mes', type=int)
        ano = request.args.get('ano', type=int)
        
        print(f"\n📄 Gerando PDF para {mes:02d}/{ano}")
        
        db = load_data()
        saldos = [s for s in db.get('saldos', []) if s['mes'] == mes and s['ano'] == ano]
        rncs = [r for r in db.get('rncs', []) if r['mes'] == mes and r['ano'] == ano]
        
        print(f"📊 Saldos: {len(saldos)}, RNCs: {len(rncs)}")
        
        buffer = io.BytesIO()
        
        # Usar orientação landscape
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(A4),
            leftMargin=15*mm,
            rightMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=15*mm
        )
        
        elements = []
        styles = criar_estilos_pdf()
        
        # Adicionar logo se existir - redimensionada para caber na página
        logo_path = os.path.join(os.path.dirname(__file__), 'Logo.emf')
        if os.path.exists(logo_path):
            try:
                # Definir tamanho máximo para a logo (100mm de largura)
                max_width = 100*mm
                
                # Obter dimensões originais para manter proporção
                img = ImageReader(logo_path)
                img_width, img_height = img.getSize()
                
                # Calcular altura proporcional
                scale = max_width / img_width
                new_width = max_width
                new_height = img_height * scale
                
                # Limitar altura máxima se necessário
                max_height = 30*mm
                if new_height > max_height:
                    scale = max_height / new_height
                    new_width = new_width * scale
                    new_height = max_height
                
                logo = Image(logo_path, width=new_width, height=new_height)
                logo.hAlign = 'LEFT'  # Alinhar à esquerda
                elements.append(logo)
                elements.append(Spacer(1, 5))
                print(f"✅ Logo redimensionada: {new_width/mm:.1f}mm x {new_height/mm:.1f}mm")
            except Exception as e:
                print(f"⚠️ Erro ao carregar logo: {e}")
        
        elements.append(Paragraph("Período de Vigência", styles['TituloPrincipal']))
        elements.append(Paragraph(f"{mes:02d}/{ano}", styles['TituloPrincipal']))
        elements.append(Spacer(1, 15))
        
        elements.append(Paragraph("SALDOS BANCÁRIOS", styles['TituloSecao']))
        elements.append(criar_tabela_saldos(saldos, styles))
        elements.append(Spacer(1, 20))
        
        elements.append(Paragraph("NÃO CONFORMIDADES", styles['TituloSecao']))
        elements.append(criar_tabela_rncs(rncs, styles))
        
        data_geracao = datetime.now().strftime('%d/%m/%Y %H:%M')
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(f"Documento gerado em: {data_geracao}", styles['TextoCentralizado']))
        
        doc.build(elements)
        buffer.seek(0)
        
        print("✅ PDF gerado com sucesso!")
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'conciliacao_{mes:02d}_{ano}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"❌ Erro ao gerar PDF: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ==================== ROTA DE ZIP ====================

@app.route('/api/gerar-zip', methods=['GET'])
def gerar_zip():
    try:
        mes = request.args.get('mes')
        ano = request.args.get('ano')
        
        print(f"\n📦 Gerando ZIP para {mes}/{ano}")
        
        mes_pasta = f"{int(mes):02d}" if mes else None
        pasta_extratos = os.path.join(EXTRATOS_FOLDER, ano, mes_pasta) if mes_pasta else None
        
        memory_file = io.BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w') as zf:
            # Adicionar extratos se existirem
            if pasta_extratos and os.path.exists(pasta_extratos):
                extratos_adicionados = False
                for root, dirs, files in os.walk(pasta_extratos):
                    for file in files:
                        if file.endswith('.pdf'):
                            file_path = os.path.join(root, file)
                            zf.write(file_path, f'extratos/{file}')
                            extratos_adicionados = True
                            print(f"✅ Adicionado extrato: {file}")
                
                if not extratos_adicionados:
                    readme_content = f"Nenhum extrato encontrado para {mes}/{ano}.\n\nPara adicionar extratos, use o botão 'Importar Extratos'."
                    zf.writestr('extratos/LEIA-ME.txt', readme_content)
            else:
                readme_content = f"Pasta de extratos para {mes}/{ano}.\n\nNenhum extrato foi importado ainda.\nUse o botão 'Importar Extratos' para adicionar arquivos PDF."
                zf.writestr('extratos/LEIA-ME.txt', readme_content)
            
            # Gerar PDF
            db = load_data()
            mes_int = int(mes) if mes else 1
            ano_int = int(ano) if ano else 2026
            
            saldos = [s for s in db.get('saldos', []) if s['mes'] == mes_int and s['ano'] == ano_int]
            rncs = [r for r in db.get('rncs', []) if r['mes'] == mes_int and r['ano'] == ano_int]
            
            pdf_buffer = io.BytesIO()
            
            # Usar orientação landscape
            doc = SimpleDocTemplate(
                pdf_buffer, 
                pagesize=landscape(A4),
                leftMargin=15*mm,
                rightMargin=15*mm,
                topMargin=15*mm,
                bottomMargin=15*mm
            )
            
            elements = []
            styles = criar_estilos_pdf()
            
            # Adicionar logo se existir - redimensionada para caber na página
            logo_path = os.path.join(os.path.dirname(__file__), 'Logo.emf')
            if os.path.exists(logo_path):
                try:
                    # Definir tamanho máximo para a logo (100mm de largura)
                    max_width = 100*mm
                    
                    # Obter dimensões originais para manter proporção
                    img = ImageReader(logo_path)
                    img_width, img_height = img.getSize()
                    
                    # Calcular altura proporcional
                    scale = max_width / img_width
                    new_width = max_width
                    new_height = img_height * scale
                    
                    # Limitar altura máxima se necessário
                    max_height = 30*mm
                    if new_height > max_height:
                        scale = max_height / new_height
                        new_width = new_width * scale
                        new_height = max_height
                    
                    logo = Image(logo_path, width=new_width, height=new_height)
                    logo.hAlign = 'LEFT'  # Alinhar à esquerda
                    elements.append(logo)
                    elements.append(Spacer(1, 5))
                except Exception as e:
                    print(f"⚠️ Erro ao carregar logo: {e}")
            
            elements.append(Paragraph("Período de Vigência", styles['TituloPrincipal']))
            elements.append(Paragraph(f"{mes_int:02d}/{ano_int}", styles['TituloPrincipal']))
            elements.append(Spacer(1, 15))
            
            elements.append(Paragraph("SALDOS BANCÁRIOS", styles['TituloSecao']))
            elements.append(criar_tabela_saldos(saldos, styles))
            elements.append(Spacer(1, 20))
            
            elements.append(Paragraph("NÃO CONFORMIDADES", styles['TituloSecao']))
            elements.append(criar_tabela_rncs(rncs, styles))
            
            data_geracao = datetime.now().strftime('%d/%m/%Y %H:%M')
            elements.append(Spacer(1, 15))
            elements.append(Paragraph(f"Documento gerado em: {data_geracao}", styles['TextoCentralizado']))
            
            doc.build(elements)
            pdf_buffer.seek(0)
            zf.writestr(f'relatorio_{mes_int:02d}_{ano_int}.pdf', pdf_buffer.getvalue())
            print("✅ PDF adicionado ao ZIP")
        
        memory_file.seek(0)
        print("✅ ZIP gerado com sucesso!")
        
        return send_file(
            memory_file,
            as_attachment=True,
            download_name=f'conciliacao_{mes}_{ano}.zip',
            mimetype='application/zip'
        )
    except Exception as e:
        print(f"❌ Erro ao gerar ZIP: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 SISTEMA DE CONCILIAÇÃO BANCÁRIA - PWA")
    print("="*60)
    print(f"📁 DATA_FILE: {DATA_FILE}")
    print(f"📁 EXTRATOS_FOLDER: {EXTRATOS_FOLDER}")
    print(f"📁 O arquivo data.json existe? {os.path.exists(DATA_FILE)}")
    print("="*60)
    print("🌐 Servidor iniciado em: http://localhost:5000")
    print("📱 Modo PWA ativado - Instale como aplicativo")
    print("🛑 Pressione CTRL+C para parar")
    print("="*60)
    app.run(debug=True, port=5000)