from flask import Flask, render_template, request, redirect, url_for, abort, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import os
import uuid
import json
import google.genai as genai
from google.genai import types
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Cm, Inches
import logging
from datetime import date

load_dotenv()

app = Flask(__name__)

app.config['WORD_TEMPLATE_FOLDER'] = 'word_templates'
app.config['GENERATED_REPORTS_FOLDER'] = 'generated_reports'
os.makedirs(app.config['GENERATED_REPORTS_FOLDER'], exist_ok=True)

logging.basicConfig(level=logging.INFO)

# --- CONFIGURACIÓN ---
# 1. Clave secreta para notificaciones flash
app.secret_key = os.getenv("SECRET_KEY")

# 2. Configuración de la carpeta de subidas
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) # Asegura que la carpeta exista

# 3. Configuración de la base de datos PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 4. Configuración de la API de Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

db = SQLAlchemy(app)

# --- MODELOS DE LA BASE DE DATOS ---

class Clase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    mantenimientos = db.relationship('Mantenimiento', backref='clase', lazy=True)

class Mantenimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(50), nullable=False)
    locacion = db.Column(db.String(100), nullable=False)
    detalle_mantenimiento_usuario = db.Column(db.Text, nullable=True)
    detalle_mantenimiento_sistema = db.Column(db.Text, nullable=True)
    informacion_estructurada = db.Column(db.Text, nullable=True)
    autor = db.Column(db.String(100), nullable=True)
    supervisor = db.Column(db.String(100), nullable=True)
    tipo_mantenimiento = db.Column(db.String(50), nullable=False)
    descripcion_activo = db.Column(db.String(200), nullable=False)
    codigo_mantenimiento = db.Column(db.String(100), nullable=False)
    mes_programado = db.Column(db.Integer, nullable=False)
    fecha_realizacion = db.Column(db.Date, nullable=True)
    estado = db.Column(db.String(50), nullable=False, default='Programado')
    clase_id = db.Column(db.Integer, db.ForeignKey('clase.id'), nullable=False)
    evidencias = db.relationship('Evidencia', backref='mantenimiento', lazy=True, cascade="all, delete-orphan")
    nombre_archivo_reporte = db.Column(db.String(255), nullable=True)

class Evidencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    mantenimiento_id = db.Column(db.Integer, db.ForeignKey('mantenimiento.id'), nullable=False)


# --- RUTAS DE LA APLICACIÓN ---

MESES = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
AREAS = ["Mecánica", "Gasfitería", "Instrumentación"]

@app.route('/')
def index():
    mes_filtrado = request.args.get('mes', type=int)
    area_filtrada = request.args.get('area', type=str)
    query = Mantenimiento.query.order_by(Mantenimiento.fecha_realizacion.desc().nulls_last(), Mantenimiento.id.desc())
    if mes_filtrado:
        query = query.filter(Mantenimiento.mes_programado == mes_filtrado)
    if area_filtrada:
        query = query.filter(Mantenimiento.area == area_filtrada)
    
    lista_mantenimientos = query.all()
    return render_template(
        "index.html", 
        mantenimientos=lista_mantenimientos, 
        meses=MESES, 
        mes_seleccionado=mes_filtrado,
        areas=AREAS,
        area_seleccionada=area_filtrada
    )

# ... (Las rutas /nuevo, /mantenimiento/<id> no cambian) ...
@app.route('/nuevo')
def nuevo_reporte():
    clases = Clase.query.order_by(Clase.nombre).all()
    return render_template("nuevo_reporte.html", meses=MESES, clases=clases)

@app.route('/mantenimiento/<int:id>')
def mantenimiento_detalle(id):
    mantenimiento = Mantenimiento.query.get_or_404(id)
    clases = Clase.query.order_by(Clase.nombre).all()
    return render_template("mantenimiento_detalle.html", mantenimiento=mantenimiento, meses=MESES, clases=clases)

@app.route('/guardar', methods=['POST'])
def guardar():
    mantenimiento_id = request.form.get('id')
    
    area = request.form.get('area')
    clase_id = request.form.get('clase_id', type=int)
    tipo_mantenimiento = request.form.get('tipo_mantenimiento')
    locacion = request.form.get('locacion')
    descripcion_activo = request.form.get('descripcion_activo')
    codigo_mantenimiento = request.form.get('codigo_mantenimiento')
    detalle_usuario = request.form.get('detalle_mantenimiento')
    detalle_sistema = request.form.get('detalle_sistema')
    informacion_estructurada = request.form.get('informacion_estructurada')
    autor = request.form.get('autor')
    supervisor = request.form.get('supervisor')
    mes_programado = request.form.get('mes_programado', type=int)
    fecha_str = request.form.get('fecha_realizacion')
    fecha_realizacion = db.func.to_date(fecha_str, 'YYYY-MM-DD') if fecha_str else None
    estado = request.form.get('estado')

    if mantenimiento_id:
        mant = Mantenimiento.query.get(mantenimiento_id)
        if not mant: return "Mantenimiento no encontrado", 404
        mant.area = area
        mant.clase_id = clase_id
        mant.tipo_mantenimiento = tipo_mantenimiento
        mant.locacion = locacion
        mant.descripcion_activo = descripcion_activo
        mant.codigo_mantenimiento = codigo_mantenimiento
        mant.detalle_mantenimiento_usuario = detalle_usuario 
        mant.detalle_mantenimiento_sistema = detalle_sistema
        mant.informacion_estructurada = informacion_estructurada
        mant.autor = autor
        mant.supervisor = supervisor
        mant.mes_programado = mes_programado
        mant.fecha_realizacion = fecha_realizacion
        mant.estado = estado
        flash(f"Mantenimiento #{mant.id} actualizado con éxito.", "success")
    else:
        nuevo_mant = Mantenimiento(
            area=area,
            clase_id=clase_id, tipo_mantenimiento=tipo_mantenimiento, locacion=locacion,
            descripcion_activo=descripcion_activo, codigo_mantenimiento=codigo_mantenimiento,
            detalle_mantenimiento_usuario=detalle_usuario, detalle_mantenimiento_sistema=detalle_sistema,
            informacion_estructurada=informacion_estructurada, autor=autor, supervisor=supervisor,
            mes_programado=mes_programado, fecha_realizacion=fecha_realizacion, estado=estado
        )
        db.session.add(nuevo_mant)
        db.session.flush()
        mant = nuevo_mant
        flash(f"Nuevo mantenimiento #{mant.id} creado con éxito.", "success")

    evidencias = request.files.getlist("evidencias")
    for img in evidencias:
        if img.filename:
            original_filename = secure_filename(img.filename)
            _, ext = os.path.splitext(original_filename)
            unique_prefix = uuid.uuid4().hex
            nuevo_nombre_archivo = f"{unique_prefix}{ext.lower()}"
            img.save(os.path.join(app.config['UPLOAD_FOLDER'], nuevo_nombre_archivo))
            nueva_evidencia = Evidencia(nombre_archivo=nuevo_nombre_archivo, mantenimiento_id=mant.id)
            db.session.add(nueva_evidencia)

    db.session.commit()
    return redirect(url_for('mantenimiento_detalle', id=mant.id))

# ... (Las rutas de eliminación no cambian) ...
@app.route('/mantenimiento/eliminar/<int:id>', methods=['POST'])
def eliminar_mantenimiento(id):
    mant = Mantenimiento.query.get_or_404(id)
    for evidencia in mant.evidencias:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], evidencia.nombre_archivo))
        except OSError as e:
            print(f"Error eliminando archivo {evidencia.nombre_archivo}: {e}")
            
    db.session.delete(mant)
    db.session.commit()
    flash(f"Mantenimiento #{id} y sus evidencias han sido eliminados.", "success")
    return redirect(url_for('index'))

@app.route('/evidencia/eliminar/<int:id>', methods=['POST'])
def eliminar_evidencia(id):
    evidencia = Evidencia.query.get_or_404(id)
    
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], evidencia.nombre_archivo))
    except OSError as e:
        flash(f"Error al eliminar el archivo físico: {e}", "danger")
        return {"error": str(e)}, 500

    db.session.delete(evidencia)
    db.session.commit()
    flash("Evidencia eliminada correctamente.", "success")
    return {"success": True}

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- RUTAS PARA LA INTEGRACIÓN CON IA ---

def call_gemini_api(prompt):
    """Función helper para llamar a la API de Gemini usando el objeto Client."""
    if not client:
        raise Exception("El cliente de la API de Gemini no está configurado. Revisa tu GEMINI_API_KEY.")
    
    model_name = "gemini-2.5-flash-lite"
    
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )
    ]
    
    generation_config_obj = types.GenerateContentConfig(
        response_mime_type="application/json"
    )

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=generation_config_obj
    )
    
    return response.text

@app.route('/generar/detalle-sistema', methods=['POST'])
def generar_detalle_sistema_ia():
    data = request.json
    clasificacion = data.get('clasificacion', 'general')
    tipo = data.get('tipo', 'preventivo')
    activo = data.get('activo', 'N/A')
    actividades = data.get('actividades_usuario', '')
    locacion = data.get('locacion', 'N/A') 

    if not actividades:
        return jsonify({"error": "El detalle del mantenimiento del usuario no puede estar vacío."}), 400

    # --- TU PROMPT ORIGINAL (prompt_1) ---
    prompt = f"""
Como experto en el area de mantenimiento, estas encargado de dar forma a una lista de actividades
que realizaron los trabajadores para un mantenimiento especifico en {activo} el tipo de mantenimiento
realizado es {tipo} y el area al que pertenece el manteniniento es {clasificacion}, tu trabajo es a
partir de la siguiente lista de actividades ingresadas por el trabajador, devolver una lista ordenada
y con el formato adecuado siendo detallado y asegurandote que las actividades calzen con el
mantenimiento realizado en {locacion}

Actividades realizadas por el trabajador
{actividades}

El resultado debe estar contenido en la variable 'strResultado' de un json valido como un solo bloque de texto
El resultado tambien es una lista de actividades sin numeracion ordanadas de inicio a fin del mantenimiento
como una serie de pasos, como en el siguiente ejemplo:

En coordinación con operador de producción se paró funcionamiento de motor para realizar mantenimiento.
Se freno aceite de sistema.
Se realizo limpieza e inspección interna de líneas de lubricación, juego de biela, colector de aceite y desgaste en piñón helicoidal.
Se fabricaron empaquetaduras nuevas de tapas de inspección.
Se llenó 2 galones de aceite SAE 40.
Se instalo filtro de aceite nuevo.
Se realizo regulación de ángulo de aceleración en sistema de control de velocidad.
Se realizo inspección y limpieza de contactos de sistema de encendido Star fire.
Se realizo calibrarlas de válvulas y fabricó empaque nuevo en tapa de balancines.
Se realizo inspección, lubricación y regulación de embrague.
Se realizo limpieza externa de motor.

Puedes agregar pasos intermedios siempre y cuando sean necesarios y la lista original lo requiera
Agrega en caso sea posible la coordinacion con el area que puede ser de mantenimiento o produccion al inicio
Cada paso de la lista de actividades no debe se muy larga, son oraciones concisas y cada oracion va en una nueva linea
Las unicas areas existentes son mantenimiento, produccion y seguridad no existen mas para elegir.
Nautilus es un area que solo es supervisada con mantenimiento.
"""
    try:
        response_text = call_gemini_api(prompt)
        response_json = json.loads(response_text)
        detalle_generado = response_json.get("strResultado", "Error: La IA no devolvió la clave 'strResultado'.")
        return jsonify({"detalle": detalle_generado})
    except Exception as e:
        app.logger.error(f"Error en generar_detalle_sistema_ia: {e}")
        return jsonify({"error": f"Error al comunicarse con la IA: {str(e)}"}), 500

@app.route('/generar/info-estructurada', methods=['POST'])
def generar_info_estructurada_ia():
    data = request.json
    clasificacion = data.get('clasificacion', 'general')
    tipo = data.get('tipo', 'preventivo')
    activo = data.get('activo', 'N/A')
    codigo = data.get('codigo', 'N/A')
    detalle_sistema = data.get('detalle_sistema', '') # Esto es el strResultado1 de tu script

    if not detalle_sistema:
        return jsonify({"error": "El detalle del sistema generado por IA no puede estar vacío."}), 400

    # --- TU PLANTILLA JSON ORIGINAL (json_base) ---
    json_base_plantilla = """
    {
      "strTituloDocumento": "nombre del documento word, debe ser representativo, por ejemplo: INFORME de mantenimiento EA12813 (7200H) o similar",
      "strTituloMantenimiento": "nombre del mantenimiento especifico, por ejemplo: INFORME DE MANTENIMIENTO PREVENTIVO MOTOR AJAX EA-22",
      "strActividad": "actividad especifica, por ejemplo: Mantenimiento preventivo de 7200 horas.",
      "strAlcance": "alcance del trabajo, por ejemplo: Realizar mantenimiento preventivo de 7200 horas y ejecutar mantenimiento correctivo si es necesario.",
      "strEstado": "como se encontro el activo, por ejemplo: El motor se encontraba operativo en el pozo. Se coordinó con el área de producción para su parada y posterior intervención, con el fin de ejecutar el mantenimiento preventivo programado.",
      "strEstadoEquipo": "estado especifico del equipo o componente, ejemplo: Se verifica estado de geomembrana de tina. Requiere reparar., •	El equipo se encontraba en condiciones operativas antes de iniciar el mantenimiento. No se reportaron fallas previas a la intervención.",
      "listTrabajosPrevios": ["lista de trabajos previos, ejemplo: Coordinar con producción la puesta fuera de servicio del motor.,Preparar herramientas, insumos y repuestos para el mantenimiento.,Realizar inspección visual externa del equipo antes de la intervención., •	Realizar inspección visual de equipo., •	Preparar herramientas, insumos y repuestos para el mantenimiento."],
      "listActividades":[ "lista de sub actividades en el siguiente formato, se mas detallado con cada paso o actividad, es decir agrega mas sub actividades para detallar sin perder coeherencia"
        {
          "strSubActividad": "actividad que engloba un conjunto de pasos, ejemplo: MANTENIMIENTO PREVENTIVO DE 7200 HORAS MOTOR., MANTENIMIENTO PREVENTIVO DE CONTROLADOR PLUNGER LIFT (PLC  24  VDC)."
          "listSubActividad": [
            "lista de pasos o actividades que pertenecen a esa categoria ejemplo:
            DRENAJE E INSPECCIÓN DE CARTER.
            Se realizó el drenaje completo del aceite del carter.
            Se realizó una inspección visual de los componentes móviles internos (cigüeñal, bielas), sin encontrar anomalías evidentes.
            Se efectuó la limpieza interna del carter para remover sedimentos.

            INSPECCIÓN DE SISTEMA DE IGNICIÓN.
            Se verificó el estado del sistema de encendido.
            Se realizó la limpieza de contactos para asegurar una correcta operación.

            INSPECCIÓN Y AJUSTE EN SISTEMA DE CONTROL DE VELOCIDAD.
            Se verificó el funcionamiento y se realizó la regulación del sistema de control de ralentí.

            en caso quieras un encabezado, ponlo en mayusculas como parte de la lista de cada uno como en DRENAJE E INSPECCIÓN DE CARTER., pero todo en una lista
            "
          ]
        },
        {
        "strSubActividad": MANTENIMIENTO PREVENTIVO A VALVULA MOTORA ALTA PRESION 2” KIMRAY 2200 SMT  PC.,
        "listSubActividad": [...]
        }
    ],
      "listConclusiones":[
        "lista de conclusiones"
      ]
    }
    """

    # --- TU PROMPT ORIGINAL (prompt_2) ---
    prompt = f"""
como experto en el area de mantenimiento tienes una lista de actividades realizadas
por los trabajadores:
{detalle_sistema}
para un mantenimiento del area {clasificacion}, siendo el mantenimiento del tipo {tipo}
sobre el activo {activo}, tu trabajo es estructurar esta informacion en un reporte completo
del area respectiva para poder hacer la documentacion correspondiente, para esto debes seguir las reglas:
1. Estructura del resultado:
 {json_base_plantilla}
2. Datos:
  usa como base los datos del contexto previo y para mas informacion puedes usar este codigo {codigo} que esta vinculado al mantenimiento
  para poder darle mas contexto al contenido del informe
3. Areas:
  Las unicas areas existentes son mantenimiento, produccion y seguridad no existen mas areas para elegir.
"""
    try:
        response_text = call_gemini_api(prompt)
        response_json = json.loads(response_text)
        info_generada = json.dumps(response_json, indent=2)
        return jsonify({"info": info_generada})
    except Exception as e:
        app.logger.error(f"Error en generar_info_estructurada_ia: {e}")
        return jsonify({"error": f"Error al comunicarse con la IA: {str(e)}"}), 500

@app.route('/generar-reporte-word/<int:id>', methods=['POST'])
def generar_reporte_word(id):
    mant = Mantenimiento.query.get_or_404(id)

    if not all([mant.informacion_estructurada, mant.autor, mant.supervisor, mant.fecha_realizacion]):
        return jsonify({"error": "Faltan datos clave (Info. Estructurada, Autor, Supervisor o Fecha)."}), 400

    try:
        # Si ya existe un reporte, lo eliminamos del sistema de archivos.
        if mant.nombre_archivo_reporte:
            ruta_antigua = os.path.join(app.config['GENERATED_REPORTS_FOLDER'], mant.nombre_archivo_reporte)
            if os.path.exists(ruta_antigua):
                os.remove(ruta_antigua)

        template_path = os.path.join(app.config['WORD_TEMPLATE_FOLDER'], 'plantilla_mantenimiento.docx')
        tpl = DocxTemplate(template_path)

        context = json.loads(mant.informacion_estructurada)
        context['locacion'] = mant.locacion
        context['autor'] = mant.autor
        context['supervisor'] = mant.supervisor
        context['fecha_ejecucion'] = mant.fecha_realizacion.strftime('%d-%m-%Y')
        context['fecha_emision'] = date.today().strftime('%d-%m-%Y')

        lista_imagenes = []
        for evidencia in mant.evidencias:
            path_img = os.path.join(app.config['UPLOAD_FOLDER'], evidencia.nombre_archivo)
            if os.path.exists(path_img):
                img = InlineImage(tpl, path_img, height=Cm(5))
                lista_imagenes.append(img)
        context['evidencias'] = lista_imagenes

        tpl.render(context, autoescape=True)

        # --- CAMBIO: Volvemos a un nombre de archivo simple y predecible para el almacenamiento ---
        nombre_archivo_almacenado = f"reporte_mantenimiento_{id}.docx"
        
        ruta_guardado = os.path.join(app.config['GENERATED_REPORTS_FOLDER'], nombre_archivo_almacenado)
        tpl.save(ruta_guardado)
        
        mant.nombre_archivo_reporte = nombre_archivo_almacenado
        db.session.commit()

        return jsonify({"success": True, "filename": nombre_archivo_almacenado, "message": "Reporte generado/actualizado con éxito."})

    except json.JSONDecodeError:
        return jsonify({"error": "La información estructurada no es un JSON válido."}), 500
    except Exception as e:
        app.logger.error(f"Error generando reporte para ID {id}: {e}")
        return jsonify({"error": f"Error inesperado al generar el documento: {str(e)}"}), 500


@app.route('/descargar-reporte/<filename>')
def descargar_reporte(filename):
    # --- LÓGICA MEJORADA PARA CAMBIAR EL NOMBRE AL DESCARGAR ---
    
    # 1. Buscar el mantenimiento que corresponde a este nombre de archivo
    mant = Mantenimiento.query.filter_by(nombre_archivo_reporte=filename).first_or_404()
    
    nombre_descarga = filename # Nombre por defecto si algo falla

    # 2. Intentar obtener el nombre descriptivo del JSON
    if mant.informacion_estructurada:
        try:
            data = json.loads(mant.informacion_estructurada)
            titulo_documento = data.get('strTituloDocumento')
            
            if titulo_documento:
                # Sanear el título y añadirle la extensión .docx
                nombre_descarga = f"{secure_filename(titulo_documento)}.docx"
        except (json.JSONDecodeError, TypeError):
            # Si el JSON es inválido o no es un string, usamos el nombre por defecto
            app.logger.warning(f"No se pudo parsear el JSON para el reporte {filename}. Usando nombre de archivo por defecto.")
            pass

    # 3. Servir el archivo desde el disco, pero decirle al navegador que use el nuevo nombre_descarga
    return send_from_directory(
        directory=app.config['GENERATED_REPORTS_FOLDER'],
        path=filename,
        download_name=nombre_descarga, # ¡Esta es la magia!
        as_attachment=True
    )


# --- COMANDOS CLI PARA INICIALIZAR LA BD ---
@app.cli.command("init-db")
def init_db_command():
    """Crea las tablas de la base de datos y datos iniciales."""
    with app.app_context():
        db.create_all()
        if not Clase.query.first():
            clases_iniciales = [
                "EQUIPOS EN BATERÍAS", "MOTORES DE GAS", "UNIDAD DE BOMBEO MECANICO", "EQUIPOS PL GL",
                "GENERACIÓN ELÉCTRICA", "GASODUCTO", "TANQUES", "SISTEMA DE PAT",
                "TANQUE DE FISCALIZACIÓN", "PLANTA DE INYECCIÓN DE AGUA"
            ]
            for nombre_clase in clases_iniciales:
                db.session.add(Clase(nombre=nombre_clase))
            db.session.commit()
        print("Base de datos inicializada.")

if __name__ == "__main__":
    app.run(debug=True)