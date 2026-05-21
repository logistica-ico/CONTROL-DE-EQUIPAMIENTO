import os
from flask_cors import CORS
from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.utils import secure_filename
import qrcode
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
from reportlab.lib.utils import simpleSplit

app = Flask(__name__)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'None'
app.config['REMEMBER_COOKIE_SECURE'] = True
CORS(app)
print("====================================")
print("¡ATENCIÓN! EL ARCHIVO REAL QUE ESTÁ CORRIENDO ES:")
print(os.path.abspath(__file__))
print("====================================")
app.config['SECRET_KEY'] = 'clave-secreta'

# CONFIGURACIÓN CORRECTA DE LA BASE DE DATOS
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventario.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads' 

# Inicializamos SQLAlchemy de manera limpia
db = SQLAlchemy()

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# MODELOS (Deben estar vinculados antes de crear las tablas)
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))

class Colaborador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    area = db.Column(db.String(100))
    dni = db.Column(db.String(20))
    equipos = db.relationship('Equipo', backref='responsable', lazy=True)

class Equipo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    serie = db.Column(db.String(50))
    foto_serie = db.Column(db.String(200)) 
    colaborador_id = db.Column(db.Integer, db.ForeignKey('colaborador.id'))

# Vinculamos la app con la base de datos de manera formal
db.init_app(app)

# CREACIÓN FORZADA AUTOMÁTICA (Para evitar que falle en el navegador)
with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(username='admin').first():
        db.session.add(Usuario(username='admin', password='123'))
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

@app.before_request
def inicializar_base_de_datos_urgente():
    # Solo se ejecuta una vez al arrancar
    db.create_all()
    try:
        if not Usuario.query.filter_by(username='admin').first():
            db.session.add(Usuario(username='admin', password='123'))
            db.session.commit()
    except Exception:
        db.session.rollback()
# RUTAS
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/')
@login_required
def index():
    colaboradores = Colaborador.query.all()
    equipos_libres = Equipo.query.filter_by(colaborador_id=None).all()
    return render_template('index.html', colaboradores=colaboradores, equipos_libres=equipos_libres)

@app.route('/agregar_colaborador', methods=['POST'])
@login_required
def agregar_colaborador():
    nombre = request.form['nombre']
    area = request.form['area']
    dni = request.form['dni']  
    
    nuevo_col = Colaborador(nombre=nombre, area=area, dni=dni)
    db.session.add(nuevo_col)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/agregar_equipo', methods=['POST'])
@login_required
def agregar_equipo():
    foto = request.files['foto']
    nombre_foto = None
    if foto:
        nombre_foto = secure_filename(foto.filename)
        foto.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_foto))
    
    nuevo = Equipo(nombre=request.form['nombre'], serie=request.form['serie'], foto_serie=nombre_foto)
    db.session.add(nuevo)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/asignar_equipo', methods=['POST'])
@login_required
def asignar_equipo():
    eq = Equipo.query.get(request.form['equipo_id'])
    eq.colaborador_id = request.form['colaborador_id']
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/desvincular/<int:equipo_id>')
@login_required
def desvincular(equipo_id):
    eq = Equipo.query.get(equipo_id)
    eq.colaborador_id = None
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/colaborador/<int:colaborador_id>/pdf')
@login_required
def generar_pdf(colaborador_id):
    col = Colaborador.query.get(colaborador_id)
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    
    ahora = datetime.now()
    fecha_entrega = ahora.strftime("%d/%m/%Y")
    hora_entrega = ahora.strftime("%H:%M")

    ruta_logo = os.path.join(app.root_path, 'static', 'logo.png')
    if os.path.exists(ruta_logo):
        c.drawImage(ruta_logo, 40, 715, width=65, height=50, preserveAspectRatio=True, mask='auto')

    c.setFont("Helvetica-Bold", 12)
    c.drawString(120, 750, "ACTA DE ASIGNACIÓN Y RESPONSABILIDAD DE EQUIPO TECNOLÓGICO")
    
    c.setFont("Helvetica", 9)
    c.drawString(120, 735, f"Fecha de entrega: {fecha_entrega}  |  Hora de entrega: {hora_entrega}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 690, "1. DATOS DEL COLABORADOR")
    c.setFont("Helvetica", 11)
    c.drawString(60, 675, f"Nombre completo: {col.nombre}")
    
    dni_texto = str(col.dni).strip() if col.dni else ""
    if dni_texto and dni_texto != "None":
        c.drawString(60, 660, f"DNI: {dni_texto}")
    else:
        c.drawString(60, 660, "DNI: ____________________")
        
    c.drawString(60, 645, f"Área / Oficina: {col.area}")
    c.line(50, 635, 550, 635)

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 620, "2. DETALLE DEL EQUIPAMIENTO")
    y = 605
    c.setFont("Helvetica", 10)
    for e in col.equipos:
        c.drawString(70, y, f"• {e.nombre} (Serie: {e.serie})")
        y -= 15

    y -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "3. RESPONSABILIDAD Y REPOSICIÓN:")
    y -= 14
    
    c.setFont("Helvetica", 10)
    txt3 = ("El colaborador que recibe el equipo, declara conocer y asume la responsabilidad del adecuado uso del "
            "equipo en mención, en casos de deterioro, extravío, pérdida o sustracción del equipo, el usuario será "
            "el único responsable para su reposición de igual o superior características, asimismo deberá comunicar "
            "el hecho en el momento del siniestro a su jefe inmediato, adjuntando la denuncia policial, así como iniciar "
            "los trámites hasta obtener la reposición del equipo. Asimismo, en el caso de que no lo reponga en el "
            "término de las 48 hours, el usuario o receptor autoriza automáticamente el descuento de su remuneración "
            "en planilla de haberes mensual u otra retribución económica, por el valor total del costo de reposición.")
    for linea in simpleSplit(txt3, "Helvetica", 10, 500):
        c.drawString(50, y, linea)
        y -= 13

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "4. CONFORMIDAD:")
    y -= 14
    
    c.setFont("Helvetica", 10)
    txt4 = "El colaborador en tal sentido, firma en señal de conformidad la presente acta habiendo verificado el buen estado del equipo."
    for linea in simpleSplit(txt4, "Helvetica", 10, 500):
        c.drawString(50, y, linea)
        y -= 13

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "5. OBLIGACIONES DEL USUARIO:")
    y -= 14
    
    c.setFont("Helvetica", 10)
    obligaciones = [
        "- Utilizar el equipo exclusivamente para funciones laborales de la empresa.",
        "- No instalar software sin licencia o programas ajenos a sus labores.",
        "- Devolver el equipo en las mismas condiciones recibidas al finalizar su vínculo laboral."
    ]
    for ob in obligaciones:
        if y < 100:
            c.showPage()
            y = 730
        c.drawString(50, y, ob)
        y -= 13

    y_firmas = 80
    c.line(80, y_firmas, 230, y_firmas)
    c.drawCentredString(155, y_firmas - 15, "Firma del Colaborador")
    
    c.line(370, y_firmas, 520, y_firmas)
    c.drawCentredString(445, y_firmas - 15, "Nombre del encargado, DNI y firma")

    c.save()
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', download_name=f"Acta_{col.nombre}.pdf")

@app.route('/editar_equipo/<int:equipo_id>', methods=['GET', 'POST'])
@login_required
def editar_equipo(equipo_id):
    eq = Equipo.query.get_or_404(equipo_id)
    if request.method == 'POST':
        eq.nombre = request.form['nombre']
        eq.serie = request.form['serie']
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('editar_equipo.html', eq=eq)

@app.route('/editar_colaborador/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_colaborador(id):
    col = Colaborador.query.get_or_404(id)
    if request.method == 'POST':
        col.nombre = request.form['nombre']
        col.area = request.form['area']
        col.dni = request.form['dni'] 
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('editar_colaborador.html', col=col)

@app.route('/ver/<int:equipo_id>')
def ver_equipo(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    return render_template('ver_equipo.html', equipo=equipo)

@app.route('/eliminar_colaborador/<int:colaborador_id>', methods=['POST'])
@login_required
def eliminar_colaborador(colaborador_id):
    col = Colaborador.query.get_or_404(colaborador_id)
    if len(col.equipos) > 0:
        return redirect(url_for('index'))
    db.session.delete(col)
    db.session.commit()
    return redirect(url_for('index'))    

@app.route('/equipo/<int:equipo_id>/qr')
@login_required
def generar_qr(equipo_id):
    # Cambiamos la IP vieja por tu dominio definitivo de Firebase
    url = f"https://control-de-equipamiento.web.app/ver/{equipo_id}"
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'None'
app.config['REMEMBER_COOKIE_SECURE'] = True

@app.after_request
def add_security_headers(response):
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://control-de-equipamiento.web.app;"
    if "X-Frame-Options" in response.headers:
        del response.headers["X-Frame-Options"]
    return response
# # ESTA SIEMPRE DEBE SER LA ÚLTIMA LÍNEA
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)