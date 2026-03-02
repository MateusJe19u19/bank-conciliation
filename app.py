from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON
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
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from werkzeug.utils import secure_filename

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
CORS(app)

# ==================== CONFIGURAÇÃO DO BANCO DE DADOS ====================
# Busca a URL do ambiente ou usa um valor padrão com tratamento de erro
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # Fallback para desenvolvimento - NÃO USE EM PRODUÇÃO
    DATABASE_URL = 'postgresql://bank_conciliation_db_user:UYuIrIbfcv9qC2HBF9dzqvEeQydqyWxK@dpg-d6isl8vgi27c73dib1kg-a:5432/bank_conciliation_db?sslmode=require'

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

print(f"📊 Conectando ao banco de dados: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'local'}")

# ==================== MODELOS DO BANCO DE DADOS ====================
class Saldo(db.Model):
    __tablename__ = 'saldos'
    id = db.Column(db.String(50), primary_key=True)
    banco = db.Column(db.String(50), nullable=False)
    empresa = db.Column(db.String(50), nullable=False)
    saldo_sagi = db.Column(db.Float, nullable=False)
    saldo_banco = db.Column(db.Float, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    averbacao = db.Column(db.String(200))
    data_registro = db.Column(db.String(50))

    def to_dict(self):
        return {
            'id': self.id,
            'banco': self.banco,
            'empresa': self.empresa,
            'saldo_sagi': self.saldo_sagi,
            'saldo_banco': self.saldo_banco,
            'mes': self.mes,
            'ano': self.ano,
            'averbacao': self.averbacao,
            'data_registro': self.data_registro
        }

class RNC(db.Model):
    __tablename__ = 'rncs'
    id = db.Column(db.String(50), primary_key=True)
    banco = db.Column(db.String(50), nullable=False)
    empresa = db.Column(db.String(50))
    data_rnc = db.Column(db.String(20), nullable=False)
    documento = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    pessoa = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.Text, nullable=False)
    correcao = db.Column(db.Text, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    expansoes = db.Column(db.JSON, default=[])
    data_registro = db.Column(db.String(50))

    def to_dict(self):
        return {
            'id': self.id,
            'banco': self.banco,
            'empresa': self.empresa,
            'data_rnc': self.data_rnc,
            'documento': self.documento,
            'valor': self.valor,
            'pessoa': self.pessoa,
            'tipo': self.tipo,
            'motivo': self.motivo,
            'correcao': self.correcao,
            'mes': self.mes,
            'ano': self.ano,
            'expansoes': self.expansoes if self.expansoes else [],
            'data_registro': self.data_registro
        }

# ==================== CONFIGURAÇÃO DE CAMINHOS ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXTRATOS_FOLDER = os.path.join(BASE_DIR, 'extratos')
ALLOWED_EXTENSIONS = {'pdf'}

# Garantir que a pasta de extratos exista
os.makedirs(EXTRATOS_FOLDER, exist_ok=True)

print("="*60)
print("🔍 INFORMAÇÕES DO SISTEMA")
print("="*60)
print(f"📁 Diretório atual: {os.getcwd()}")
print(f"📁 EXTRATOS_FOLDER: {EXTRATOS_FOLDER}")
print("="*60)

# ==================== FUNÇÕES AUXILIARES ====================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== FUNÇÕES DE FORMATAÇÃO PARA PDF ====================
def formatar_valor_pdf(valor):
    if valor < 0:
        return f"-R$ {abs(valor):,.2f}".replace('.', ',')
    else:
        return f"R$ {valor:,.2f}".replace('.', ',')

def criar_estilos_pdf():
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='TituloPrincipal',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#002060'),
        alignment=1,
        spaceAfter=10,
        spaceBefore=10
    ))
    
    styles.add(ParagraphStyle(
        name='TituloSecao',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor('#002060'),
        alignment=1,
        spaceAfter=15,
        spaceBefore=20
    ))
    
    styles.add(ParagraphStyle(
        name='TextoNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#002060'),
        alignment=0,
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
        alignment=1,
        spaceAfter=5
    ))
    
    return styles

def criar_tabela_saldos(saldos, styles):
    if not saldos:
        return Paragraph("Nenhum saldo registrado para este período.", styles['TextoCentralizado'])
    
    dados = [['Banco', 'Empresa', 'Saldo SAGI', 'Saldo Banco', 'Diferença']]
    
    for s in saldos:
        diferenca = s.saldo_banco - s.saldo_sagi
        
        linha = [
            Paragraph(s.banco, styles['TextoNormal']),
            Paragraph(s.empresa, styles['TextoNormal']),
            Paragraph(formatar_valor_pdf(s.saldo_sagi), styles['TextoNormal']),
            Paragraph(formatar_valor_pdf(s.saldo_banco), styles['TextoNormal']),
            Paragraph(formatar_valor_pdf(diferenca), styles['TextoNormal'])
        ]
        dados.append(linha)
    
    col_widths = [50*mm, 40*mm, 50*mm, 50*mm, 50*mm]
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
    if not rncs:
        return Paragraph("Nenhuma não conformidade registrada para este período.", styles['TextoCentralizado'])
    
    dados = [['Banco', 'Empresa', 'Data', 'Documento', 'Valor', 'Tipo', 'Motivo', 'Correção']]
    
    for r in rncs:
        try:
            data_rnc = r.data_rnc
            if 'T' in data_rnc:
                data_obj = datetime.fromisoformat(data_rnc.split('T')[0])
            else:
                data_obj = datetime.fromisoformat(data_rnc)
            data = data_obj.strftime('%d/%m/%Y')
        except:
            data = r.data_rnc[:10] if r.data_rnc else ''
        
        linha = [
            Paragraph(r.banco, styles['TextoNormal']),
            Paragraph(r.empresa or '', styles['TextoNormal']),
            Paragraph(data, styles['TextoNormal']),
            Paragraph(r.documento, styles['TextoNormal']),
            Paragraph(formatar_valor_pdf(r.valor), styles['TextoNormal']),
            Paragraph(r.tipo, styles['TextoNormal']),
            Paragraph(r.motivo, styles['TextoNormal']),
            Paragraph(r.correcao, styles['TextoNormal'])
        ]
        dados.append(linha)
    
    col_widths = [30*mm, 25*mm, 22*mm, 30*mm, 30*mm, 25*mm, 40*mm, 40*mm]
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

# ==================== CRIAR TABELAS NO BANCO ====================
with app.app_context():
    try:
        db.create_all()
        print("✅ Tabelas criadas/verificadas no banco de dados")
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        print("⚠️ Verifique a conexão com o banco de dados")

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
            
            novo_saldo = Saldo(
                id=str(int(datetime.now().timestamp() * 1000)),
                banco=data['banco'],
                empresa=data['empresa'],
                saldo_sagi=float(data['saldo_sagi']),
                saldo_banco=float(data['saldo_banco']),
                mes=int(data['mes']),
                ano=int(data['ano']),
                averbacao=data.get('averbacao', ''),
                data_registro=datetime.now().isoformat()
            )
            
            db.session.add(novo_saldo)
            db.session.commit()
            print("✅ Saldo salvo com sucesso!")
            return jsonify(novo_saldo.to_dict())
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar saldo: {e}")
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    else:  # GET
        try:
            mes = request.args.get('mes', type=int)
            ano = request.args.get('ano', type=int)
            print(f"\n📋 Buscando saldos para mês={mes}, ano={ano}")
            
            saldos_filtrados = Saldo.query.filter_by(mes=mes, ano=ano).all()
            print(f"✅ Encontrados {len(saldos_filtrados)} saldos")
            
            return jsonify([s.to_dict() for s in saldos_filtrados])
        except Exception as e:
            print(f"❌ Erro ao buscar saldos: {e}")
            return jsonify([]), 200

@app.route('/api/saldos/<id>', methods=['DELETE'])
def delete_saldo(id):
    try:
        print(f"\n🗑️ Deletando saldo ID: {id}")
        saldo = Saldo.query.get(id)
        if saldo:
            db.session.delete(saldo)
            db.session.commit()
            print("✅ Saldo deletado com sucesso!")
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Saldo não encontrado'}), 404
    except Exception as e:
        db.session.rollback()
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
            
            data_rnc = data['data_rnc']
            if 'T' in data_rnc:
                data_rnc = data_rnc.split('T')[0]
            
            data_parts = data_rnc.split('-')
            mes = int(data_parts[1])
            ano = int(data_parts[0])
            
            nova_rnc = RNC(
                id=str(int(datetime.now().timestamp() * 1000)),
                banco=data['banco'],
                empresa=data.get('empresa', ''),
                data_rnc=data_rnc,
                documento=data['documento'],
                valor=float(data['valor']),
                pessoa=data['pessoa'],
                tipo=data['tipo'],
                motivo=data['motivo'],
                correcao=data['correcao'],
                mes=mes,
                ano=ano,
                expansoes=[],
                data_registro=datetime.now().isoformat()
            )
            
            db.session.add(nova_rnc)
            db.session.commit()
            print("✅ RNC salva com sucesso!")
            return jsonify(nova_rnc.to_dict())
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao criar RNC: {e}")
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    else:  # GET
        try:
            mes = request.args.get('mes', type=int)
            ano = request.args.get('ano', type=int)
            print(f"\n📋 Buscando RNCs para mês={mes}, ano={ano}")
            
            rncs_filtradas = RNC.query.filter_by(mes=mes, ano=ano).all()
            print(f"✅ Encontradas {len(rncs_filtradas)} RNCs")
            
            return jsonify([r.to_dict() for r in rncs_filtradas])
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
        
        rnc = RNC.query.get(id)
        if not rnc:
            return jsonify({'error': 'RNC não encontrada'}), 404
        
        data_rnc = data['data_rnc']
        if 'T' in data_rnc:
            data_rnc = data_rnc.split('T')[0]
        
        if 'mes' not in data or 'ano' not in data:
            data_parts = data_rnc.split('-')
            mes = int(data_parts[1])
            ano = int(data_parts[0])
        else:
            mes = int(data['mes'])
            ano = int(data['ano'])
        
        rnc.banco = data['banco']
        rnc.empresa = data.get('empresa', '')
        rnc.data_rnc = data_rnc
        rnc.documento = data['documento']
        rnc.valor = float(data['valor'])
        rnc.pessoa = data['pessoa']
        rnc.tipo = data['tipo']
        rnc.motivo = data['motivo']
        rnc.correcao = data['correcao']
        rnc.mes = mes
        rnc.ano = ano
        
        db.session.commit()
        print("✅ RNC atualizada com sucesso!")
        return jsonify({'success': True, 'id': id})
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao atualizar RNC: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/rncs/<id>', methods=['DELETE'])
def delete_rnc(id):
    try:
        print(f"\n🗑️ Deletando RNC ID: {id}")
        rnc = RNC.query.get(id)
        if not rnc:
            return jsonify({'error': 'RNC não encontrada'}), 404
        
        db.session.delete(rnc)
        db.session.commit()
        print(f"✅ RNC {id} deletada com sucesso!")
        return jsonify({'success': True})
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao deletar RNC: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/rncs/<id>/expansoes', methods=['POST'])
def add_expansao(id):
    try:
        print(f"\n📝 Adicionando expansão à RNC ID: {id}")
        data = request.json
        
        rnc = RNC.query.get(id)
        if not rnc:
            return jsonify({'error': 'RNC não encontrada'}), 404
        
        if not rnc.expansoes:
            rnc.expansoes = []
        
        nova_expansao = {
            'id': str(int(datetime.now().timestamp() * 1000)),
            'solicitacao': data.get('solicitacao', ''),
            'data_sol': data.get('data_sol'),
            'setor': data.get('setor', ''),
            'data_dev': data.get('data_dev'),
            'devolutiva': data.get('devolutiva', ''),
            'status': data.get('status', 'Pendente')
        }
        
        expansoes_atuais = rnc.expansoes if rnc.expansoes else []
        novas_expansoes = expansoes_atuais + [nova_expansao]
        rnc.expansoes = novas_expansoes
        
        db.session.commit()
        print(f"✅ Expansão adicionada: {nova_expansao['id']}")
        return jsonify({'success': True})
            
    except Exception as e:
        db.session.rollback()
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
        
        saldos = Saldo.query.filter_by(mes=mes, ano=ano).all()
        rncs = RNC.query.filter_by(mes=mes, ano=ano).all()
        
        print(f"📊 Saldos: {len(saldos)}, RNCs: {len(rncs)}")
        
        buffer = io.BytesIO()
        
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
        
        # Logo
        logo_path = os.path.join(os.path.dirname(__file__), 'logo.png')
        if os.path.exists(logo_path):
            try:
                max_width = 100*mm
                img = ImageReader(logo_path)
                img_width, img_height = img.getSize()
                scale = max_width / img_width
                new_width = max_width
                new_height = img_height * scale
                max_height = 30*mm
                if new_height > max_height:
                    scale = max_height / new_height
                    new_width = new_width * scale
                    new_height = max_height
                
                logo = Image(logo_path, width=new_width, height=new_height)
                logo.hAlign = 'LEFT'
                elements.append(logo)
                elements.append(Spacer(1, 5))
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
            mes_int = int(mes) if mes else 1
            ano_int = int(ano) if ano else 2026
            
            saldos = Saldo.query.filter_by(mes=mes_int, ano=ano_int).all()
            rncs = RNC.query.filter_by(mes=mes_int, ano=ano_int).all()
            
            pdf_buffer = io.BytesIO()
            
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
            
            # Logo
            logo_path = os.path.join(os.path.dirname(__file__), 'logo.png')
            if os.path.exists(logo_path):
                try:
                    max_width = 100*mm
                    img = ImageReader(logo_path)
                    img_width, img_height = img.getSize()
                    scale = max_width / img_width
                    new_width = max_width
                    new_height = img_height * scale
                    max_height = 30*mm
                    if new_height > max_height:
                        scale = max_height / new_height
                        new_width = new_width * scale
                        new_height = max_height
                    
                    logo = Image(logo_path, width=new_width, height=new_height)
                    logo.hAlign = 'LEFT'
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

# ==================== CONFIGURAÇÃO PARA RENDER ====================
application = app

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 SISTEMA DE CONCILIAÇÃO BANCÁRIA")
    print("="*60)
    print(f"📁 EXTRATOS_FOLDER: {EXTRATOS_FOLDER}")
    print("="*60)
    print("🌐 Servidor iniciado em: http://localhost:5000")
    print("🛑 Pressione CTRL+C para parar")
    print("="*60)
    app.run(debug=True, port=5000)
