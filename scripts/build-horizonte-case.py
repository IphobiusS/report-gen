#!/usr/bin/env python3
"""Build deterministic fictional banking inputs; only report-gen exports reports.

The builder writes YAML, synthetic PNG fixtures and small scanner/annex inputs.
It deliberately does not render PDF, DOCX, HTML or Markdown report documents.
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

import cvss
import engine
import finding_imports
import validate
import workflows
import yaml
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

CASE = 'HORIZONTE-AUSTRAL-2026'
DATE = '2026-10-16'
NAMESPACE = uuid.UUID('78b5aeec-030c-5e27-a0d0-9b538b337546')
WARNING = 'SIMULACIÓN DOCUMENTAL: organización, activos, resultados y personas ficticios.'
PRIVATE_MARKER = 'HORIZONTE_PRIVATE_INBOX_DO_NOT_PUBLISH_2026'
REDACTION_MARKER = 'HORIZONTE_SYNTHETIC_REDACTION_CANARY_2026'
METADATA_MARKER = 'HORIZONTE_PRIVATE_IMAGE_METADATA_2026'
LONG_URL = ('https://docs.horizonte.example/architecture/payment-authorisation-and-reconciliation/'
            '2026-10-16/operation-0123456789abcdef0123456789abcdef0123456789abcdef'
            '?case=HORIZONTE-AUSTRAL&control=mandate%2Drevocation&language=pt-BR#revisão-açaí-ñ')

ASSETS = [
    ('Banca de personas', 'personas.horizonte.example', '192.0.2.10', 'web', 'Canales digitales'),
    ('Banca de empresas', 'empresas.horizonte.example', '192.0.2.11', 'web', 'Pagos corporativos'),
    ('API de transferencias', 'pagos.horizonte.example', '192.0.2.12', 'api', 'Pagos corporativos'),
    ('Aplicación móvil y su API', 'movil.horizonte.example', '192.0.2.13', 'mobile', 'Canales digitales'),
    ('Servicio de identidad', 'identidad.horizonte.example', '192.0.2.14', 'identity', 'Identidad y acceso'),
    ('Directorio del laboratorio', 'directorio.horizonte.example', '198.51.100.20', 'directory', 'Plataforma interna'),
    ('Estación administrativa', 'salto.horizonte.example', '198.51.100.21', 'host', 'Plataforma interna'),
    ('Almacenamiento documental', 'custodia.horizonte.example', '198.51.100.22', 'cloud', 'Datos y nube'),
    ('Trabajador de conciliación', 'conciliacion.horizonte.example', '198.51.100.23', 'host', 'Pagos corporativos'),
    ('Observabilidad y auditoría', 'auditoria.horizonte.example', '203.0.113.30', 'logging', 'Detección y respuesta'),
    ('Pasarela de tercero ficticio', 'tercero.horizonte.example', '203.0.113.31', 'third-party', 'Integraciones'),
    ('Orquestador de recuperación', 'recuperacion.horizonte.example', '203.0.113.32', 'host', 'Continuidad'),
]

# Title, asset index, severity, CWE, root group, description, impact, remediation.
FINDINGS = [
    ('Autorización cruzada en instrucciones de transferencia', 2, 'critical', 'CWE-862', 0,
     'El guion permite que una identidad de la organización A consulte y modifique una instrucción cuyo propietario es B. La comprobación de sesión se efectúa antes de resolver el recurso, pero la política no enlaza sujeto, organización y operación. Se comparan objetos equivalentes y se excluye el comportamiento de un administrador global.',
     'Una autorización incorrecta en la operación modelada podría afectar confidencialidad, integridad y disponibilidad del servicio de pagos. No se ha transferido dinero ni se ha contactado una API bancaria.',
     'Evaluar autorización sobre el recurso resuelto en cada lectura, modificación y ejecución. Usar un contexto organizacional del servidor y rechazar identificadores fuera de ese contexto.'),
    ('Delegación administrativa sin límite de privilegios', 5, 'critical', 'CWE-269', 0,
     'Una cuenta sintética destinada a inventario hereda capacidad de modificar pertenencia a grupos administrativos. La relación aparece en un modelo local de permisos; no existe consulta a un directorio real. La ruta exige identidad de laboratorio y se separa de cualquier acceso a sistemas operativos.',
     'En el escenario, el fallo ampliaría la autoridad de una cuenta ordinaria y comprometería la administración central. La puntuación es un supuesto del caso, no una medición de explotación.',
     'Reducir la delegación al conjunto mínimo de atributos; separar inventario y administración. Revisar herencia y propietarios, y verificar el rechazo de cambios administrativos con la identidad restringida.'),
    ('Paquetes de recuperación aceptados sin vínculo de integridad', 11, 'critical', 'CWE-494', 2,
     'El catálogo ficticio conserva nombres de paquetes, pero no relaciona la copia aprobada con los bytes restaurados. Dos archivos diferentes pueden compartir nombre y fecha de presentación. El ensayo descrito usa texto inerte y nunca descarga, ejecuta ni instala software.',
     'Aceptar una copia distinta de la revisada podría reintroducir configuración incompatible o modificar la lógica de recuperación. No se ha alterado ninguna copia real ni ejecutado contenido externo.',
     'Vincular manifiesto, hash y versión de cada dependencia a una aprobación verificable. Rechazar cambios de bytes y probar el procedimiento completo en un entorno desconectado.'),
    ('Revocación de sesión no propagada al trabajador asíncrono', 4, 'high', 'CWE-613', 0,
     'La maqueta separa revocación de identidad y consumo de mensajes. Un mensaje preparado antes de revocar conserva una decisión de autorización antigua. La condición relevante es el momento de ejecución, no sólo la recepción inicial; los plazos usan un reloj simulado.',
     'El escenario permitiría ejecutar operaciones ya no autorizadas durante una ventana de propagación. No se afirma una duración observada ni persistencia sobre servicios reales.',
     'Reevaluar permisos en el consumo; versionar el mandato y documentar la semántica de revocación. Cancelar operaciones pendientes mediante un flujo idempotente y auditable.'),
    ('Doble aprobación que admite el mismo sujeto por dos canales', 1, 'high', 'CWE-841', 0,
     'La política ilustrada diferencia canales, pero no identidades: la misma persona ficticia solicita en web y aprueba desde móvil. El identificador de sujeto permanece estable y la demostración no depende de contraseñas, tokens ni técnicas de evasión.',
     'La separación de funciones aparente permitiría aprobar una instrucción sin revisión independiente dentro del modelo. No se interpreta la mera existencia de dos interfaces como doble control.',
     'Aplicar separación por sujeto y conflicto de funciones. Invalidar aprobaciones cuando cambie el importe, beneficiario o mandato, y conservar una explicación verificable de la decisión.'),
    ('Caché móvil conserva comprobantes después de cerrar sesión', 3, 'high', 'CWE-922', 1,
     'El diseño de muestra almacena un comprobante sintético en una caché asociada al dispositivo y no a la sesión. Tras un cierre lógico, una segunda identidad local podría recuperar la misma vista. Sólo se representan identificadores inventados.',
     'La reutilización del dispositivo podría revelar datos de otra identidad del escenario. No se han extraído datos de un teléfono ni se demuestra compromiso del sistema móvil.',
     'Vincular caché y claves a la identidad activa; eliminar contenido sensible al cerrar sesión. Probar cambio de usuario, proceso reiniciado y funcionamiento sin conexión.'),
    ('Enlaces documentales duraderos sin revocación individual', 7, 'high', 'CWE-284', 1,
     'Un enlace del caso concede acceso a un documento más allá de la retirada del permiso de su destinatario. La vigencia está modelada como un contrato separado del directorio de acceso. El enlace reservado no contiene un secreto operativo.',
     'El modelo mantendría exposición de documentación tras revocar a un destinatario. No se presupone acceso a otros objetos ni visibilidad pública del almacenamiento.',
     'Adoptar vigencia corta y revocación por vínculo; validar permiso actual antes de servir contenido. Registrar motivo y responsable de toda extensión de vigencia.'),
    ('Reintentos de liquidación no comparten clave de idempotencia', 8, 'high', 'CWE-362', 2,
     'Dos entregas del mismo evento conservan identificadores de transporte diferentes y el simulador las interpreta como intenciones nuevas. Se distinguen explícitamente intención comercial, intento de transporte y resultado contable.',
     'La condición ficticia duplicaría un asiento lógico o dificultaría conciliación. Los importes y cuentas son etiquetas simbólicas; no existe conexión a sistemas financieros.',
     'Reservar una clave estable por intención y hacer atómica su evaluación con el cambio de estado. Definir resultado recuperable para reintentos y fallos entre confirmación y respuesta.'),
    ('Alcance excesivo de credenciales de integración delegadas', 10, 'high', 'CWE-250', 0,
     'El tercero representado recibe un rol capaz de consultar y modificar conjuntos ajenos a su finalidad. El caso documenta una matriz de permisos inventada y no contiene credenciales. La autorización de salida se separa del transporte seguro.',
     'Un uso incorrecto del rol tendría alcance mayor que el servicio contratado en la ficción. No se atribuye una vulnerabilidad a un proveedor existente.',
     'Conceder permisos por operación y recurso; separar lectura, solicitud y aprobación. Mantener pruebas negativas por integración y una retirada de acceso independiente de la rotación.'),
    ('Restauración reabre permisos revocados en una copia antigua', 11, 'high', 'CWE-863', 2,
     'La restauración sintética devuelve contenido y ACL a un punto anterior a la revocación. Un registro de restricciones más reciente permanece fuera del manifiesto. La lectura correcta del archivo no basta para declarar recuperado el servicio.',
     'El caso reactivaría accesos que el negocio ya retiró. La ausencia de pérdida de archivos no demuestra conservación de política ni de obligaciones documentales.',
     'Restaurar restricciones junto al contenido y reconciliar revocaciones posteriores. Bloquear reapertura hasta demostrar lectura autorizada y rechazo de identidades retiradas.'),
    ('Diferencias de autorización entre detalle y exportación masiva', 0, 'medium', 'CWE-639', 0,
     'La vista individual filtra por organización, mientras la consulta de exportación usa un filtro opcional recibido del cliente. Una fila sintética de otra organización aparece únicamente en el resultado masivo.',
     'La inconsistencia podría divulgar parte del conjunto documental modelado. No se extrapola a todos los recursos ni se afirma exposición completa del banco.',
     'Reutilizar el mismo predicado de autorización en listados, detalles y exportaciones. Probar lotes vacíos, mezcla de organizaciones y recursos eliminados durante el proceso.'),
    ('Límites de recuperación de cuenta aplicados sólo por dispositivo', 4, 'medium', 'CWE-307', 0,
     'El flujo de muestra cuenta intentos por dispositivo pero omite una agrupación por cuenta. Los valores representados son secuencias locales; no se envían correos, SMS ni peticiones reales.',
     'La política modelada podría permitir más intentos de los previstos y generar carga de atención. No se estima una probabilidad de toma de cuenta a partir de este guion.',
     'Combinar límites por cuenta, origen y operación con respuestas uniformes. Probar recuperación legítima y evitar bloqueos permanentes inducidos por terceros.'),
    ('Redacción incompleta de identificadores en registros de soporte', 9, 'medium', 'CWE-532', 3,
     'Un mensaje de soporte incluye un identificador sintético que no aparece en el listado de campos redactados. Las pruebas de publicación deben eliminar el marcador de control sin borrar información técnica necesaria para correlación.',
     'La distribución del registro podría aumentar exposición innecesaria en el escenario. El marcador empleado fue inventado para comprobar censura literal.',
     'Definir esquema de campos permitidos y redactar antes de persistir. Mantener identificadores de correlación no sensibles y comprobar tanto vistas como exportaciones.'),
    ('Cadena de eventos pierde correlación durante cambio de cola', 8, 'medium', 'CWE-778', 3,
     'Al mover un mensaje entre colas, el ejemplo sustituye la correlación comercial por un identificador temporal. El resultado final existe, pero la trazabilidad ya no permite relacionarlo de forma inequívoca con autorización y reintento.',
     'La investigación ficticia requeriría reconstrucción manual y podría confundir duplicados con operaciones diferentes. No se afirma que el evento se haya perdido físicamente.',
     'Preservar correlación estable y añadir identificadores de tramo. Registrar transiciones con orden lógico, estado y motivo sin almacenar cuerpos completos de mensajes.'),
    ('Relojes desalineados alteran el orden aparente de auditoría', 9, 'medium', 'CWE-778', 3,
     'El caso utiliza dos relojes con desfase conocido y muestra que ordenar sólo por fecha de pared invierte autorización y ejecución. No existe medición temporal de una infraestructura real.',
     'La secuencia resultante dificultaría explicar una decisión y delimitar una ventana de investigación. Un timestamp preciso en apariencia no acredita sincronización.',
     'Conservar tiempo de pared, fuente temporal y secuencia lógica. Alertar por deriva y evitar usar la hora de recepción como sustituto del momento de decisión.'),
    ('Vínculo OAuth sin comprobación consistente de intención', 3, 'medium', 'CWE-352', 0,
     'La maqueta conserva el estado de navegación pero no lo enlaza siempre a la intención de vinculación iniciada. La comparación utiliza dos transacciones sintéticas y ningún proveedor externo.',
     'El escenario podría asociar una respuesta con una intención diferente. No demuestra captura de credenciales ni acceso a una cuenta real.',
     'Asociar intención, sesión y respuesta con valores de un solo uso. Validar expiración y consumo atómico; comprobar abandono y retorno a una sesión distinta.'),
    ('Política CORS permite orígenes de laboratorio en entorno estable', 2, 'medium', 'CWE-942', 1,
     'Una lista de orígenes inventada conserva una entrada de preproducción al representar la configuración estable. La fila documenta un fallo de separación de configuración, no una prueba ejecutada desde un navegador remoto.',
     'La confianza del escenario se extiende a un origen innecesario. La exposición concreta dependería de los recursos, credenciales y métodos autorizados.',
     'Derivar listas por entorno y exigir revisión de cambios. Probar origen permitido, rechazado, nulo y normalización de esquema, host y puerto.'),
    ('Referencia documental conserva acceso al reemplazar una versión', 7, 'medium', 'CWE-200', 1,
     'La URL reservada cambia de contenido cuando se reemplaza una versión y conserva la decisión previa de acceso. El modelo compara hash del contenido y versión de política, sin hospedar ningún documento.',
     'La misma referencia podría entregar un documento que nunca fue revisado para ese destinatario. No se presume equivalencia entre nombre y contenido.',
     'Enlazar permisos a versión inmutable o reevaluarlos al resolver la referencia. Notificar sustituciones y conservar hashes de las revisiones aprobadas.'),
    ('Cabeceras de protección incompletas en páginas auxiliares', 0, 'low', 'CWE-693', 1,
     'La página principal del ejemplo declara controles de navegador, pero la página auxiliar omite algunos. La tabla contiene respuestas HTTP inventadas para revisar consistencia de plantillas.',
     'La diferencia reduce defensa adicional en el escenario, sin demostrar una cadena de explotación. La valoración no sustituye el contexto de las funciones presentes.',
     'Aplicar una política central coherente y justificar excepciones por plantilla. Comprobar respuestas de error, autenticación y contenido estático por separado.'),
    ('Mensajes de error distinguen identificadores inexistentes', 4, 'low', 'CWE-204', 1,
     'Dos respuestas sintéticas difieren en texto cuando el identificador existe o no. No se han enumerado usuarios; se comparan únicamente dos entradas creadas para el caso.',
     'El modelo ofrece una señal limitada sobre existencia de identidades. No acredita exposición de otros atributos ni acceso autenticado.',
     'Uniformar mensajes y rutas de recuperación sin degradar soporte legítimo. Verificar equivalencia del estado y evitar afirmar igualdad temporal sin medirla.'),
    ('Versiones internas presentes en mensajes de diagnóstico', 6, 'low', 'CWE-209', 3,
     'Una respuesta de diagnóstico de muestra incluye nombres y versiones ficticias. Se separa información necesaria para soporte de datos destinados a usuarios finales.',
     'La información reduce incertidumbre sobre el componente modelado, pero por sí sola no demuestra una vulnerabilidad explotable.',
     'Usar identificadores de incidencia y mantener detalle técnico en una vista restringida. Añadir una prueba de contenido permitido a las respuestas de error.'),
    ('URLs extensas se truncan en el procedimiento de soporte', 10, 'low', 'CWE-223', 3,
     'El procedimiento manual del escenario copia sólo una parte de una referencia larga. La cadena completa debe preservarse en el informe, incluidas secuencias codificadas, parámetros y fragmento Unicode.',
     'La referencia incompleta dificulta reproducibilidad documental. Se trata de una observación ficticia del proceso; no presupone que report-gen tenga este defecto.',
     'Usar campos estructurados y validar igualdad del destino completo. Conservar texto legible y enlace navegable, sin introducir espacios o caracteres invisibles.'),
    ('Inventario de dependencias con responsables documentados', 11, 'info', 'CWE-1104', 2,
     'Se registra como observación informativa una matriz de componentes, responsables y ventanas de revisión. No se declara una vulnerabilidad ni incumplimiento por la mera existencia de dependencias.',
     'Sin impacto técnico asignado. La fila permite comprobar CVSS cero, inventario informativo y separación entre recomendación de gestión y vulnerabilidad.',
     'Mantener propietario, propósito y fecha de revisión. Separar software retirado de excepciones aprobadas y conservar una razón para cada dependencia.'),
    ('Criterios de aceptación distinguen corrección y verificación', 9, 'info', 'CWE-703', 3,
     'El caso documenta la distinción entre un cambio comunicado, una prueba ejecutada y una conclusión verificada. Los estados del informe son parte de la ficción y nunca constituyen evidencia de una auditoría real.',
     'Sin impacto técnico asignado. La observación informa sobre trazabilidad de decisiones, no sobre la seguridad de una institución existente.',
     'Exigir alcance, fecha, evidencia y evaluador en cada retest. Mantener visible todo resultado parcial, no verificable o sin fecha.'),
]

VECTORS = {
    'critical': 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
    'high': 'CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N',
    'medium': 'CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N',
    'low': 'CVSS:3.1/AV:N/AC:H/PR:L/UI:R/S:U/C:L/I:N/A:N',
    'info': 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N',
}
V4 = {
    3: 'CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N',
    23: 'CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N',
}
ROOT_GROUPS = [
    ('Autorización y separación de funciones', 'Decisiones de permiso sin contexto completo de sujeto, recurso, operación y momento.', 'Centralizar el contrato de autorización; mantener pruebas positivas y negativas independientes.'),
    ('Ciclo de vida y exposición de datos', 'Controles de acceso, vigencia y eliminación aplicados de manera desigual entre canales.', 'Definir clasificación, conservación y revocación por flujo; verificar cada consumidor.'),
    ('Consistencia y recuperación', 'Transiciones de estado y recuperación sin una identidad estable de operación y contenido.', 'Usar invariantes verificables, manifiestos de dependencias y reapertura controlada.'),
    ('Trazabilidad y calidad de la evidencia', 'Eventos y decisiones documentales sin información suficiente para reproducir su significado.', 'Conservar correlación, autoría y límites; no transformar ausencia de evidencia en conclusión positiva.'),
]


def uid(label):
    return str(uuid.uuid5(NAMESPACE, label))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def write(path, blob):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob if isinstance(blob, bytes) else blob.encode('utf-8'))


def font(size, mono=False):
    name = 'themes/fonts/DejaVuSansMono.ttf' if mono else 'exporters/fonts/DejaVuSans.ttf'
    return ImageFont.truetype(str(ROOT / name), size)


def evidence_image(path, number, finding):
    """Clearly drawn synthetic evidence, never a claimed bank screenshot."""
    title, asset_index, severity = finding[:3]
    portrait = number in (6, 18)
    width, height = (760, 840) if portrait else (1360, 400)
    canvas = Image.new('RGB', (width, height), '#f3f7fb')
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, 77), fill='#132940')
    draw.text((28, 21), f'BHA / F{number:02d} / EVIDENCIA SINTÉTICA', font=font(23), fill='white')
    for line, value in enumerate(textwrap.wrap(title, 49 if portrait else 87)):
        draw.text((28, 100 + line * 32), value, font=font(22), fill='#132940')
    rows = [('Activo', ASSETS[asset_index][1]), ('Entrada', f'OBJETO-SINTETICO-{number:02d} / identidad A'),
            ('Contrato', 'Separar permiso, ejecución y resultado'), ('Escenario', f'{severity.upper()} / valoración inventada'),
            ('Resultado', 'MODELO LOCAL; SIN TRÁFICO NI DATOS REALES')]
    y = 186 if portrait else 166
    for index, (label, value) in enumerate(rows):
        if portrait:
            draw.rounded_rectangle((24, y, width - 24, y + 95), radius=8, fill='white', outline='#cbd8e5')
            draw.text((42, y + 12), label.upper(), font=font(17), fill='#3d6e87')
            for line, part in enumerate(textwrap.wrap(value, 45)):
                draw.text((42, y + 39 + line * 22), part, font=font(17, True), fill='#132940')
            y += 107
        else:
            draw.rectangle((26, y, width - 26, y + 32), fill='#ffffff' if index % 2 == 0 else '#e9f0f7')
            draw.text((39, y + 6), label, font=font(17), fill='#3d6e87')
            draw.text((230, y + 6), value, font=font(17, True), fill='#132940')
            y += 35
    draw.text((28, height - 37), f'{CASE}  |  {DATE}  |  NO ES UNA CAPTURA REAL', font=font(15), fill='#3d6e87')
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('Description', METADATA_MARKER)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, format='PNG', pnginfo=metadata, optimize=False)


def branding_images(directory):
    logo = Image.new('RGB', (1000, 180), '#132940')
    draw = ImageDraw.Draw(logo)
    draw.line([(45, 124), (85, 56), (125, 124)], fill='#5dd8bd', width=10)
    draw.line((45, 124, 125, 124), fill='#5dd8bd', width=10)
    draw.text((165, 42), 'HORIZONTE AUSTRAL', font=font(45), fill='white')
    draw.text((168, 108), 'BANCO FICTICIO / LABORATORIO DOCUMENTAL', font=font(22), fill='#a8c4d7')
    logo.save(directory / 'logo.png', format='PNG')
    cover = Image.new('RGB', (1400, 380), '#132940')
    draw = ImageDraw.Draw(cover)
    for index, label in enumerate(('IDENTIDAD', 'PAGOS', 'CUSTODIA', 'RECUPERACIÓN')):
        x = 30 + index * 345
        draw.rounded_rectangle((x, 70, x + 300, 270), radius=16, outline='#5dd8bd', width=3)
        draw.text((x + 20, 106), f'0{index + 1}', font=font(48), fill='#5dd8bd')
        draw.text((x + 20, 205), label, font=font(22), fill='white')
    draw.text((34, 324), 'MODELO FICTICIO / 12 ACTIVOS / SIN SERVICIOS REALES', font=font(24), fill='#a8c4d7')
    cover.save(directory / 'cover.png', format='PNG')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(str(v).replace('|', '\\|').replace('\n', '<br>') for v in row) + ' |' for row in rows])


def sections(findings):
    counts = Counter(f['severity'] for f in findings)
    count_text = ', '.join(f'{counts[s]} {name}' for s, name in [('critical', 'críticos'), ('high', 'altos'), ('medium', 'medios'), ('low', 'bajos'), ('info', 'informativos')])
    controls = []
    for n, finding in enumerate(findings, 1):
        for suffix, test in [('P', 'Caso permitido con sujeto y recurso autorizados'), ('N', 'Caso rechazado sin efecto de negocio')]:
            controls.append([f'BHA-{n:02d}-{suffix}', f"[{finding['id']}](#{finding['id']})", test,
                             'Datos sintéticos; resultado inventado para el documento, no una ejecución bancaria.'])
    history = [dict(version='0.1', date='2026-10-12', author='Equipo ficticio BHA', notes='Inventario y contratos sintéticos.'),
               dict(version='0.2', date='2026-10-14', author='Equipo ficticio BHA', notes='Guion de hallazgos y seguimiento simulado.'),
               dict(version='1.0', date=DATE, author='Equipo ficticio BHA', notes='Caso documental completo para validar report-gen.')]
    return [
        dict(key='confidentiality', body=WARNING + '\n\nEste documento es una simulación de control de calidad. No describe una auditoría real, no contiene información bancaria ni acredita cumplimiento normativo. Los dominios terminan en .example y las direcciones usan redes de documentación. Ningún enlace fue contactado. Los estados de hallazgo, CVSS, cobertura y retest representan el guion inventado.\n\nLas figuras fueron dibujadas de forma determinista para comprobar el manejo de evidencia; no son capturas de una aplicación bancaria. Los nombres de roles son ficticios. La distribución del ejemplo debe conservar esta declaración.'),
        dict(key='document_control', version_history=history, distribution='Ejemplo público reutilizable, siempre identificado como ficticio. Fuentes privadas y marcadores de prueba permanecen separados de la entrega pública.\n\n**Idioma del contenido:** español. Las variantes EN y PT prueban etiquetas, navegación y formatos locales; no constituyen traducciones de la prosa del caso.'),
        dict(key='contacts'),
        dict(key='executive_summary', summary=f'Banco Horizonte Austral es una entidad inventada con banca de personas, empresas, canal móvil, pagos asíncronos y custodia documental. El alcance contiene **12 activos**, **24 hallazgos ({count_text})** y **3 cuadernos de máquinas**. Las máquinas no se cuentan como vulnerabilidades. La clasificación procede de vectores hipotéticos calculados por report-gen y conserva coherencia con las bandas de severidad.\n\nLa prioridad del escenario es evitar que una autorización correcta al iniciar una operación sobreviva a la pérdida del permiso o se aplique a un recurso distinto. La segunda prioridad es mantener una identidad estable de intención para que reintentos y recuperaciones no produzcan decisiones duplicadas. La tercera es conservar una trazabilidad útil sin incluir información innecesaria en logs o entregas.\n\nLas tres cadenas descritas son relaciones de diseño, no recorridos ejecutados. Un cierre registrado en la ficción no equivale a una corrección real. El caso incluye resultados abiertos, parciales, corregidos y no verificables para ejercer los estados de seguimiento; cada uno conserva una explicación y una evidencia sintética.\n\nLa entrega está dirigida a dos audiencias. Dirección debe entender impacto, prioridad y responsables; los equipos técnicos deben poder localizar condiciones previas, controles negativos, criterios de cierre y referencias. La puntuación CVSS no expresa exposición real del banco ficticio ni probabilidad cuantificada de pérdida.\n\nEl criterio de éxito de este ejercicio es documental: preservar estructura, imágenes, referencias, tablas y decisiones de publicación en PDF, DOCX, Markdown e HTML. Una exportación correcta valida el generador dentro del caso ejecutado; no demuestra ausencia universal de bugs ni certifica una organización.'),
        dict(key='risk_posture', posture='La postura modelada combina dependencias comunes entre canales. Cambiar un control de identidad puede afectar pagos, enlaces documentales y recuperación; por eso la priorización usa consecuencias de negocio e invariantes compartidas.\n\n' + table(['Dimensión', 'Riesgo ficticio', 'Indicador propuesto'], [['Confidencialidad', 'Acceso cruzado y conservación innecesaria', 'Casos negativos rechazados / casos negativos preparados'], ['Integridad', 'Aprobación sin independencia y duplicados', 'Intenciones con un único resultado recuperable'], ['Continuidad', 'Copias legibles con política antigua', 'Restauraciones con contenido y restricciones verificadas'], ['Trazabilidad', 'Eventos sin relación inequívoca', 'Operaciones con correlación completa y explicación']]) + '\n\nNo se asignan pérdidas monetarias, porcentajes de madurez o conformidad regulatoria. Los indicadores son propuestas y no resultados medidos.'),
        dict(key='strategic_recommendations', recommendations='1. Formalizar contratos de autorización por recurso y momento de ejecución.\n2. Separar intención, intento de transporte y resultado contable.\n3. Integrar revocaciones y restricciones en la recuperación.\n4. Mantener pruebas de regresión positivas y negativas por canal.\n5. Revisar evidencia y exposición de datos antes de distribuir informes.\n\n> La aceptación del riesgo pertenece a una decisión empresarial documentada; el cambio de un estado no crea una aprobación real.\n\nCada iniciativa debe tener propietario, dependencia, criterio de aceptación y reversión. La prioridad ejecutiva no sustituye el análisis de impacto de un despliegue.'),
        dict(key='scope', objectives='Modelar las fronteras de confianza de doce activos y comprobar la documentación de sus controles. El ejemplo cubre web, API, móvil, identidad, directorio, administración, nube, procesamiento asíncrono, observabilidad, tercero y recuperación.\n\nSe excluyen transacciones reales, redes de pago, infraestructura pública, datos personales, ingeniería social, denegación de servicio y pruebas contra terceros existentes. No se envían peticiones a los identificadores del alcance.', assumptions='Sólo datos fabricados y operaciones locales de composición documental. Las direcciones 192.0.2.0/24, 198.51.100.0/24 y 203.0.113.0/24 identifican redes de documentación. Los roles solicitante, aprobador y operador no representan personas reales. Todas las conclusiones de seguridad son parte de la ficción.'),
        dict(key='methodology', approach='Para cada control se fija una condición previa, una entrada permitida, una entrada rechazada y una consecuencia observable. Los identificadores de hallazgos y activos permanecen estables entre variantes de idioma. El conjunto usa trazabilidad de requisitos, revisión de permisos, contratos de estado y criterios de cierre.\n\nLa prueba del generador compara la fidelidad de texto e imágenes y la estructura de las salidas. Los resultados de esa prueba deben documentarse por separado del guion bancario.', standards='Las referencias CWE sirven como etiquetas técnicas orientativas. No se afirma cumplimiento con una norma bancaria, PCI DSS, ISO o NIST ni se usa este ejemplo como interpretación normativa.', information_gathering='Inventario compuesto desde cero; no hubo búsqueda, OSINT ni contacto con una organización. Los archivos CSV, Burp XML, Nuclei JSONL, Nmap XML y SARIF son entradas fabricadas para comprobar importación.', enumeration='Los puertos y nombres de servicio pertenecen al guion. La existencia de una fila de inventario no acredita descubrimiento de un servicio real.', exploitation='Los recorridos contienen solicitudes HTTP y pseudocódigo inertes para explicar contratos. No incluyen sesiones operativas, payloads de explotación ni instrucciones para atacar una entidad.', post_exploitation='Las cadenas narrativas relacionan impactos hipotéticos. No hubo acceso inicial, elevación, movimiento lateral ni persistencia en sistemas ajenos.', cleanup='El proyecto conserva sólo datos sintéticos. Al terminar el ejercicio se deben cerrar servidores locales y conservar los manifiestos de resultados del generador, sin convertir los estados inventados en evidencia técnica real.'),
        dict(key='findings_summary'), dict(key='findings'),
        dict(key='attack_narrative', narrative='### Cadena A: identidad, aprobación y ejecución\n\n[F04](#F04) describe revocación tardía; [F05](#F05) modela doble aprobación por el mismo sujeto; [F08](#F08) añade un reintento sin identidad comercial estable. Juntas muestran por qué validar una solicitud no garantiza la corrección de una liquidación. No se ejecutó esta cadena.\n\n### Cadena B: administración y recuperación\n\n[F02](#F02) amplía autoridad en el directorio ficticio, [F03](#F03) pierde el vínculo de integridad y [F10](#F10) restaura permisos antiguos. El corte propuesto exige autorización mínima, manifiesto de bytes y reconciliación de restricciones. La cadena es un modelo de dependencias, no una intrusión.\n\n### Cadena C: datos y explicación\n\n[F07](#F07) conserva un vínculo documental; [F13](#F13) deja un identificador en soporte; [F14](#F14) pierde correlación. Una investigación de la ficción necesitaría reunir las tres fronteras sin publicar contenido sensible. La ausencia de correlación no prueba por sí sola exfiltración.\n\nNinguna cadena implica que todos sus pasos sean simultáneamente alcanzables. El análisis de precondiciones debe preceder cualquier conclusión en un entorno real.'),
        dict(key='remediation_plan', overview='La planificación usa cuatro grupos de causa raíz y conserva acciones específicas por hallazgo. El orden depende del riesgo de cambiar autorización, colas y restauración al mismo tiempo. Todo plazo es ficticio.\n\n' + table(['Etapa', 'Responsable ficticio', 'Condición de salida'], [['Contención', 'Identidad y pagos', 'Operaciones de mayor impacto ligadas a sujeto y recurso'], ['Corrección', 'Canales, datos y plataforma', 'Contratos coherentes y pruebas negativas documentadas'], ['Validación', 'Revisión independiente', 'Resultado reproducible, evidencia y límites registrados'], ['Sostenimiento', 'Continuidad y detección', 'Regresión, restauración y trazabilidad mantenidas']]), short_term='En siete días ficticios: revisar las tres hipótesis críticas, reducir permisos innecesarios y aprobar contratos de revocación e idempotencia. Conservar un plan de reversión que mantenga consistencia de estado.', medium_term='En treinta días ficticios: armonizar canales, revisar enlaces documentales y redactar registros antes de persistir. Ejecutar la matriz de controles bajo un entorno autorizado si se construye un laboratorio real.', long_term='En noventa días ficticios: incorporar pruebas de recuperación y cambios de política a la regresión. Revisar dependencias, excepciones y criterios de aceptación sin reemplazar evidencia por métricas de actividad.'),
        dict(key='appendix', host_service_discovery=table(['Red documental', 'Activos', 'Interpretación'], [['192.0.2.0/24', '5 canales y servicios', 'Inventario ficticio'], ['198.51.100.0/24', '4 componentes internos', 'Inventario ficticio'], ['203.0.113.0/24', '3 funciones de soporte', 'Inventario ficticio; total de activos: 5 + 4 + 3 = 12.']]), exploited_hosts='Ninguno. Las tres fichas de máquinas son cuadernos sintéticos y no pruebas de compromiso.', compromised_users='Ninguno. Los nombres de roles y las cuentas A/B son etiquetas inventadas.', changes_cleanup='No se alteraron servicios bancarios. Los únicos cambios esperados corresponden al proyecto de ejemplo y a los archivos generados por report-gen.', tools_used='**Generación de informes:** report-gen y sus exportadores registrados.\n\n**Preparación de entradas:** script reproducible que escribe YAML, PNG sintéticos y archivos de importación. No genera PDF, DOCX, HTML ni el informe Markdown.\n\n**Importadores de prueba:** CSV, Burp XML, Nuclei JSONL, Nmap XML y SARIF 2.1.0 con driver y extensión autocontenida.', glossary=table(['Término', 'Uso en este caso'], [['Mandato', 'Permiso de negocio vinculado a sujeto y operación'], ['Idempotencia', 'Una intención conserva un único resultado recuperable'], ['Retest', 'Registro de repetición; aquí su resultado es ficticio'], ['Hash', 'Identidad de bytes; no acredita autoría por sí solo'], ['Causa raíz', 'Agrupación de remediaciones del guion, no conclusión forense']])),
        dict(key='bha-control-matrix', title='Anexo A — Matriz extensa de aceptación y correspondencia entre hallazgos', body='Las 48 filas siguientes permiten revisar paginación, repetición de encabezados, referencias internas y conservación del orden. Su contenido define contratos del escenario; no es un registro de 48 pruebas bancarias ejecutadas.\n\n' + table(['Control', 'Hallazgo', 'Contrato', 'Límite de la evidencia'], controls)),
        dict(key='bha-literals', title='Anexo B — Literales extensos, Unicode y preservación de destinos', body='Se conserva exactamente el destino de referencia y sus caracteres codificados. El enlace no fue consultado.\n\n[Contrato de autorización, revisión y açaí](' + LONG_URL + ')\n\n<' + LONG_URL + '>\n\n' + table(['Identificador', 'Literal', 'Comprobación'], [['REF-LARGA', LONG_URL, 'Mismo destino completo en cada formato'], ['UNICODE-LATIN', 'acción / revisão / açaí / São Paulo / ñ / Überprüfung', 'Texto Unicode y acentos conservados'], ['LITERAL-ESCAPES', 'A&B <demo> [prueba] %2D %3A', 'Entidades y caracteres legibles']]) + '\n\n```text\nHORIZONTE_LITERAL_SENTINEL\nGET /v1/operations/OBJETO-SINTETICO-01?preview=true HTTP/1.1\nHost: pagos.horizonte.example\nX-Synthetic-Only: true\nX-Correlation: HORIZONTE-0123456789abcdef0123456789abcdef0123456789abcdef\n```\n\n1. Conservar intención y sujeto.\n    1. Validar el caso permitido.\n    2. Validar el caso rechazado.\n2. Registrar resultado y limitación.\n\n> Una representación no equivale a una prueba.\n>\n> - **ES:** ejemplo ficticio.\n> - **EN:** fictional example.\n> - **PT:** exemplo fictício.'),
        dict(key='bha-annexes', title='Anexo C — Inventario de anexos y decisiones de publicación', body='Los anexos seleccionados viajan como archivos independientes en el paquete de entrega; no se presupone que el cuerpo PDF incruste su contenido. El proyecto conserva además un anexo privado excluido.\n\n' + table(['Archivo', 'Decisión', 'Contenido'], [['inventario-activos.csv', 'Incluido y revisado', '12 activos sintéticos'], ['matriz-de-aceptacion.csv', 'Incluido y revisado', '48 contratos de control'], ['manifiesto-del-caso.json', 'Incluido y revisado', 'Conteos y límites del escenario'], ['criterios-de-entrega.md', 'Incluido y revisado', 'Contrato de fidelidad documental'], ['notas-internas.txt', 'Privado, excluido', 'Marcador sintético para verificar aislamiento']]) + '\n\nLas notas privadas, los originales de imagen y sus metadatos no forman parte de la publicación. La redacción literal se configura de forma explícita sobre un marcador inventado; no constituye una detección automática completa de secretos.'),
    ]


def finding_rows():
    rows = []
    for n, spec in enumerate(FINDINGS, 1):
        title, asset, severity, cwe, group, description, impact, remediation = spec
        vector = V4.get(n, VECTORS[severity])
        calculated = cvss.score(vector)
        assert calculated['severity'] == severity, (n, calculated)
        fid = f'F{n:02d}'
        state = ('open', 'in_progress', 'reported_fixed', 'verified_fixed', 'accepted', 'not_verified')[(n - 1) % 6]
        verification = 'confirmed' if state in ('open', 'in_progress', 'reported_fixed', 'verified_fixed', 'accepted') else 'inconclusive'
        row = dict(id=fid, uid=uid(fid), mode='vuln', title=title + ' [SIMULADO]', severity=severity,
                   cvss=calculated['score'], cvss_vector=vector, cvss_version=vector.split('/')[0].split(':')[1], cwe=cwe,
                   description_md=description + '\n\n**Naturaleza de la evidencia:** modelo sintético; los estados y resultados son inventados para este informe.',
                   impact_md=impact, remediation_md=remediation,
                   affected=f'https://{ASSETS[asset][1]}/scenario/{fid.lower()}', owner=ASSETS[asset][4] + ' [rol ficticio]',
                   due_date=f'2026-11-{(n - 1) % 20 + 1:02d}', status=state, verification=verification,
                   asset_uids=[uid(f'asset-{asset}')], evidence_uids=[uid(f'evidence-{n}')], root_cause_uid=uid(f'root-{group}'),
                   closure_criteria_md='Demostrar caso permitido y rechazo sin efecto de negocio; conservar identidad del recurso, versión, correlación y evidencia revisada. El criterio pertenece al guion ficticio.',
                   walkthrough=[dict(lead='Contrato y control local', text_md='1. Preparar dos identidades y objetos inventados.\n2. Comparar la decisión del caso permitido y del rechazado.\n3. Conservar resultado y limitación, sin enviar tráfico externo.')],
                   references=[f'https://docs.horizonte.example/controls/{fid.lower()}#criterio-de-aceptación'])
        if n in (1, 8, 13, 22):
            row['walkthrough'].append(dict(lead='Registro documental inerte', command=f'CASE={CASE}\nFINDING={fid}\nSUBJECT=IDENTIDAD-FICTICIA-A\nRESOURCE=OBJETO-SINTETICO-{n:02d}\nNETWORK_EXECUTION=NONE\nEXPECTED=PERMIT_OR_DENY_AS_DOCUMENTED'))
        if n == 12:
            row['walkthrough'].append(dict(lead='Matriz de evidencia enlazada', text_md=table(
                ['Patrón', 'Evidencia sintética'], [
                    ['Una imagen con destino externo', '[![BHA tabla UNO](img/evidence-12.png)](https://docs.horizonte.example/evidence#control)'],
                    ['Dos imágenes bajo el mismo enlace', '[![BHA tabla DOS](img/evidence-11.png) ![BHA tabla TRES](img/evidence-12.png)](https://docs.horizonte.example/evidence#multiple)'],
                    ['Prosa e imagen enlazadas al hallazgo', '[Antes![BHA tabla CUATRO](img/evidence-12.png)Después](#F12)'],
                ])))
        if n == 13:
            row['description_md'] += '\n\nMarcador de redacción de prueba: ' + REDACTION_MARKER + '.'
        if n == 22:
            row['references'].append(LONG_URL)
            row['description_md'] += '\n\n[Referencia íntegra de la prueba](' + LONG_URL + ')'
        if state == 'reported_fixed':
            row['reported_remediation'] = 'Comunicación ficticia: se modificó el contrato del simulador. Requiere revisión; no representa un cambio bancario real.'
        if state == 'accepted':
            row['reported_remediation'] = 'Aceptación ficticia documentada sólo para ejercitar el estado; revisión programada. No hay aprobación de una entidad real.'
        if state == 'verified_fixed':
            row['retests'] = [dict(uid=uid(f'retest-{n}-fixed'), tested_on='2026-10-15', assessor='Revisor ficticio independiente', result='fixed', notes_md='**RESULTADO INVENTADO:** el guion de la maqueta cierra el caso. Evidencia sintética; no hubo retest sobre un sistema bancario.', evidence_uids=[uid(f'evidence-{n}')])]
        if n in (7, 14, 21, 24):
            result = {7: 'open', 14: 'partial', 21: 'not_verified', 24: 'not_verified'}[n]
            row['retests'] = [dict(uid=uid(f'retest-{n}-current'), tested_on='2026-10-15', assessor='Revisor ficticio de seguimiento', result=result, notes_md='**RESULTADO INVENTADO:** registro de seguimiento para probar el documento.\n\n' + table(['Control', 'Lectura del guion'], [['Positivo', 'Operación permitida descrita'], ['Negativo', 'Rechazo o limitación según el escenario'], ['Evidencia', 'Figura fabricada, no captura real']]), evidence_uids=[uid(f'evidence-{n}')])]
        if n == 24:
            row['retests'].append(dict(uid=uid('retest-24-undated'), tested_on='', assessor='Nota heredada ficticia', result='not_verified', notes_md='Nota sin fecha; no sustituye el último registro fechado ni acredita verificación.', evidence_uids=[]))
        rows.append(row)
    return rows


def machines():
    rows = []
    for i, asset in enumerate((6, 8, 11), 1):
        name, target, address, _, owner = ASSETS[asset]
        phases = []
        for n, (phase, narrative) in enumerate([
            ('Inventario y contrato', 'Identificar componentes y dependencias ficticios. La ficha no acredita puertos descubiertos ni acceso a un host.'),
            ('Decisiones de autorización', 'Relacionar sujeto, recurso y operación con los hallazgos asociados. Conservar tanto el comportamiento permitido como el rechazado.'),
            ('Consistencia y observabilidad', 'Diferenciar intención, reintento y resultado. Registrar correlación y versión sin incluir datos personales o credenciales.'),
            ('Recuperación y cierre', 'Preparar una restauración aislada y verificar restricciones. No reabrir el flujo del modelo si una condición permanece desconocida.'),
        ], 1):
            phases.append(dict(name=phase, steps=[dict(lead=f'Paso M{i}.{n}', text_md=narrative, command=f'MODEL_ONLY=true\nMACHINE=M{i:02d}\nPHASE={n}\nNETWORK_EXECUTION=NONE')]))
        rows.append(dict(id=f'M{i:02d}', uid=uid(f'M{i:02d}'), mode='machine', title=f'{name} — cuaderno ficticio',
                         host=dict(name=target, ip=address, os='Sistema de laboratorio ficticio'),
                         open_ports='443/tcp, 8443/tcp [INVENTADOS]', summary_md=WARNING + ' Esta ficha documenta el diseño de validación local y conserva cuatro fases. No existió acceso inicial, elevación ni persistencia.',
                         status='not_verified', verification='unverified', owner=owner + ' [rol ficticio]', due_date='2026-11-30',
                         asset_uids=[uid(f'asset-{asset}')], evidence_uids=[uid(f'evidence-{(i - 1) * 6 + 1}')], phases=phases,
                         proof=[dict(name=f'modelo-M{i:02d}.txt', value=f'HORIZONTE_SYNTHETIC_PROOF_{i}_NOT_A_CAPTURED_FLAG', notes='Valor inventado; no prueba de compromiso.')]))
    return rows


def make_project(language='es'):
    """Return fresh source data. Prose stays Spanish; report chrome is localized."""
    if language not in ('es', 'en', 'pt'):
        raise ValueError('Supported languages: es, en, pt')
    findings = finding_rows()
    assets = [dict(uid=uid(f'asset-{i}'), name=a[0], target=f'{a[1]} / {a[2]}', kind=a[3], notes=f'{a[4]}; activo ficticio, no contactado.') for i, a in enumerate(ASSETS)]
    coverage = [dict(uid=uid(f'coverage-{n}-{suffix}'), asset_uid=uid(f'asset-{spec[1]}'), test=f'BHA-{n:02d}-{suffix} / {label}', status=state,
                     notes='ESTADO SIMULADO: fila del guion, no una prueba ejecutada contra un banco.')
                for n, spec in enumerate(FINDINGS, 1)
                for suffix, label, state in [('P', 'Caso permitido', 'done'), ('N', 'Caso rechazado', ('done', 'pending', 'blocked', 'not_applicable')[(n - 1) % 4])]]
    raw = PRIVATE_MARKER + '\nNota privada sintética, nunca debe aparecer en la publicación.'
    data = dict(schema_version=2, finding_sequence=24,
                meta=dict(lang=language, theme='corporativo', report_density='compact', report_title='Banco Horizonte Austral — evaluación integral ficticia',
                          report_subtitle='Banca digital, pagos, identidad, nube y continuidad / 24 hallazgos + 3 máquinas',
                          client='Banco Horizonte Austral [FICTICIO]', assessor='Equipo de auditoría ficticio BHA', assessor_title='Simulación documental / report-gen', date=DATE, version='BHA 1.0',
                          branding=dict(wordmark='HORIZONTE AUSTRAL', byline='CASO FICTICIO / SIN SISTEMAS REALES', confidential_text='FICTICIO / DATOS SINTÉTICOS', accent='#137C74', logo='img/logo.png', cover_image='img/cover.png'),
                          contacts=dict(client=[dict(name='Responsable de tecnología [ficticio]', title='Patrocinio del ejemplo', email='tecnologia@horizonte.example'), dict(name='Responsable de riesgo [ficticio]', title='Coordinación del ejemplo', email='riesgo@horizonte.example')], assessor=[dict(name='Revisor independiente [ficticio]', title='Control documental', email='revision@horizonte.example')]),
                          scope=[dict(target=a[1], description=f'{a[0]} / {a[2]} / FICTICIO') for a in ASSETS]),
                report=dict(sections=sections(findings), workflow=dict(include_assets=True, include_coverage=True, include_retest=True, include_root_causes=True)),
                findings=findings + machines(), assets=assets,
                evidence=[dict(uid=uid(f'evidence-{n}'), title=f'BHA-E{n:02d} / modelo de {spec[0]}', src=f'img/evidence-{n:02d}.png', caption=f'BHA-E{n:02d} — representación sintética de F{n:02d}; no es una captura de un banco.') for n, spec in enumerate(FINDINGS, 1)],
                coverage=coverage,
                root_cause_groups=[dict(uid=uid(f'root-{i}'), name=name, cause_md=cause + ' Hipótesis ficticia de agrupación.', remediation_md=action) for i, (name, cause, action) in enumerate(ROOT_GROUPS)],
                limitations_md='Todos los resultados de seguridad, retests, CVSS y estados de cobertura son inventados. No hubo tráfico de red a los activos ni auditoría de una entidad real. Las variantes EN/PT localizan la interfaz documental; la prosa de autor permanece en español. Las pruebas del generador y sus límites se registran por separado.',
                publication=dict(redactions=[dict(needle=REDACTION_MARKER, replacement='[CENSURADO: MARCADOR SINTÉTICO]')], exceptions=[]),
                capture_inbox=[dict(uid=uid('private-note'), kind='note', title='Nota privada de control de publicación', raw_text=raw, note='No promover a hallazgos.', created=DATE + 'T12:00:00Z', sha256=sha256(raw.encode()).hexdigest())],
                project_management=dict(archived=False, delivery_date='2026-11-30'))
    data['evidence'][0]['original'] = 'originals/evidence-01.png'
    return data


def csv_bytes(headers, rows):
    stream = StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def add_annexes(directory, data):
    public_manifest = dict(schema='report-gen-horizonte-case/1', case=CASE, date=DATE, fictional=True,
                           vulnerabilities=24, machines=3, assets=12, evidence_images=24, coverage_rows=48,
                           severity_counts=dict(Counter(f['severity'] for f in data['findings'] if f['mode'] == 'vuln')),
                           prose_language='es', presentation_language=data['meta']['lang'])
    rows = [[f'BHA-{n:02d}-{suffix}', f'F{n:02d}', label, 'SIMULADO'] for n in range(1, 25) for suffix, label in [('P', 'Permitido'), ('N', 'Rechazado')]]
    blobs = [
        ('inventario-activos.csv', csv_bytes(['nombre', 'destino', 'ipv4', 'tipo', 'responsable_ficticio'], ASSETS), True),
        ('matriz-de-aceptacion.csv', csv_bytes(['control', 'hallazgo', 'caso', 'naturaleza'], rows), True),
        ('manifiesto-del-caso.json', json_bytes(public_manifest), True),
        ('criterios-de-entrega.md', '# Criterios del caso ficticio\n\nPreservar los 24 hallazgos, 3 máquinas, 24 evidencias, 12 activos y 48 contratos.\n\nNo publicar notas privadas, originales, metadatos ni el marcador de redacción. Las variantes EN/PT mantienen prosa española declarada.\n', True),
        ('notas-internas.txt', PRIVATE_MARKER + '\nAnexo privado fabricado; excluido de la entrega.\n', False),
    ]
    attachments = []
    for name, content, included in blobs:
        blob = content if isinstance(content, bytes) else content.encode('utf-8')
        member = 'attachments/' + uuid.UUID(uid('annex-' + name)).hex + Path(name).suffix
        write(directory / member, blob)
        attachments.append(dict(uid=uid('annex-' + name), name=name, member=member, sha256=sha256(blob).hexdigest(), include=included, reviewed=included, required=included))
    data['attachments'] = attachments


def write_import_inputs(directory):
    """All input formats are manufactured and validated offline by report-gen."""
    directory.mkdir(parents=True, exist_ok=True)
    # Duplicate source identity requires the same external ID and target.
    csv_input = csv_bytes(['title', 'severity', 'affected', 'description_md', 'impact_md', 'remediation_md', 'external_id'], [
        ['Entrada CSV de contrato de soporte [SIMULADA]', 'low', 'https://soporte.horizonte.example/csv', 'Fila sintética con coma, acentos y salto\nde línea para comprobar importación.', 'No describe una exposición real.', 'Revisar contrato ficticio.', 'BHA-CSV-01'],
        ['Entrada CSV de contrato de soporte [SIMULADA]', 'low', 'https://soporte.horizonte.example/csv', 'Duplicado deliberado de identidad para la vista previa.', 'No describe una exposición real.', 'Revisar contrato ficticio.', 'BHA-CSV-01']])
    burp = '''<?xml version="1.0" encoding="UTF-8"?>
<issues burpVersion="synthetic"><issue><serialNumber>BHA-BURP-01</serialNumber><name>Respuesta de soporte [SIMULADA]</name><host>https://soporte.horizonte.example</host><path>/burp</path><severity>Information</severity><confidence>Tentative</confidence><issueBackground>Archivo ficticio creado para probar un importador.</issueBackground><issueDetail>Sin peticiones realizadas.</issueDetail><remediationBackground>Revisar manualmente antes de publicar.</remediationBackground><references>&lt;a href="https://docs.horizonte.example/import/burp"&gt;Referencia ficticia&lt;/a&gt;</references><requestresponse><request>GET /burp HTTP/1.1
Host: soporte.horizonte.example
X-Synthetic: true</request><response>HTTP/1.1 200 OK
Content-Type: text/plain

SYNTHETIC_ONLY</response></requestresponse></issue></issues>
'''
    nuclei = dict(**{'template-id': 'bha-synthetic-contract', 'matched-at': 'https://soporte.horizonte.example/nuclei', 'type': 'http', 'timestamp': DATE + 'T12:00:00Z', 'matcher-status': True,
                     'info': dict(name='Contrato Nuclei [SIMULADO]', severity='info', description='Coincidencia fabricada para ejercitar importación, no resultado de escáner.', remediation='Revisar el origen ficticio.', reference=['https://docs.horizonte.example/import/nuclei']),
                     'request': 'GET /nuclei HTTP/1.1\nHost: soporte.horizonte.example\nX-Synthetic: true', 'response': 'HTTP/1.1 200 OK\n\nSYNTHETIC_ONLY', 'extracted-results': ['HORIZONTE_SYNTHETIC_NUCLEI']})
    nmap = '''<?xml version="1.0" encoding="UTF-8"?>
<nmaprun scanner="nmap" version="synthetic" start="1792152000"><host><status state="up" reason="user-set"/><address addr="192.0.2.90" addrtype="ipv4"/><hostnames><hostname name="inventario.horizonte.example" type="user"/></hostnames><ports><port protocol="tcp" portid="443"><state state="open" reason="synthetic"/><service name="https" product="Synthetic gateway" version="1.0" method="table" conf="3"/></port><port protocol="tcp" portid="8443"><state state="closed" reason="synthetic"/><service name="https-alt" method="table" conf="3"/></port></ports></host><runstats><finished time="1792152001" elapsed="1.00" exit="success"/><hosts up="1" down="0" total="1"/></runstats></nmaprun>
'''
    sarif = dict(version='2.1.0', runs=[dict(tool=dict(driver=dict(name='Horizonte synthetic scanner', version='1.0', rules=[dict(id='BHA-DRIVER', name='DriverContract', shortDescription=dict(text='Contrato del driver ficticio'))]), extensions=[dict(name='Horizonte synthetic extension', guid='78b5aeec-030c-5e27-a0d0-9b538b337547', rules=[dict(id='BHA-EXT', name='ExtensionContract', shortDescription=dict(text='Contrato de extensión ficticia'), messageStrings={'detail': {'text': 'Resultado sintético para {0}; no hubo escaneo.'}})])]), results=[
        dict(ruleId='BHA-DRIVER', ruleIndex=0, level='note', message=dict(text='Resultado ficticio del driver; no existe escaneo.'), locations=[dict(physicalLocation=dict(artifactLocation=dict(uri='https://codigo.horizonte.example/driver.py'), region=dict(startLine=8, startColumn=1)))], partialFingerprints={'primaryLocationLineHash': 'bha-driver-synthetic'}),
        dict(rule=dict(id='BHA-EXT', index=0, toolComponent=dict(index=0, guid='78b5aeec-030c-5e27-a0d0-9b538b337547')), level='warning', message=dict(id='detail', arguments=['BHA']), locations=[dict(physicalLocation=dict(artifactLocation=dict(uri='https://codigo.horizonte.example/extension.py'), region=dict(startLine=21, startColumn=3)))], partialFingerprints={'primaryLocationLineHash': 'bha-extension-synthetic'})])])
    entries = [('findings.csv', 'csv', csv_input), ('burp.xml', 'burp', burp.encode()), ('nuclei.jsonl', 'nuclei', (json.dumps(nuclei, ensure_ascii=False) + '\n').encode()), ('nmap.xml', 'nmap', nmap.encode()), ('sarif.json', 'sarif', json_bytes(sarif))]
    previews = {}
    for name, kind, blob in entries:
        write(directory / name, blob)
        preview = finding_imports.preview(dict(format=kind, text=blob.decode('utf-8')), dict(meta=dict(lang='es'), findings=[], assets=[], coverage=[]))
        if any(row.get('errors') for row in preview['rows']):
            raise ValueError(f'Invalid synthetic importer fixture: {name}')
        previews[name] = dict(format=kind, counts=preview['counts'], sha256=sha256(blob).hexdigest())
    return previews


def build_case(output: Path, languages=('es', 'en', 'pt')):
    """Build a fresh case directory; refuses to overwrite any existing output."""
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    languages = tuple(languages)
    if not languages or len(set(languages)) != len(languages) or any(lang not in ('es', 'en', 'pt') for lang in languages):
        raise ValueError('Choose unique languages from es, en, pt')
    output.mkdir(parents=True)
    import attachments
    import capture_inbox
    manifests = {}
    for language in languages:
        project = output / 'projects' / language
        (project / 'img').mkdir(parents=True)
        for n, finding in enumerate(FINDINGS, 1):
            evidence_image(project / 'img' / f'evidence-{n:02d}.png', n, finding)
        branding_images(project / 'img')
        write(project / 'originals' / 'evidence-01.png', (project / 'img' / 'evidence-01.png').read_bytes())
        data = make_project(language)
        add_annexes(project, data)
        validate.require_valid(data, final=True)
        if workflows.structure_errors(data):
            raise ValueError(workflows.structure_errors(data))
        capture_inbox.validate_rows(data['capture_inbox'])
        annexes = attachments.inventory(data, project)
        if any(item['status'] not in ('included', 'excluded') for item in annexes):
            raise ValueError('Invalid annex inventory')
        write(project / 'engagement.yaml', yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110))
        loaded = engine.load_engagement(project / 'engagement.yaml')
        if loaded != data:
            raise ValueError('YAML roundtrip altered the source')
        manifests[language] = dict(project=f'projects/{language}', vulnerabilities=24, machines=3, assets=len(data['assets']),
                                   evidence=len(data['evidence']), coverage=len(data['coverage']), sections=len(data['report']['sections']),
                                   root_cause_groups=len(data['root_cause_groups']), retest_records=sum(len(f.get('retests', [])) for f in data['findings']),
                                   severity_counts=engine.severity_counts(data['findings']), source_bytes=(project / 'engagement.yaml').stat().st_size,
                                   annexes=[dict(name=a['name'], status=a['status'], bytes=a['bytes']) for a in annexes],
                                   validation_errors=0, warnings=validate.validate(data))
    imports = write_import_inputs(output / 'inputs')
    files = {path.relative_to(output).as_posix(): dict(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()).hexdigest())
             for path in sorted(output.rglob('*')) if path.is_file()}
    manifest = dict(schema='report-gen-horizonte-source/1', case=CASE, date=DATE, fictional=True,
                    source_generator='scripts/build-horizonte-case.py', prose_language='es',
                    variants_note='EN/PT localize report labels and navigation. Authored prose remains Spanish.',
                    network_to_scenario_targets=False, reports_generated_by_builder=False, projects=manifests,
                    import_previews=imports, files=files)
    write(output / 'manifest.json', json_bytes(manifest))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New output directory; existing paths are refused.')
    parser.add_argument('--languages', nargs='+', choices=('es', 'en', 'pt'), default=['es', 'en', 'pt'])
    options = parser.parse_args()
    result = build_case(options.output, options.languages)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, ensure_ascii=False, indent=2))
