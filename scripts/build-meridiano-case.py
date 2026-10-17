#!/usr/bin/env python3
"""Author a deterministic, fictional logistics project, never its report outputs.

Only YAML, PNG evidence and inert scanner/annex inputs are written here. Report
documents must be produced later by report-gen's registered exporters.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import sys
import textwrap
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import attachments
import capture_inbox
import cvss
import engine
import finding_imports
import validate
import workflows
import yaml
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

CASE = 'MERIDIANO-LOGISTICA-2026'
DATE = '2026-10-16'
NAMESPACE = uuid.UUID('2b1965db-26ba-5b67-8287-677b8616ba36')
WARNING = 'CASO FICTICIO: organización, personas, activos y resultados inventados; no hubo pruebas contra sistemas reales.'
PRIVATE_MARKER = 'MERIDIANO_PRIVATE_INBOX_DO_NOT_PUBLISH_2026'
REDACTION_MARKER = 'MERIDIANO_SYNTHETIC_REDACTION_CANARY_2026'
METADATA_MARKER = 'MERIDIANO_PRIVATE_IMAGE_METADATA_2026'
UNLINKED_MARKER = 'MERIDIANO_PRIVATE_UNLINKED_7D42'
LONG_URL = ('https://docs.meridiano.example/operaciones/conciliacion-de-contratos-multimodales/'
            'version-2026-10-16/expediente-0123456789abcdef0123456789abcdef0123456789abcdef'
            '?transportista=TRANS%2D42&moneda=CLP&idioma=pt-BR#revisão-açaí-ñ')

# Name, host, documentation IPv4, type, fictional owner.
ASSETS = [
    ('Portal de clientes', 'clientes.meridiano.example', '192.0.2.10', 'web', 'Experiencia de clientes'),
    ('Planificador de rutas', 'rutas.meridiano.example', '192.0.2.11', 'api', 'Operaciones terrestres'),
    ('Gestión de almacenes', 'almacen.meridiano.example', '192.0.2.12', 'web', 'Operaciones de bodega'),
    ('Escáner móvil de entregas', 'movil.meridiano.example', '192.0.2.13', 'mobile', 'Última milla'),
    ('Identidad de empleados', 'identidad.meridiano.example', '192.0.2.14', 'identity', 'Identidad y acceso'),
    ('Facturación y notas de crédito', 'facturas.meridiano.example', '192.0.2.15', 'api', 'Finanzas'),
    ('Trabajador de pagos a transportistas', 'pagos.meridiano.example', '198.51.100.20', 'host', 'Tesorería'),
    ('Intercambio documental EDI', 'edi.meridiano.example', '198.51.100.21', 'api', 'Integraciones'),
    ('Custodia de manifiestos', 'documentos.meridiano.example', '198.51.100.22', 'cloud', 'Datos y documentos'),
    ('Pasarela de dispositivos de frío', 'frio.meridiano.example', '198.51.100.23', 'host', 'Cadena de frío'),
    ('Directorio de soporte', 'directorio.meridiano.example', '198.51.100.24', 'directory', 'Plataforma'),
    ('Estación de administración', 'salto.meridiano.example', '198.51.100.25', 'host', 'Plataforma'),
    ('Observabilidad de operaciones', 'eventos.meridiano.example', '203.0.113.30', 'logging', 'Detección y respuesta'),
    ('Portal de proveedores', 'terceros.meridiano.example', '203.0.113.31', 'third-party', 'Gestión de terceros'),
    ('Orquestador de recuperación', 'recuperacion.meridiano.example', '203.0.113.32', 'host', 'Continuidad'),
    ('Catálogo de datos y conservación', 'catalogo.meridiano.example', '203.0.113.33', 'cloud', 'Gobierno de datos'),
]

# Title, asset, severity, CWE, root cause, condition, consequence, correction.
FINDINGS = [
    ('Autorización cruzada al reasignar una expedición', 1, 'critical', 'CWE-862', 0,
     'El planificador valida que la identidad puede editar rutas, pero no que la expedición pertenezca al contrato que administra. Dos organizaciones inventadas comparten un catálogo de destinos. El identificador de ruta válido no demuestra permiso sobre cada expedición asociada.',
     'La condición modelada permitiría reasignar una carga ajena o divulgar su destino. No se han movido mercancías ni consultado rutas reales.',
     'Resolver el recurso bajo el contexto organizacional del servidor y autorizar cada expedición antes de modificar la ruta; rechazar el lote completo cuando falle una precondición.'),
    ('Restauración de paquetes sin comprobar la identidad de sus bytes', 14, 'critical', 'CWE-494', 3,
     'La recuperación del escenario identifica paquetes por nombre y fecha. Dos contenidos inertes distintos pueden ocupar el mismo nombre. La aprobación del catálogo no vincula la revisión exacta de configuración y dependencias que se restauraría.',
     'Una reapertura podría incorporar configuración no aprobada y modificar permisos o destinos de integración. El caso no descarga ni ejecuta paquetes.',
     'Vincular cada paquete y dependencia con hash, versión y aprobación; verificar el manifiesto antes de restaurar y conservar una salida de error que impida la reapertura parcial.'),
    ('Cuenta de soporte con delegación administrativa heredada', 10, 'critical', 'CWE-269', 0,
     'Una cuenta sintética de inventario hereda derechos sobre grupos de administración a través de una unidad organizativa. La matriz de permisos distingue lectura, modificación de atributos y control de pertenencia, pero el rol efectivo combina las tres capacidades.',
     'El rol de menor confianza podría modificar una frontera administrativa dentro del modelo. No se accedió a un directorio ni se capturaron credenciales.',
     'Separar inventario y administración, revisar herencia y propietarios y comprobar con una identidad restringida tanto los atributos permitidos como las modificaciones que deben rechazarse.'),
    ('Pago duplicado por reintento con identificador de transporte nuevo', 6, 'high', 'CWE-362', 2,
     'La maqueta de liquidación identifica cada mensaje recibido, pero no la obligación comercial que representa. Después de perderse una confirmación, el reintento conserva factura y transportista y obtiene un identificador de transporte diferente.',
     'La secuencia ficticia podría registrar dos pagos para una sola obligación. Los valores son simbólicos y no existe conexión financiera.',
     'Definir una clave de idempotencia por obligación y transición; evaluar su unicidad de forma atómica con el asiento y devolver un resultado recuperable ante reintentos.'),
    ('Cambio de cuenta de proveedor sin aprobación independiente', 13, 'high', 'CWE-841', 0,
     'El solicitante ficticio modifica el destino de pago y aprueba el cambio desde otra interfaz. La política diferencia web y móvil, pero ambos canales resuelven el mismo sujeto. Una aprobación previa permanece cuando se altera el beneficiario.',
     'La separación aparente de funciones no impediría modificar un dato de alto impacto sin una segunda identidad autorizada. No hay cuentas bancarias reales.',
     'Separar por sujeto y función; invalidar aprobaciones ante cambios del destinatario y exigir una nueva revisión vinculada al contenido exacto.'),
    ('Comprobantes móviles conservados al cambiar de conductor', 3, 'high', 'CWE-922', 1,
     'La aplicación modelada almacena comprobantes en una caché del dispositivo. Al cerrar sesión y entrar con otra identidad, la pantalla sin conexión puede recuperar la última expedición del conductor anterior.',
     'La reutilización de un terminal podría exponer información de una entrega ajena. Las imágenes y direcciones del ejemplo son inventadas.',
     'Cifrar y separar el contenido por identidad, eliminar caché al retirar permisos y verificar cambio de usuario, reinicio del proceso y modo sin conexión.'),
    ('Revocación de credencial de integración no aplicada en la cola', 7, 'high', 'CWE-613', 0,
     'La recepción EDI autoriza un mensaje y guarda la decisión. Un trabajador posterior procesa esa autorización después de revocarse el contrato de integración. La maqueta usa un reloj fijo y no atribuye una duración real a la ventana.',
     'El modelo permitiría cambios documentales después de retirar el acceso del tercero. No demuestra que los mensajes previos deban cancelarse siempre: esa semántica requiere un contrato explícito.',
     'Versionar el mandato y reevaluar su vigencia en el consumo. Documentar qué operaciones ya aceptadas pueden completarse y cuáles necesitan cancelación idempotente.'),
    ('Manifiesto descargable mediante enlace duradero tras la revocación', 8, 'high', 'CWE-284', 1,
     'El enlace de un manifiesto sintético sigue resolviendo después de retirar a su destinatario del contrato. La caducidad del vínculo y la del permiso pertenecen a registros independientes sin reconciliación.',
     'La documentación modelada permanecería accesible fuera del plazo de autorización. No se presupone exposición pública de otros objetos.',
     'Aplicar vigencia corta y revocación por vínculo; comprobar permiso actual antes de servir cada versión del documento y registrar motivo de cualquier extensión.'),
    ('Corrección de factura sin vínculo con el estado de liquidación', 5, 'high', 'CWE-840', 2,
     'La nota de crédito del escenario puede cambiar el total de una factura mientras un pago ya preparado conserva el importe anterior. Cada servicio valida su propio estado, pero falta una versión compartida de la obligación.',
     'La carrera ficticia generaría conciliación incorrecta y trabajo manual para explicar saldos. No hay importes de clientes ni asientos reales.',
     'Vincular factura, ajuste y pago a una versión de obligación; rechazar transiciones incompatibles y definir compensación trazable para fallos parciales.'),
    ('Restauración reintroduce accesos de transportistas retirados', 14, 'high', 'CWE-863', 3,
     'Una copia anterior contiene ACL de un proveedor cuyo acceso se retiró después. El guion restaura archivos y permisos, pero no el registro posterior de revocaciones. La lectura del archivo se marca como recuperación completa.',
     'Reabrir el servicio podría reactivar permisos que el negocio ya había retirado. Disponibilidad de bytes no implica recuperación de política.',
     'Restaurar contenido y restricciones como una unidad, reconciliar revocaciones posteriores y bloquear la reapertura hasta verificar accesos autorizados y rechazados.'),
    ('Lotes de exportación omiten el filtro organizacional de la vista', 0, 'high', 'CWE-639', 0,
     'La pantalla individual usa el contrato activo del servidor, mientras el exportador de expediciones recibe un filtro opcional del cliente. Un lote sintético mixto conserva una fila perteneciente a otra organización.',
     'La inconsistencia del modelo permitiría divulgar parte del inventario de otro cliente. No se extrapola a todos los recursos.',
     'Reutilizar el mismo predicado de autorización en detalle, búsqueda y exportación; probar lotes mixtos, vacíos y recursos retirados durante la ejecución.'),
    ('Referencia EDI ambigua cuando un socio reutiliza números de orden', 7, 'medium', 'CWE-20', 2,
     'Dos socios inventados envían la misma referencia de orden y el importador la interpreta como identidad global. El contenido conserva el identificador del socio, pero la resolución posterior usa sólo el número comercial.',
     'La ambigüedad podría asociar un documento a una expedición incorrecta. La importación sintética no proviene de un escáner ni de un sistema EDI real.',
     'Definir identidad compuesta de socio, contrato, tipo y referencia; rechazar ambigüedades explícitamente y conservar los campos originales como procedencia.'),
    ('Lecturas de frío tardías sobrescriben una muestra más reciente', 9, 'medium', 'CWE-682', 2,
     'La pasarela modelada ordena por llegada de mensajes y no por secuencia del dispositivo. Un reintento atrasado reemplaza la lectura vigente, aunque conserva una fecha anterior. No se miden temperaturas físicas.',
     'El estado mostrado podría describir otro momento de la cadena y confundir una revisión de operación. El guion no afirma deterioro de mercancía.',
     'Separar tiempo de medición, recepción y secuencia; conservar historial y declarar explícitamente muestras tardías, duplicadas y de reloj no confiable.'),
    ('Redacción de soporte omite un identificador en mensajes anidados', 12, 'medium', 'CWE-532', 4,
     'La regla de redacción del ejemplo trata campos superiores, pero un mensaje anidado conserva un marcador fabricado. El contrato de publicación debe retirar ese literal sin perder la correlación técnica de la incidencia.',
     'Distribuir el registro aumentaría exposición innecesaria dentro del escenario. El marcador no es una credencial ni dato personal.',
     'Adoptar un esquema de campos permitidos y redactar antes de persistir; probar objetos anidados, vistas, descargas y errores de validación.'),
    ('Ajuste de stock admite una unidad incompatible con el catálogo', 2, 'medium', 'CWE-1284', 2,
     'Una posición ficticia usa unidades y otra usa cajas de tamaño variable. El ajuste valida un valor numérico, pero resuelve la unidad por etiqueta visible. Dos etiquetas similares producen una conversión no definida.',
     'La operación modelada podría desalinear existencias y generar decisiones de preparación equivocadas. No se ha alterado inventario físico.',
     'Usar identificadores de unidad y conversiones versionadas por artículo; rechazar valores sin contexto y registrar cantidad original y normalizada.'),
    ('Recuperación de identidad limita intentos sólo por terminal', 4, 'medium', 'CWE-307', 0,
     'El flujo cuenta intentos por dispositivo y omite la agrupación por cuenta y operación. Las entradas del caso son secuencias locales; no envían SMS, correos ni peticiones a un proveedor.',
     'La política del modelo podría aceptar más intentos que los previstos y aumentar carga de soporte. No se estima probabilidad de toma de cuenta.',
     'Combinar límites por cuenta, origen y operación con mensajes uniformes, y comprobar que una identidad legítima conserva una vía de recuperación.'),
    ('Eventos pierden correlación al mover una expedición entre colas', 12, 'medium', 'CWE-778', 4,
     'Al cambiar de cola, el modelo sustituye la correlación de expedición por un identificador temporal. El estado final existe, pero ya no puede relacionarse de manera inequívoca con autorización, reintento y ajuste.',
     'La reconstrucción ficticia podría confundir duplicados con operaciones distintas. Ausencia de correlación no demuestra pérdida de eventos.',
     'Preservar una correlación estable y añadir identificadores de tramo; registrar transición, estado y motivo sin almacenar cuerpos sensibles completos.'),
    ('Firma de recepción reutilizada después de cambiar el contenido', 3, 'medium', 'CWE-345', 1,
     'Una confirmación sintética queda enlazada al número visible de entrega. La lista de bultos puede cambiar sin invalidar esa confirmación y el documento posterior conserva la misma marca de aceptación.',
     'El receptor del informe podría atribuir aceptación a un contenido diferente del revisado. No se contiene firma biométrica ni evidencia de una recepción real.',
     'Vincular confirmación a una revisión inmutable del contenido; invalidarla al cambiar cantidad o destino y mostrar la versión aceptada en cada salida.'),
    ('Retención de documentos no alcanza sus miniaturas derivadas', 15, 'medium', 'CWE-459', 1,
     'El catálogo elimina el documento principal al vencer el plazo, pero no sus miniaturas ni índices secundarios. El guion distingue borrado lógico, retirada de acceso y eliminación de copias derivadas.',
     'La conservación residual del escenario prolongaría la exposición de contenido que ya no debería servirse. No se afirma borrado físico irrecuperable.',
     'Inventariar todas las derivaciones, propagar retirada de acceso y eliminación y demostrar el rechazo de lecturas desde cada consumidor.'),
    ('Origen de laboratorio permanece permitido en la API estable', 1, 'medium', 'CWE-942', 1,
     'Una configuración inventada conserva un origen de pruebas al representar el entorno estable. Las respuestas de error usan además una lista distinta de la de las respuestas exitosas.',
     'La confianza del modelo se extiende a un origen innecesario. El impacto depende de credenciales, métodos y datos expuestos.',
     'Derivar listas por entorno y centralizar la política; probar origen permitido, rechazado, nulo y normalización de esquema, host y puerto.'),
    ('Cambio de reloj invierte el orden aparente de auditoría', 12, 'medium', 'CWE-778', 4,
     'Dos componentes ficticios registran tiempos de pared con desfase conocido. Ordenar los registros por esa fecha sitúa una liquidación antes de la autorización que la permite.',
     'La lectura podría dificultar la explicación de una decisión y el alcance de una investigación. Un timestamp preciso en apariencia no acredita sincronización.',
     'Guardar fuente temporal y secuencia lógica; alertar por deriva y distinguir tiempo de decisión, recepción y presentación.'),
    ('Cierre de incidencia admite evidencia sin versión de expedición', 0, 'medium', 'CWE-223', 4,
     'El cierre conserva una imagen sintética, pero no identifica a qué revisión del expediente corresponde. Al reemplazarse la expedición, la evidencia continúa visible junto a la versión nueva.',
     'La asociación podría inducir una conclusión de corrección no sustentada por el contenido revisado. Una imagen no basta para acreditar un resultado.',
     'Vincular evidencia, hash, revisión y criterio de aceptación; mantener visible cualquier limitación y evitar cierres automáticos por mera presencia de un archivo.'),
    ('Privilegios de observación permiten también cambiar umbrales', 9, 'medium', 'CWE-250', 0,
     'El rol de consulta de sensores incluye una operación de configuración que modifica umbrales. La matriz ficticia verifica métodos HTTP, pero no diferencia operaciones de lectura y cambio bajo el mismo recurso.',
     'El modelo permitiría alterar alertas desde una identidad cuyo propósito es únicamente observar. No se manipularon dispositivos físicos.',
     'Separar permisos por operación y recurso, evaluar configuración como cambio privilegiado y registrar revisión y reversión de cada ajuste.'),
    ('Cabeceras de protección incompletas en pantallas auxiliares', 13, 'low', 'CWE-693', 1,
     'La portada de muestra define controles de navegador que no están presentes en las pantallas de error y ayuda. Las respuestas HTTP del anexo son literales inventados.',
     'La inconsistencia reduce defensa adicional sin demostrar una cadena explotable. La gravedad depende de las funciones que conserva cada plantilla.',
     'Centralizar cabeceras y justificar excepciones; comprobar autenticación, errores, ayuda y contenido estático de manera independiente.'),
    ('Mensajes de soporte distinguen contratos inexistentes', 0, 'low', 'CWE-204', 1,
     'Dos entradas preparadas producen textos diferentes según exista el contrato ficticio. No se enumeraron clientes: sólo se comparan dos datos creados para el documento.',
     'El escenario ofrece una señal limitada de existencia. No acredita acceso a otros atributos ni equivalencia temporal de las respuestas.',
     'Uniformar respuestas y rutas de ayuda sin impedir soporte legítimo; mantener el detalle técnico en un registro restringido.'),
    ('Versión interna expuesta en una respuesta de diagnóstico', 11, 'low', 'CWE-209', 4,
     'Una respuesta de ejemplo incluye versiones inventadas de componentes internos. El mismo diagnóstico se muestra a un usuario sin función administrativa.',
     'La información reduciría incertidumbre sobre el componente modelado, pero no constituye por sí misma una vulnerabilidad explotable.',
     'Usar un identificador de incidencia para usuarios y separar el detalle técnico en una vista de soporte con autorización explícita.'),
    ('Referencia extensa truncada en el procedimiento de conciliación', 5, 'low', 'CWE-223', 4,
     'El procedimiento manual copia sólo una parte del destino de una referencia. El caso exige conservar parámetros codificados, fragmento Unicode y puntuación visible sin introducir espacios invisibles.',
     'Una referencia incompleta dificultaría la reproducibilidad documental. Esta observación ficticia no afirma un defecto existente de report-gen.',
     'Usar un campo estructurado para el destino y verificar igualdad exacta; mostrar un texto legible conservando el enlace completo.'),
    ('Etiquetas de conservación ambiguas entre dos calendarios', 15, 'low', 'CWE-20', 1,
     'Dos plazos ficticios se presentan como treinta días sin indicar calendario, inicio ni zona horaria. Un lector interpreta días corridos y otro días hábiles.',
     'La ambigüedad generaría decisiones de conservación inconsistentes. No se realiza una interpretación de obligaciones legales reales.',
     'Expresar fecha inicial, zona horaria, regla de cómputo y fecha final; distinguir plazos operativos de requisitos que necesiten revisión especializada.'),
    ('Inventario de dependencias con responsables y excepciones visibles', 14, 'info', 'CWE-1104', 3,
     'Se registra una matriz inventada de componentes, propietarios y excepciones con vencimiento. La observación sirve para probar puntuación cero y recomendaciones de gestión sin declarar una vulnerabilidad.',
     'Sin impacto técnico asignado. La presencia de dependencias no demuestra exposición ni incumplimiento.',
     'Conservar propósito, propietario y motivo de cada excepción; distinguir software retirado de componentes activos y revisar su necesidad periódicamente.'),
    ('Seguimiento distingue cambio comunicado de corrección verificada', 12, 'info', 'CWE-703', 4,
     'El caso mantiene por separado comunicación, repetición, resultado y limitación. Incluye registros fechados y una nota sin fecha que no sustituye el último resultado verificable.',
     'Sin impacto técnico asignado. Los estados son inventados y no acreditan corrección en una organización real.',
     'Exigir alcance, fecha, evaluador, evidencia y criterio de cierre; conservar resultados parciales o no verificables sin convertirlos en aprobación.'),
]

ROOT_GROUPS = [
    ('Autorización y separación de funciones', 'Decisiones sin vínculo completo entre sujeto, contrato, recurso y momento.', 'Reutilizar un contrato de autorización y mantener casos positivos y negativos.'),
    ('Ciclo de vida de datos y documentos', 'Vigencia, versión y conservación distintas entre productores y consumidores.', 'Definir todas las derivaciones y comprobar revocación y eliminación por consumidor.'),
    ('Consistencia de operaciones y pagos', 'La identidad de transporte sustituye la identidad comercial o su versión.', 'Preservar invariantes de intención y estado con transiciones atómicas y compensación.'),
    ('Continuidad y configuración aprobada', 'Recuperación de bytes sin reconciliar restricciones y dependencias.', 'Restaurar contenido y política y exigir una reapertura comprobada.'),
    ('Trazabilidad y calidad de evidencia', 'Registros que omiten versión, correlación o límites de interpretación.', 'Conservar procedencia y alcance sin publicar contenido innecesario.'),
]
VECTORS = {
    'critical': 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
    'high': 'CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N',
    'medium': 'CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N',
    'low': 'CVSS:3.1/AV:N/AC:H/PR:L/UI:R/S:U/C:L/I:N/A:N',
    'info': 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N',
}
V4 = {2: 'CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N',
      29: 'CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N'}


def uid(label):
    return str(uuid.uuid5(NAMESPACE, label))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def write(path, blob):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob if isinstance(blob, bytes) else blob.encode('utf-8'))


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(str(v).replace('|', '\\|').replace('\n', '<br>') for v in row) + ' |' for row in rows])


def csv_bytes(headers, rows):
    stream = StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def font(size, mono=False):
    return ImageFont.truetype(str(ROOT / ('themes/fonts/DejaVuSansMono.ttf' if mono else 'exporters/fonts/DejaVuSans.ttf')), size)


def evidence_image(path, number):
    spec = FINDINGS[(number - 1) % len(FINDINGS)]
    title, asset, severity = spec[:3]
    portrait = number in (6, 18, 31)
    width, height = (760, 850) if portrait else (1400, 430)
    image = Image.new('RGB', (width, height), '#f5f4ef')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 78), fill='#173a44')
    draw.text((28, 23), f'GML / E{number:02d} / MODELO SINTÉTICO', font=font(23), fill='white')
    for line, value in enumerate(textwrap.wrap(title, 48 if portrait else 86)):
        draw.text((28, 102 + line * 30), value, font=font(22), fill='#173a44')
    rows = [('Activo', ASSETS[asset][1]), ('Expediente', f'GML-EXP-{number:02d} / organización A'),
            ('Decisión', 'Permiso + versión + intención comercial'), ('Clasificación', severity.upper() + ' / supuesto ficticio'),
            ('Ejecución', 'SIN RED / SIN CARGAS / SIN PAGOS REALES')]
    y = 197 if portrait else 184
    for index, (label, value) in enumerate(rows):
        if portrait:
            draw.rounded_rectangle((24, y, width - 24, y + 94), radius=7, fill='white', outline='#ccd6d5')
            draw.text((42, y + 11), label.upper(), font=font(17), fill='#4d6a70')
            for line, part in enumerate(textwrap.wrap(value, 45)):
                draw.text((42, y + 39 + line * 21), part, font=font(17, True), fill='#173a44')
            y += 106
        else:
            draw.rectangle((26, y, width - 26, y + 32), fill='white' if index % 2 == 0 else '#e8edeb')
            draw.text((39, y + 6), label, font=font(17), fill='#4d6a70')
            draw.text((235, y + 6), value, font=font(17, True), fill='#173a44')
            y += 35
    draw.text((28, height - 35), f'{CASE} / {DATE} / NO ES CAPTURA REAL', font=font(14), fill='#4d6a70')
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('Description', METADATA_MARKER)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format='PNG', pnginfo=metadata, optimize=False)


def branding(directory):
    logo = Image.new('RGB', (1200, 185), '#173a44')
    draw = ImageDraw.Draw(logo)
    draw.ellipse((34, 36, 144, 146), outline='#e3bc65', width=7)
    draw.line((89, 24, 89, 159), fill='#e3bc65', width=5)
    draw.line((26, 91, 153, 91), fill='#e3bc65', width=5)
    draw.text((185, 35), 'GRUPO MERIDIANO', font=font(49), fill='white')
    draw.text((188, 112), 'LOGÍSTICA FICTICIA / LABORATORIO DOCUMENTAL', font=font(23), fill='#c5d5d5')
    logo.save(directory / 'logo.png')
    cover = Image.new('RGB', (1400, 380), '#173a44')
    draw = ImageDraw.Draw(cover)
    for index, label in enumerate(('OPERACIONES', 'PAGOS', 'TERCEROS', 'RECUPERACIÓN')):
        x = 30 + 345 * index
        draw.rounded_rectangle((x, 64, x + 300, 265), radius=13, outline='#e3bc65', width=3)
        draw.text((x + 20, 98), f'0{index + 1}', font=font(49), fill='#e3bc65')
        draw.text((x + 20, 204), label, font=font(22), fill='white')
    draw.text((34, 320), '16 ACTIVOS / 30 HALLAZGOS / 4 CUADERNOS / DATOS SINTÉTICOS', font=font(24), fill='#c5d5d5')
    cover.save(directory / 'cover.png')


def findings():
    result = []
    for n, spec in enumerate(FINDINGS, 1):
        title, asset, severity, cwe, group, condition, consequence, correction = spec
        fid, vector = f'F{n:02d}', V4.get(n, VECTORS[severity])
        rating = cvss.score(vector)
        assert rating['severity'] == severity
        status = ('open', 'in_progress', 'reported_fixed', 'verified_fixed', 'accepted', 'not_verified')[(n - 1) % 6]
        row = dict(id=fid, uid=uid(fid), mode='vuln', title=title + ' [SIMULADO]', severity=severity,
                   cvss=rating['score'], cvss_vector=vector, cvss_version=vector.split('/')[0].split(':')[1], cwe=cwe,
                   description_md=condition + '\n\n**Límite:** descripción de un modelo local inventado. No es un resultado de una auditoría real.',
                   impact_md=consequence, remediation_md=correction,
                   affected=f'https://{ASSETS[asset][1]}/scenario/{fid.lower()}', owner=ASSETS[asset][4] + ' [rol ficticio]',
                   due_date=f'2026-11-{(n - 1) % 28 + 1:02d}', status=status,
                   verification='inconclusive' if status == 'not_verified' else 'confirmed',
                   asset_uids=[uid(f'asset-{asset}')], evidence_uids=[uid(f'evidence-{n}')], root_cause_uid=uid(f'root-{group}'),
                   closure_criteria_md='Preparar caso permitido y caso rechazado; vincular resultado a sujeto, expediente y versión. Documentar cualquier resultado parcial y preservar la evidencia sintética con su alcance.',
                   walkthrough=[dict(lead='Contrato del escenario', text_md='1. Preparar dos organizaciones y expedientes ficticios con permisos distintos.\n2. Comparar la transición permitida y la que debe rechazarse sin efecto de negocio.\n3. Registrar versión, correlación y limitación. No enviar tráfico a los destinos del documento.')],
                   references=[f'https://docs.meridiano.example/controls/{fid.lower()}#criterio-de-aceptación'])
        if n in (1, 4, 12, 14, 22, 27):
            row['walkthrough'].append(dict(lead='Registro documental inerte', command=f'CASE={CASE}\nFINDING={fid}\nSUBJECT=ORGANIZACION-FICTICIA-A\nEXPEDITION=GML-EXP-{n:02d}\nVERSION=3\nNETWORK_EXECUTION=NONE'))
        if n == 12:
            row['walkthrough'].append(dict(lead='Tabla de evidencias con destinos externos', text_md=table(['Patrón', 'Evidencia sintética'], [
                ['Imagen y destino externo', '[![GML tabla UNO](img/evidence-12.png)](https://docs.meridiano.example/edi#contrato)'],
                ['Imágenes con destino compartido', '[![GML tabla DOS](img/evidence-11.png) ![GML tabla TRES](img/evidence-12.png)](https://docs.meridiano.example/edi#multiple)'],
            ])))
            row['walkthrough'].append(dict(lead='Tabla de continuidad, prosa y evidencia vertical', text_md=table(['Patrón', 'Evidencia sintética'], [
                ['Prosa adyacente y destino interno', '[Antes![GML tabla CUATRO](img/evidence-12.png)Después](#F12)'],
                ['Dos figuras contiguas', '![GML tabla CINCO](img/evidence-31.png)![GML tabla SEIS](img/evidence-32.png)'],
            ])))
            row['evidence_uids'] += [uid('evidence-31'), uid('evidence-32')]
        if n == 14:
            row['description_md'] += '\n\nMarcador de redacción: ' + REDACTION_MARKER + '.'
        if n == 27:
            row['references'].append(LONG_URL)
            row['description_md'] += '\n\n[Referencia íntegra de conciliación](' + LONG_URL + ')'
        if status in ('reported_fixed', 'accepted'):
            row['reported_remediation'] = 'Registro ficticio de comunicación o aceptación. No equivale a una corrección verificada ni a una aprobación empresarial real.'
        if status == 'verified_fixed' or n in (7, 14, 21, 30):
            outcome = 'fixed' if status == 'verified_fixed' else {7: 'open', 14: 'partial', 21: 'not_verified', 30: 'not_verified'}[n]
            row['retests'] = [dict(uid=uid(f'retest-{n}'), tested_on='2026-10-15', assessor='Revisor ficticio GML', result=outcome,
                                  notes_md='**RESULTADO INVENTADO:** seguimiento documental del modelo.\n\n' + table(['Condición', 'Interpretación'], [['Permitida', 'Descrita en el guion'], ['Rechazada', 'Resultado o límite ficticio'], ['Alcance', 'No hubo validación de un servicio real']]), evidence_uids=[uid(f'evidence-{n}')])]
        if n == 30:
            row['retests'].append(dict(uid=uid('retest-undated'), tested_on='', assessor='Nota heredada ficticia', result='not_verified', notes_md='Sin fecha; no sustituye el último seguimiento fechado.', evidence_uids=[]))
        result.append(row)
    return result


def machines():
    result = []
    for n, asset in enumerate((6, 9, 11, 14), 1):
        name, target, address, _, owner = ASSETS[asset]
        phases = [dict(name=phase, steps=[dict(lead=f'M{n:02d}.{step}', text_md=narrative,
                  command=f'MODEL_ONLY=true\nMACHINE=M{n:02d}\nPHASE={step}\nNETWORK_EXECUTION=NONE')])
                  for step, (phase, narrative) in enumerate([
                      ('Inventario', 'Registrar componentes y dependencias ficticios sin atribuir puertos descubiertos ni acceso inicial.'),
                      ('Fronteras de confianza', 'Relacionar identidad, recurso y momento. Conservar el caso permitido y el rechazado.'),
                      ('Estado y correlación', 'Separar intención, reintento y resultado; mantener versión y correlación sin datos personales.'),
                      ('Recuperación', 'Proponer restauración aislada y verificación de restricciones antes de reabrir el flujo.'),
                      ('Cierre y límites', 'Identificar cualquier condición desconocida y evitar presentar documentación como ejecución.'),
                  ], 1)]
        result.append(dict(id=f'M{n:02d}', uid=uid(f'M{n:02d}'), mode='machine', title=name + ' — cuaderno ficticio',
                           host=dict(name=target, ip=address, os='Sistema de laboratorio ficticio'), open_ports='443/tcp, 8443/tcp [INVENTADOS]',
                           summary_md=WARNING + ' Este cuaderno contiene cinco fases documentales, no acceso inicial, elevación ni persistencia.',
                           status='not_verified', verification='unverified', owner=owner + ' [rol ficticio]', due_date='2026-12-15',
                           asset_uids=[uid(f'asset-{asset}')], evidence_uids=[uid(f'evidence-{n * 6}')], phases=phases,
                           proof=[dict(name=f'modelo-M{n:02d}.txt', value=f'MERIDIANO_SYNTHETIC_PROOF_{n}_NOT_A_CAPTURED_FLAG', notes='Valor inventado, no prueba de compromiso.')]))
    return result


def sections(rows):
    counts = Counter(row['severity'] for row in rows)
    controls = [[f'GML-{n:02d}-{suffix}', f'[F{n:02d}](#F{n:02d})', test, 'Contrato inventado; no prueba ejecutada']
                for n in range(1, 31) for suffix, test in [('P', 'Permiso y versión válidos'), ('N', 'Rechazo sin efecto de negocio'), ('R', 'Reintento o recuperación coherente')]]
    return [
        dict(key='confidentiality', body=WARNING + '\n\nGrupo Meridiano Logística no es una empresa existente. Los dominios .example y las redes 192.0.2.0/24, 198.51.100.0/24 y 203.0.113.0/24 son identificadores de documentación. No se contactaron destinos, no se transportaron mercancías y no hubo pagos. Las imágenes son diagramas de evidencia sintética, no capturas de sistemas operativos.\n\nEste informe permite comprobar fidelidad documental y funciones de report-gen. No demuestra cumplimiento normativo, seguridad de una organización ni ausencia universal de errores del generador.'),
        dict(key='document_control', version_history=[dict(version='0.1', date='2026-10-14', author='Equipo ficticio GML', notes='Inventario, contratos y fronteras de confianza.'), dict(version='0.2', date='2026-10-15', author='Equipo ficticio GML', notes='Hallazgos, dependencias y seguimiento simulado.'), dict(version='1.0', date=DATE, author='Equipo ficticio GML', notes='Caso complejo para verificar report-gen.')], distribution='Ejemplo reutilizable identificado como ficticio. La prosa se redacta en español; EN y PT localizan etiquetas y navegación documental y no constituyen una traducción del contenido de autor.'),
        dict(key='contacts'),
        dict(key='executive_summary', summary='Grupo Meridiano Logística representa una operación inventada con almacenes, planificación de rutas, última milla, intercambio documental, cadena de frío y pagos a transportistas. El alcance reúne **16 activos, 30 hallazgos, 4 cuadernos de máquinas, 32 evidencias y 90 contratos de control**. Las máquinas no se cuentan como vulnerabilidades.\n\nLa clasificación sintética contiene ' + ', '.join(f'{counts[s]} {label}' for s, label in [('critical', 'críticos'), ('high', 'altos'), ('medium', 'medios'), ('low', 'bajos'), ('info', 'informativos')]) + '. Los vectores CVSS son supuestos coherentes con las bandas, no una medición de exposición ni probabilidad de pérdida.\n\nLa prioridad del escenario es mantener el vínculo entre contrato comercial, identidad autorizada y versión del expediente. Una autorización al recibir un mensaje no basta para ejecutar una operación tras la revocación. Un identificador nuevo de transporte no convierte un reintento en una obligación nueva. Una copia recuperable tampoco demuestra que los permisos restaurados sigan vigentes.\n\nLa segunda prioridad es preservar la explicación de cada decisión. Las evidencias deben señalar la revisión a la que corresponden; la correlación debe atravesar colas y reintentos; los mensajes publicados deben excluir información innecesaria. El cierre de una incidencia exige un resultado y sus límites, no sólo un archivo adjunto.\n\nDirección necesita prioridades, dependencias y responsables. Los equipos técnicos necesitan condiciones previas, comportamiento permitido y rechazado, referencias íntegras y criterios de cierre. Los derivados técnico, ejecutivo y público disponibles en report-gen sirven a propósitos distintos y no deben presentarse como equivalentes.\n\nEl éxito de este ejercicio es documental: conservar texto, estructura, imágenes, enlaces y decisiones de publicación en PDF, DOCX, HTML y Markdown. Los resultados de la herramienta se documentan fuera de esta ficción.'),
        dict(key='risk_posture', posture='Las fronteras de confianza se extienden desde una expedición hasta sus documentos, pagos y copias recuperadas. La priorización se basa en invariantes compartidas, no en sumar puntuaciones.\n\n' + table(['Dimensión', 'Hipótesis ficticia', 'Criterio de aceptación'], [['Confidencialidad', 'Contrato ajeno o vínculo revocado', 'Lecturas autorizadas y rechazo por recurso'], ['Integridad', 'Duplicado o versión desalineada', 'Una intención, un resultado coherente'], ['Continuidad', 'Recuperación con política antigua', 'Contenido y restricciones reconciliados'], ['Trazabilidad', 'Registro sin versión o correlación', 'Decisión explicable con alcance visible']]) + '\n\nNo se asignan pérdidas monetarias, porcentajes de madurez ni equivalencias regulatorias. Los indicadores son propuestas, no mediciones.'),
        dict(key='strategic_recommendations', recommendations='1. Autorizar sobre expediente resuelto, contrato, operación y momento.\n2. Mantener identidad comercial y versión a través de colas y reintentos.\n3. Recuperar restricciones junto al contenido.\n4. Mantener el ciclo de vida de documentos y derivaciones.\n5. Asociar evidencia y decisión con revisión, fecha y límites.\n\nCada iniciativa necesita propietario, dependencia, criterio de aceptación y reversión. Un estado de riesgo aceptado en este ejemplo no constituye aprobación empresarial.'),
        dict(key='scope', objectives='Modelar dieciséis activos que conectan clientes, operaciones, pagos, terceros y recuperación. Distinguir responsabilidades de los productores de datos y sus consumidores.\n\nSe excluyen infraestructura real, datos personales, ingeniería social, transacciones, pruebas físicas y denegación de servicio. Ningún enlace del inventario fue consultado.', assumptions='Sólo entradas fabricadas y composición documental local. Los roles son nombres genéricos inventados. Las conclusiones de seguridad, cobertura y retest forman parte del guion.'),
        dict(key='methodology', approach='Cada control conserva condición previa, entrada permitida, entrada rechazada y criterio de recuperación. Los IDs y UIDs permanecen estables entre variantes de idioma. Se documentan contratos de estado, versiones y dependencias, sin inferir que una narrativa fue ejecutada.', standards='CWE se utiliza como clasificación orientativa. Este ejemplo no interpreta ni acredita cumplimiento de ISO, NIST, PCI DSS u otra normativa.', information_gathering='Inventario creado desde cero, sin OSINT ni contacto externo. CSV, Burp XML, Nuclei JSONL, Nmap XML y SARIF son entradas fabricadas.', enumeration='Puertos, hosts y relaciones pertenecen al guion. Una fila de inventario no acredita descubrimiento de un servicio.', exploitation='Se usan solicitudes y pseudocódigo inertes para explicar condiciones. No hay sesiones, credenciales ni cargas operativas.', post_exploitation='Las dependencias narrativas son relaciones de diseño, no una intrusión. No hubo acceso inicial, escalada, persistencia ni movimiento lateral.', cleanup='Conservar manifiestos de la herramienta y separar los resultados ficticios del informe. Cerrar servidores locales al concluir la aceptación.'),
        dict(key='findings_summary'), dict(key='findings'),
        dict(key='attack_narrative', narrative='### Cadena A: contrato, expediente y lote\n\n[F01](#F01), [F11](#F11) y [F12](#F12) relacionan autorización de recurso, exportación masiva e identidad compuesta EDI. La asociación es conceptual: no demuestra que los tres pasos sean simultáneamente alcanzables.\n\n### Cadena B: obligación, reintento y corrección\n\n[F04](#F04), [F05](#F05) y [F09](#F09) muestran cómo la decisión de pago depende de una identidad independiente y de una versión comercial estable. El cambio de estado no sustituye el control del contenido aprobado.\n\n### Cadena C: restauración y revocación\n\n[F02](#F02), [F03](#F03) y [F10](#F10) relacionan integridad de paquetes, autoridad administrativa y política restaurada. El corte propuesto exige privilegio mínimo y reapertura verificada.\n\n### Cadena D: evidencia y explicación\n\n[F14](#F14), [F17](#F17), [F21](#F21) y [F22](#F22) separan redacción, correlación, tiempo y versión de evidencia. Una investigación debería preservar las cuatro dimensiones sin publicar datos innecesarios. Ninguna cadena fue ejecutada.'),
        dict(key='remediation_plan', overview='Cinco grupos de causa raíz conectan acciones específicas. La secuencia evita cambiar a la vez autorización, colas y restauración sin un plan de reversión.\n\n' + table(['Etapa', 'Responsable ficticio', 'Dependencia', 'Salida esperada'], [['Contención', 'Operaciones y plataforma', 'Contrato de autorización', 'Cambios de mayor impacto controlados'], ['Corrección', 'Finanzas e integraciones', 'Identidad y versión comercial', 'Transiciones consistentes'], ['Validación', 'Revisión independiente', 'Casos positivos y negativos', 'Resultado con evidencia y límites'], ['Sostenimiento', 'Continuidad y datos', 'Regresión y catálogo', 'Revocación y recuperación verificables']]), short_term='En siete días ficticios, revisar las tres hipótesis críticas y reducir permisos innecesarios. Acordar contratos de revocación y reapertura antes de automatizarlos.', medium_term='En treinta días ficticios, armonizar pagos, correcciones y reintentos. Incorporar trazabilidad y política de documentos a cada consumidor.', long_term='En noventa días ficticios, ensayar recuperación y cambios de política en un entorno autorizado. Revisar dependencias y excepciones sin confundir actividad con eficacia.'),
        dict(key='appendix', host_service_discovery=table(['Red documental', 'Activos', 'Naturaleza'], [['192.0.2.0/24', '6', 'Canales y operaciones inventadas'], ['198.51.100.0/24', '6', 'Procesamiento y plataforma inventados'], ['203.0.113.0/24', '4', 'Soporte y continuidad inventados']]), exploited_hosts='Ninguno. Los cuatro cuadernos son modelos documentales, no pruebas de compromiso.', compromised_users='Ninguno. No hay credenciales ni identidades reales.', changes_cleanup='No se alteraron operaciones, documentos o pagos reales. Sólo se prepararon entradas y se produjeron archivos del proyecto de ejemplo.', tools_used='**Informes:** exclusivamente exportadores registrados y entrega nativa de report-gen.\n\n**Entradas:** builder reproducible de YAML, PNG sintéticos e importaciones inertes.\n\n**Inspección:** validadores de la herramienta y revisión de salidas; los motores externos sólo pueden inspeccionar o representar el DOCX generado.', glossary=table(['Término', 'Uso'], [['Expediente', 'Unidad documental con versión y contrato'], ['Obligación', 'Intención comercial independiente del transporte'], ['Derivación', 'Miniatura, índice o salida vinculada al origen'], ['Retest', 'Seguimiento ficticio con resultado y límite'], ['Reapertura', 'Decisión de restaurar servicio y restricciones']])) ,
        dict(key='gml-controls', title='Anexo A — Noventa contratos de aceptación', body='Estas 90 filas prueban tablas extensas, encabezados y referencias internas. No representan 90 pruebas ejecutadas contra una empresa.\n\n' + table(['Control', 'Hallazgo', 'Contrato', 'Límite'], controls)),
        dict(key='gml-literals', title='Anexo B — Literales, enlaces y caracteres internacionales', body='El destino completo debe conservarse; no fue consultado.\n\n[Conciliación: revisión, revisão y açaí](' + LONG_URL + ')\n\n<' + LONG_URL + '>\n\n' + table(['Identificador', 'Literal', 'Contrato'], [['REF-LARGA', LONG_URL, 'Conservar destino exacto'], ['UNICODE', 'acción / revisão / açaí / São Paulo / ñ / Überprüfung', 'Conservar texto Unicode'], ['ESCAPES', 'A&B <demo> [prueba] %2D %3A', 'Entidades y escapes legibles']]) + '\n\n```text\nMERIDIANO_LITERAL_SENTINEL\nGET /v1/expeditions/GML-EXP-01?preview=true HTTP/1.1\nHost: rutas.meridiano.example\nX-Synthetic-Only: true\nX-Correlation: GML-0123456789abcdef0123456789abcdef0123456789abcdef\n```\n\n1. Resolver contrato y expediente.\n    1. Verificar el caso permitido.\n    2. Verificar rechazo sin efecto de negocio.\n2. Conservar resultado y limitación.\n\n> Una representación no equivale a una prueba.\n>\n> - **ES:** ejemplo ficticio.\n> - **EN:** fictional example.\n> - **PT:** exemplo fictício.'),
        dict(key='gml-annexes', title='Anexo C — Publicación y documentos anexos', body='Los anexos incluidos son archivos independientes de la entrega; no se afirma que el cuerpo PDF los incruste. Los originales, notas privadas y marcadores excluidos pertenecen al proyecto editable.\n\n' + table(['Archivo', 'Decisión', 'Contenido'], [['inventario-activos.csv', 'Incluido', '16 activos sintéticos'], ['matriz-de-aceptacion.csv', 'Incluido', '90 contratos ficticios'], ['manifiesto-del-caso.json', 'Incluido', 'Conteos y límites'], ['criterios-de-entrega.md', 'Incluido', 'Fidelidad y publicación'], ['notas-internas.txt', 'Privado, excluido', 'Marcador sintético de aislamiento']]) + '\n\nLa revisión estructural de anexos PDF es una ayuda para localizar contenido que requiere decisión. No acredita ausencia universal de datos privados ni sustituye la revisión del material. Un resultado parcial debe conservar sus límites.'),
    ]


def make_project(language='es'):
    if language not in ('es', 'en', 'pt'):
        raise ValueError('Supported languages: es, en, pt')
    rows = findings()
    raw = PRIVATE_MARKER + '\nNota privada sintética no destinada a publicación.'
    data = dict(schema_version=2, finding_sequence=30,
        meta=dict(lang=language, theme='corporativo', report_density='compact', report_title='Grupo Meridiano Logística — evaluación integral ficticia',
                  report_subtitle='Operaciones, pagos, terceros y recuperación / 30 hallazgos + 4 cuadernos', client='Grupo Meridiano Logística [FICTICIO]',
                  assessor='Equipo de auditoría ficticio GML', assessor_title='Simulación documental / report-gen', date=DATE, version='GML 1.0',
                  branding=dict(wordmark='GRUPO MERIDIANO', byline='LOGÍSTICA FICTICIA / SIN SISTEMAS REALES', confidential_text='FICTICIO / DATOS SINTÉTICOS', accent='#206879', logo='img/logo.png', cover_image='img/cover.png'),
                  contacts=dict(client=[dict(name='Patrocinio tecnológico [ficticio]', title='Coordinación del escenario', email='tecnologia@meridiano.example'), dict(name='Responsable de operaciones [ficticio]', title='Alcance logístico', email='operaciones@meridiano.example')], assessor=[dict(name='Revisión documental [ficticia]', title='Control del ejemplo', email='revision@meridiano.example')]),
                  scope=[dict(target=a[1], description=f'{a[0]} / {a[2]} / FICTICIO') for a in ASSETS]),
        report=dict(sections=sections(rows), workflow=dict(include_assets=True, include_coverage=True, include_retest=True, include_root_causes=True)),
        findings=rows + machines(),
        assets=[dict(uid=uid(f'asset-{n}'), name=a[0], target=f'{a[1]} / {a[2]}', kind=a[3], notes=a[4] + '; activo ficticio no contactado.') for n, a in enumerate(ASSETS)],
        evidence=[dict(uid=uid(f'evidence-{n}'), title=f'GML-E{n:02d} / modelo documental', src=f'img/evidence-{n:02d}.png', caption=f'GML-E{n:02d} — representación sintética; no es una captura de una empresa.') for n in range(1, 33)],
        coverage=[dict(uid=uid(f'coverage-{n}-{suffix}'), asset_uid=uid(f'asset-{spec[1]}'), test=f'GML-{n:02d}-{suffix} / {label}', status=state,
                       notes='ESTADO SIMULADO: contrato del guion, no una prueba ejecutada.')
                  for n, spec in enumerate(FINDINGS, 1) for suffix, label, state in [('P', 'Caso permitido', 'done'), ('N', 'Caso rechazado', ('done', 'pending', 'blocked', 'not_applicable')[(n - 1) % 4]), ('R', 'Reintento o recuperación', ('done', 'pending')[(n - 1) % 2])]],
        root_cause_groups=[dict(uid=uid(f'root-{n}'), name=name, cause_md=cause + ' Hipótesis ficticia.', remediation_md=action) for n, (name, cause, action) in enumerate(ROOT_GROUPS)],
        limitations_md=WARNING + ' EN/PT localizan etiquetas del documento; la prosa permanece en español. Los resultados del generador se registran fuera del guion.',
        publication=dict(redactions=[dict(needle=REDACTION_MARKER, replacement='[CENSURADO: MARCADOR SINTÉTICO]')], exceptions=[]),
        capture_inbox=[dict(uid=uid('private-note'), kind='note', title='Nota privada de control', raw_text=raw, note='No promover a hallazgos.', created=DATE + 'T12:00:00Z', sha256=sha256(raw.encode()).hexdigest())],
        project_management=dict(archived=False, delivery_date='2026-12-15'))
    data['evidence'][0]['original'] = 'originals/evidence-01.png'
    return data


def add_annexes(directory, data):
    manifest = dict(schema='report-gen-meridiano-case/1', case=CASE, date=DATE, fictional=True,
                    vulnerabilities=30, machines=4, assets=16, evidence_images=32, coverage_rows=90,
                    severity_counts=dict(Counter(row['severity'] for row in data['findings'] if row['mode'] == 'vuln')),
                    prose_language='es', presentation_language=data['meta']['lang'])
    controls = [[f'GML-{n:02d}-{suffix}', f'F{n:02d}', label, 'SIMULADO'] for n in range(1, 31) for suffix, label in [('P', 'Permitido'), ('N', 'Rechazado'), ('R', 'Reintento')]]
    blobs = [('inventario-activos.csv', csv_bytes(['nombre', 'destino', 'ipv4', 'tipo', 'responsable_ficticio'], ASSETS), True),
             ('matriz-de-aceptacion.csv', csv_bytes(['control', 'hallazgo', 'caso', 'naturaleza'], controls), True),
             ('manifiesto-del-caso.json', json_bytes(manifest), True),
             ('criterios-de-entrega.md', '# Contrato ficticio Meridiano\n\nConservar 30 hallazgos, 4 cuadernos, 16 activos, 32 evidencias y 90 contratos.\n\nExcluir notas privadas, originales y marcadores de prueba; mantener destinos y pies de figura. EN/PT conservan prosa española declarada.\n', True),
             ('notas-internas.txt', PRIVATE_MARKER + '\nAnexo sintético excluido.\n', False)]
    data['attachments'] = []
    for name, content, included in blobs:
        blob = content if isinstance(content, bytes) else content.encode()
        member = 'attachments/' + uuid.UUID(uid('annex-' + name)).hex + Path(name).suffix
        write(directory / member, blob)
        data['attachments'].append(dict(uid=uid('annex-' + name), name=name, member=member, sha256=sha256(blob).hexdigest(), include=included, reviewed=included, required=included))


def import_inputs(directory):
    """Five independently authored, inert scanner inputs with real parser validation."""
    directory.mkdir(parents=True)
    burp = '''<?xml version="1.0" encoding="UTF-8"?><issues burpVersion="synthetic"><issue><serialNumber>GML-BURP-01</serialNumber><name>Contrato de proveedor [SIMULADO]</name><host>https://terceros.meridiano.example</host><path>/documento</path><severity>Information</severity><confidence>Tentative</confidence><issueBackground>Entrada fabricada, sin escaneo.</issueBackground><issueDetail>Contrato de referencia documental.</issueDetail><remediationBackground>Revisión ficticia.</remediationBackground><references><![CDATA[<a href="https://docs.meridiano.example/import/burp#revisión">Referencia sintética</a>]]></references><requestresponse><request>GET /documento HTTP/1.1
Host: terceros.meridiano.example
X-Synthetic: true</request><response>HTTP/1.1 200 OK

SYNTHETIC_ONLY</response></requestresponse></issue></issues>'''
    nuclei = {'template-id': 'gml-synthetic-contract', 'matched-at': 'https://edi.meridiano.example/contract', 'type': 'http', 'timestamp': DATE + 'T12:00:00Z', 'matcher-status': True,
              'info': dict(name='Contrato EDI [SIMULADO]', severity='info', description='Resultado fabricado; ningún escáner fue ejecutado.', remediation='Revisar el contrato ficticio.', reference=['https://docs.meridiano.example/import/nuclei']), 'extracted-results': ['MERIDIANO_SYNTHETIC_NUCLEI']}
    nmap = '''<?xml version="1.0" encoding="UTF-8"?><nmaprun scanner="nmap" version="synthetic"><host><status state="up" reason="user-set"/><address addr="192.0.2.90" addrtype="ipv4"/><hostnames><hostname name="inventario.meridiano.example" type="user"/></hostnames><ports><port protocol="tcp" portid="443"><state state="open" reason="synthetic"/><service name="https" product="Synthetic gateway" version="1.0" method="table" conf="3"/></port><port protocol="tcp" portid="8443"><state state="closed" reason="synthetic"/><service name="https-alt" method="table" conf="3"/></port></ports></host><runstats><finished elapsed="1.00" exit="success"/><hosts up="1" down="0" total="1"/></runstats></nmaprun>'''
    sarif = dict(version='2.1.0', runs=[dict(tool=dict(driver=dict(name='Meridiano synthetic scanner', version='1.0', rules=[dict(id='GML-CONTRACT', name='ContractIdentity', shortDescription=dict(text='Contrato ficticio de identidad'))])), results=[dict(ruleId='GML-CONTRACT', ruleIndex=0, level='note', message=dict(text='Resultado fabricado, no escaneo.'), locations=[dict(physicalLocation=dict(artifactLocation=dict(uri='https://codigo.meridiano.example/contract.py'), region=dict(startLine=17, startColumn=3)))], partialFingerprints={'primaryLocationLineHash': 'gml-synthetic-contract'})])])
    # A deliberate duplicate repeats the external ID and target. Different
    # source IDs remain independent observations even when their titles match.
    csv_input = csv_bytes(['title', 'severity', 'affected', 'description_md', 'impact_md', 'remediation_md', 'external_id'], [['Contrato de transporte [SIMULADO]', 'low', 'https://edi.meridiano.example/csv', 'Texto con coma, revisión y salto\nde línea inventado.', 'Sin exposición real.', 'Revisar contrato.', 'GML-CSV-01'], ['Contrato de transporte [SIMULADO]', 'low', 'https://edi.meridiano.example/csv', 'Duplicado deliberado de identidad.', 'Sin exposición real.', 'Revisar contrato.', 'GML-CSV-01']])
    entries = [('findings.csv', 'csv', csv_input), ('burp.xml', 'burp', burp.encode()), ('nuclei.jsonl', 'nuclei', (json.dumps(nuclei, ensure_ascii=False) + '\n').encode()), ('nmap.xml', 'nmap', nmap.encode()), ('sarif.json', 'sarif', json_bytes(sarif))]
    result = {}
    for name, kind, blob in entries:
        write(directory / name, blob)
        preview = finding_imports.preview(dict(format=kind, text=blob.decode()), dict(meta=dict(lang='es'), findings=[], assets=[], coverage=[]))
        if any(row.get('errors') for row in preview['rows']):
            raise ValueError(f'Invalid scanner fixture: {name}')
        result[name] = dict(format=kind, counts=preview['counts'], sha256=sha256(blob).hexdigest())
    return result


def build_case(output, languages=('es', 'en', 'pt')):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    languages = tuple(languages)
    if not languages or len(set(languages)) != len(languages) or any(lang not in ('es', 'en', 'pt') for lang in languages):
        raise ValueError('Choose unique languages from es, en, pt')
    output.mkdir(parents=True)
    projects = {}
    for language in languages:
        project = output / 'projects' / language
        (project / 'img').mkdir(parents=True)
        for n in range(1, 33):
            evidence_image(project / 'img' / f'evidence-{n:02d}.png', n)
        branding(project / 'img')
        write(project / 'originals/evidence-01.png', (project / 'img/evidence-01.png').read_bytes())
        write(project / 'private/unlinked.txt', UNLINKED_MARKER + '\nExcluded synthetic control.\n')
        data = make_project(language)
        add_annexes(project, data)
        validate.require_valid(data, final=True)
        if workflows.structure_errors(data):
            raise ValueError(workflows.structure_errors(data))
        capture_inbox.validate_rows(data['capture_inbox'])
        inventory = attachments.inventory(data, project)
        if any(item['status'] not in ('included', 'excluded') for item in inventory):
            raise ValueError('Invalid annex inventory')
        write(project / 'engagement.yaml', yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110))
        if engine.load_engagement(project / 'engagement.yaml') != data:
            raise ValueError('YAML roundtrip altered the fixture')
        issues = workflows.preflight(data, project, language)
        if any(issue['level'] == 'error' for issue in issues):
            raise ValueError(issues)
        projects[language] = dict(project=f'projects/{language}', vulnerabilities=30, machines=4, assets=len(data['assets']), evidence=len(data['evidence']), coverage=len(data['coverage']), sections=len(data['report']['sections']), root_cause_groups=len(data['root_cause_groups']), retest_records=sum(len(f.get('retests', [])) for f in data['findings']), severity_counts=engine.severity_counts(data['findings']), source_bytes=(project / 'engagement.yaml').stat().st_size, annexes=[dict(name=a['name'], status=a['status'], bytes=a['bytes']) for a in inventory], validation_errors=0, validation_warnings=validate.validate(data), preflight_issues=issues)
    imports = import_inputs(output / 'inputs')
    files = {path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()).hexdigest()) for path in sorted(output.rglob('*')) if path.is_file()}
    manifest = dict(schema='report-gen-meridiano-source/1', case=CASE, date=DATE, fictional=True, source_generator='scripts/build-meridiano-case.py', prose_language='es', variants_note='EN/PT localize labels and navigation; authored prose stays Spanish.', network_to_scenario_targets=False, reports_generated_by_builder=False, projects=projects, import_previews=imports, files=files)
    write(output / 'manifest.json', json_bytes(manifest))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--languages', nargs='+', choices=('es', 'en', 'pt'), default=['es', 'en', 'pt'])
    args = parser.parse_args()
    result = build_case(args.output, args.languages)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, ensure_ascii=False, indent=2))
