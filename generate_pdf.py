#!/usr/bin/env python3
"""
generate_pdf.py — Reporte Técnico: Clasificador de Frutas con IA V4

Uso:    python3.14 generate_pdf.py
Salida: Reporte_Tecnico_FruitSorter_V4.pdf
Deps:   pip install reportlab pygments
"""

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ── Dependencias ────────────────────────────────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import (
        BaseDocTemplate, Frame, PageTemplate,
        Paragraph, Spacer, Table, TableStyle,
        Image, PageBreak, HRFlowable, KeepTogether, NextPageTemplate,
    )
except ImportError as e:
    sys.exit(f"Instala: python3.14 -m pip install reportlab\n{e}")

HAS_PYGMENTS = False
try:
    from pygments.lexers import get_lexer_by_name
    from pygments.token import Token
    HAS_PYGMENTS = True
except ImportError:
    print("Advertencia: pygments no disponible — código sin colores.")

# ── Dimensiones y colores ────────────────────────────────────────────────
PW, PH = A4
M   = 2 * cm
CW  = PW - 2 * M

PRIMARY   = HexColor('#1B5E20')
SECONDARY = HexColor('#2E7D32')
ACCENT    = HexColor('#43A047')
LIGHT     = HexColor('#E8F5E9')
LIGHT2    = HexColor('#F1F8E9')
CODE_BG   = HexColor('#1E1E1E')
CODE_FG   = HexColor('#D4D4D4')
TBL_HDR   = HexColor('#2E7D32')
TBL_R1    = HexColor('#F1F8E9')
GRAY      = HexColor('#757575')
DARK      = HexColor('#212121')
BLUE_BG   = HexColor('#E3F2FD')
BLUE_FG   = HexColor('#0D47A1')
WARN_BG   = HexColor('#FFF8E1')
WARN_FG   = HexColor('#E65100')


# ═══════════════════════════════════════════════════════════════════════
#  SYNTAX HIGHLIGHTING
# ═══════════════════════════════════════════════════════════════════════

def _tok_color(ttype):
    """Token → VS Code Dark+ hex. Traverses token hierarchy."""
    if not HAS_PYGMENTS:
        return '#D4D4D4'
    rules = [
        (Token.Comment,         '#6A9955'),
        (Token.Literal.String,  '#CE9178'),
        (Token.Literal.Number,  '#B5CEA8'),
        (Token.Keyword.Import,  '#C586C0'),
        (Token.Keyword,         '#569CD6'),
        (Token.Name.Decorator,  '#DCDCAA'),
        (Token.Name.Function,   '#DCDCAA'),
        (Token.Name.Class,      '#4EC9B0'),
        (Token.Name.Builtin,    '#4EC9B0'),
    ]
    for base, color in rules:
        cur = ttype
        while cur is not Token and cur is not None:
            if cur is base:
                return color
            cur = cur.parent
    return '#D4D4D4'


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _colorize_line(line, lang='python'):
    """Return a reportlab XML fragment for one highlighted line."""
    if not HAS_PYGMENTS:
        return f'<font color="#D4D4D4">{_esc(line) or " "}</font>'
    try:
        parts = []
        for ttype, val in get_lexer_by_name(lang).get_tokens(line + '\n'):
            if val == '\n':
                continue
            parts.append(f'<font color="{_tok_color(ttype)}">{_esc(val)}</font>')
        return ''.join(parts) or '&nbsp;'
    except Exception:
        return f'<font color="#D4D4D4">{_esc(line) or " "}</font>'


# ═══════════════════════════════════════════════════════════════════════
#  ESTILOS
# ═══════════════════════════════════════════════════════════════════════

def build_styles():
    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        'Normal': ps('Normal', fontName='Helvetica', fontSize=10, leading=15,
                     textColor=DARK, spaceAfter=6, alignment=TA_JUSTIFY),
        'Lead':   ps('Lead',   fontName='Helvetica', fontSize=11, leading=17,
                     textColor=DARK, spaceAfter=10, alignment=TA_JUSTIFY),
        'H1': ps('H1', fontName='Helvetica-Bold', fontSize=15, leading=21,
                 textColor=white, backColor=PRIMARY, spaceBefore=20, spaceAfter=12,
                 leftPadding=10, rightPadding=10, topPadding=7, bottomPadding=7),
        'H2': ps('H2', fontName='Helvetica-Bold', fontSize=13, leading=18,
                 textColor=PRIMARY, spaceBefore=16, spaceAfter=8),
        'H3': ps('H3', fontName='Helvetica-Bold', fontSize=11, leading=15,
                 textColor=SECONDARY, spaceBefore=12, spaceAfter=6),
        'Bullet': ps('Bullet', fontName='Helvetica', fontSize=10, leading=14,
                     textColor=DARK, spaceAfter=3, leftIndent=16, firstLineIndent=-10),
        'Caption': ps('Caption', fontName='Helvetica-Oblique', fontSize=9,
                      textColor=GRAY, alignment=TA_CENTER, spaceAfter=10, spaceBefore=4),
        'Callout': ps('Callout', fontName='Helvetica', fontSize=9.5, leading=14,
                      textColor=BLUE_FG, backColor=BLUE_BG,
                      leftPadding=10, rightPadding=10, topPadding=6, bottomPadding=6,
                      spaceAfter=10, spaceBefore=6),
        'Warn': ps('Warn', fontName='Helvetica', fontSize=9.5, leading=14,
                   textColor=WARN_FG, backColor=WARN_BG,
                   leftPadding=10, rightPadding=10, topPadding=6, bottomPadding=6,
                   spaceAfter=10, spaceBefore=6),
        'TblHdr':  ps('TblHdr',  fontName='Helvetica-Bold', fontSize=9, leading=12,
                      textColor=white, alignment=TA_CENTER),
        'TblCell': ps('TblCell', fontName='Helvetica', fontSize=9, leading=12,
                      textColor=DARK),
        'TblMono': ps('TblMono', fontName='Courier', fontSize=8.5, leading=11,
                      textColor=DARK),
        'CodeTitle': ps('CodeTitle', fontName='Helvetica-Bold', fontSize=9,
                        textColor=white, backColor=HexColor('#2D2D2D'),
                        leftPadding=8, rightPadding=8, topPadding=4, bottomPadding=4),
        'GlossTerm': ps('GlossTerm', fontName='Helvetica-Bold', fontSize=10,
                        textColor=PRIMARY, spaceBefore=10),
        'GlossDef':  ps('GlossDef',  fontName='Helvetica', fontSize=9.5, leading=14,
                        textColor=DARK, leftIndent=14, spaceAfter=4),
        'TOC1': ps('TOC1', fontName='Helvetica-Bold', fontSize=11, leading=16,
                   textColor=DARK, spaceBefore=4),
        'TOC2': ps('TOC2', fontName='Helvetica', fontSize=10, leading=14,
                   textColor=GRAY, leftIndent=20, spaceAfter=2),
    }


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS DE FLOWABLES
# ═══════════════════════════════════════════════════════════════════════

def sp(n=1):     return Spacer(1, n * 6)
def pb():        return PageBreak()
def hr():        return HRFlowable(width='100%', thickness=0.5, color=ACCENT,
                                    spaceBefore=4, spaceAfter=4)

def h1(t, S):    return Paragraph(t, S['H1'])
def h2(t, S):    return Paragraph(t, S['H2'])
def h3(t, S):    return Paragraph(t, S['H3'])
def p(t, S):     return Paragraph(t, S['Normal'])
def lead(t, S):  return Paragraph(t, S['Lead'])
def callout(t, S): return Paragraph(t, S['Callout'])
def warn(t, S):    return Paragraph(t, S['Warn'])
def caption(t, S): return Paragraph(t, S['Caption'])

def bullet(t, S, icon='●'):
    return Paragraph(f'{icon}&nbsp;&nbsp;{t}', S['Bullet'])


def code_block(code_str, lang='python', title=None, S=None, max_lines=None):
    """Code block con fondo oscuro y syntax highlighting."""
    lines = code_str.split('\n')
    while lines and not lines[-1].strip():
        lines.pop()
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines] + ['    # ...']

    result = []
    if title:
        result.append(Paragraph(f'&nbsp;{title}', S['CodeTitle']))

    lnum_st = ParagraphStyle('_LN', fontName='Courier', fontSize=7.5, leading=12,
                              textColor=HexColor('#555555'), leftPadding=4, rightPadding=4)
    code_st = ParagraphStyle('_CL', fontName='Courier', fontSize=8.5, leading=12,
                              textColor=CODE_FG, leftPadding=6, rightPadding=4)
    rows = []
    for i, line in enumerate(lines):
        ln = Paragraph(f'<font color="#555555">{i+1:3d}</font>', lnum_st)
        cp = Paragraph(_colorize_line(line, lang), code_st)
        rows.append([ln, cp])

    if not rows:
        return result

    t = Table(rows, colWidths=[0.75*cm, CW - 0.75*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), CODE_BG),
        ('TOPPADDING',    (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('BOX',           (0, 0), (-1, -1), 0.5, HexColor('#444444')),
        ('LINEAFTER',     (0, 0), (0, -1),  0.5, HexColor('#333333')),
    ]))
    result.append(t)
    result.append(sp(2))
    return result


def data_table(headers, rows, widths=None, S=None, mono_cols=None):
    """Tabla con cabecera verde y filas alternadas."""
    mono_cols = mono_cols or []
    hrow  = [Paragraph(h, S['TblHdr']) for h in headers]
    data  = [hrow]
    for r in rows:
        data.append([
            Paragraph(str(c), S['TblMono'] if j in mono_cols else S['TblCell'])
            for j, c in enumerate(r)
        ])
    if widths is None:
        widths = [CW / len(headers)] * len(headers)

    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  TBL_HDR),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0),  9),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 7),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 7),
        ('ALIGN',         (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [TBL_R1, white]),
        ('GRID',          (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),
        ('LINEBELOW',     (0, 0), (-1, 0),  1.5, ACCENT),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════
#  PLANTILLA DEL DOCUMENTO
# ═══════════════════════════════════════════════════════════════════════

def _body_page(cv, doc):
    """Header y footer para páginas de contenido."""
    cv.saveState()
    # Header
    cv.setFillColor(PRIMARY)
    cv.rect(0, PH - 1.2*cm, PW, 1.2*cm, fill=1, stroke=0)
    cv.setFillColor(white)
    cv.setFont('Helvetica-Bold', 9)
    cv.drawString(M, PH - 0.77*cm, 'Clasificador de Frutas con IA — V4')
    cv.setFont('Helvetica', 9)
    cv.drawRightString(PW - M, PH - 0.77*cm, 'Reporte Técnico')
    # Footer
    cv.setFillColor(LIGHT)
    cv.rect(0, 0, PW, 1.1*cm, fill=1, stroke=0)
    cv.setStrokeColor(ACCENT)
    cv.setLineWidth(1.5)
    cv.line(M, 1.15*cm, PW - M, 1.15*cm)
    cv.setFillColor(GRAY)
    cv.setFont('Helvetica', 8)
    cv.drawCentredString(PW/2, 0.42*cm, f'Página {doc.page}')
    cv.restoreState()


def _cover_page(cv, doc):
    """Portada dibujada directamente sobre el canvas."""
    cv.saveState()

    # — Bloque superior verde —
    top_h = PH * 0.52
    cv.setFillColor(PRIMARY)
    cv.rect(0, PH - top_h, PW, top_h, fill=1, stroke=0)

    # Franja decorativa
    cv.setFillColor(SECONDARY)
    cv.rect(0, PH - top_h - 0.6*cm, PW, 0.6*cm, fill=1, stroke=0)
    cv.setFillColor(ACCENT)
    cv.rect(0, PH - top_h - 0.9*cm, PW, 0.3*cm, fill=1, stroke=0)

    # Título
    cv.setFillColor(white)
    cv.setFont('Helvetica-Bold', 26)
    ty = PH - top_h * 0.38
    cv.drawCentredString(PW / 2, ty,                  'Clasificador Automático')
    cv.drawCentredString(PW / 2, ty - 1.0*cm,         'de Frutas con IA')

    # Subtítulo
    cv.setFont('Helvetica', 13)
    cv.setFillColor(LIGHT)
    cv.drawCentredString(PW / 2, ty - 2.1*cm, 'Reporte Técnico — Arquitectura V4 (Agéntico)')

    # Badges
    cv.setFont('Helvetica', 9)
    tags = ['Python 3.10+', 'Arduino UNO R3', 'LMStudio', 'VL53L0X Láser', 'Tool-Calling']
    badge_w, badge_h = 3.0*cm, 0.65*cm
    gap = 0.3*cm
    total = len(tags) * badge_w + (len(tags) - 1) * gap
    bx = (PW - total) / 2
    by = ty - 3.1*cm
    for tag in tags:
        cv.setFillColor(SECONDARY)
        cv.roundRect(bx, by, badge_w, badge_h, 4, fill=1, stroke=0)
        cv.setFillColor(white)
        cv.drawCentredString(bx + badge_w / 2, by + badge_h * 0.28, tag)
        bx += badge_w + gap

    # — Bloque inferior blanco —
    bottom_top = PH - top_h - 0.9*cm

    # Foto de la maqueta
    maqueta = getattr(doc, '_maqueta', None)
    if maqueta and os.path.exists(maqueta):
        try:
            ir = ImageReader(maqueta)
            iw, ih = ir.getSize()
            max_w, max_h = 9*cm, 5.5*cm
            scale = min(max_w / iw, max_h / ih)
            dw, dh = iw * scale, ih * scale
            img_y = bottom_top - 1.0*cm - dh
            cv.drawImage(ir, (PW - dw) / 2, img_y, dw, dh,
                         preserveAspectRatio=True, mask='auto')
            auth_y = img_y - 1.3*cm
        except Exception:
            auth_y = bottom_top - 1.5*cm
    else:
        auth_y = bottom_top - 1.5*cm

    # Autores
    cv.setFillColor(PRIMARY)
    cv.setFont('Helvetica-Bold', 11)
    cv.drawCentredString(PW / 2, auth_y, 'Desarrolladores')
    authors = [
        'Jesús Andrés Mondragón Tenorio',
        'Cristofer Piña Rodriguez',
        'Mauricio Sanchez Garcia',
    ]
    cv.setFont('Helvetica', 10)
    cv.setFillColor(DARK)
    for i, a in enumerate(authors):
        cv.drawCentredString(PW / 2, auth_y - (i + 1) * 0.58*cm, a)

    # Pie de portada
    cv.setFillColor(PRIMARY)
    cv.rect(0, 0, PW, 1.0*cm, fill=1, stroke=0)
    cv.setFillColor(white)
    cv.setFont('Helvetica', 8.5)
    cv.drawCentredString(PW / 2, 0.38*cm, 'Mayo 2026')

    cv.restoreState()


class FruitDoc(BaseDocTemplate):
    def __init__(self, filename, maqueta_path=None, **kw):
        super().__init__(filename, pagesize=A4, **kw)
        self._maqueta = maqueta_path
        self.section_pages = []

        cover_frame = Frame(0, 0, PW, PH, id='cover')
        body_frame  = Frame(M, 1.4*cm, CW, PH - 1.4*cm - 2.5*cm, id='body')

        self.addPageTemplates([
            PageTemplate(id='Cover', frames=[cover_frame], onPage=_cover_page),
            PageTemplate(id='Body',  frames=[body_frame],  onPage=_body_page),
        ])

    def afterFlowable(self, flowable):
        """Registra números de página de cada sección H1/H2."""
        if isinstance(flowable, Paragraph):
            sn = flowable.style.name
            if sn in ('H1', 'H2'):
                level = 0 if sn == 'H1' else 1
                self.section_pages.append((level, flowable.getPlainText(), self.page))


# ═══════════════════════════════════════════════════════════════════════
#  SECCIONES DEL DOCUMENTO
# ═══════════════════════════════════════════════════════════════════════

def build_toc(section_pages, S, page_offset=2):
    """Genera una página de índice estática con números de página reales."""
    pg_right = ParagraphStyle('_PgR', fontName='Helvetica-Bold', fontSize=11,
                               textColor=DARK, alignment=TA_RIGHT)
    pg_right2 = ParagraphStyle('_PgR2', fontName='Helvetica', fontSize=10,
                                textColor=GRAY, alignment=TA_RIGHT)
    dot_st   = ParagraphStyle('_Dot', fontName='Helvetica', fontSize=11,
                               textColor=HexColor('#CCCCCC'))

    rows = []
    for level, text, raw_page in section_pages:
        page_num = raw_page + page_offset
        if level == 0:
            rows.append(Table(
                [[Paragraph(text, S['TOC1']),
                  Paragraph(str(page_num), pg_right)]],
                colWidths=[CW - 1.8*cm, 1.8*cm],
            ))
        else:
            rows.append(Table(
                [[Paragraph(f'&nbsp;&nbsp;&nbsp;&nbsp;{text}', S['TOC2']),
                  Paragraph(str(page_num), pg_right2)]],
                colWidths=[CW - 1.8*cm, 1.8*cm],
            ))

    story = [h1('Tabla de Contenido', S), sp(2)]
    for r in rows:
        r.setStyle(TableStyle([
            ('LINEBELOW',     (0,0), (-1,0), 0.3, HexColor('#DDDDDD')),
            ('TOPPADDING',    (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(r)

    story.append(pb())
    return story


def build_intro(S):
    story = [h1('1. Descripción del Sistema', S)]
    story.append(lead(
        'El <b>Clasificador Automático de Frutas con IA</b> es un sistema embebido autónomo '
        'que combina visión por computadora, inteligencia artificial local y control de hardware '
        'para clasificar frutas en una rampa física. El sistema no requiere conexión a internet '
        'ni servicios en la nube — todo el procesamiento ocurre localmente.',
        S))

    story.append(h2('1.1 ¿Cómo funciona en términos generales?', S))
    story.append(p(
        'Una fruta se coloca sobre una rampa. El sensor láser <b>VL53L0X</b> detecta su presencia '
        'midiendo la distancia. Python captura una foto con la webcam, la codifica en Base64 y la '
        'envía al modelo de lenguaje <b>Qwen3-VL-4B</b> ejecutándose en LMStudio. El modelo identifica '
        'la fruta y <i>llama</i> la herramienta correcta (tool-calling), que envía un comando serial '
        'al Arduino para activar el servo correspondiente.',
        S))

    story.append(h2('1.2 Características Principales', S))
    features = [
        ('<b>100% local</b> — Sin dependencias de cloud. LMStudio corre en la misma PC.',
         'Sensor láser de precisión'),
        ('<b>Agente autónomo</b> — El LLM decide qué tool llamar; Python solo ejecuta.',
         'Tool-calling nativo OpenAI'),
        ('<b>HTTP estándar</b> — Usa <font name="Courier">requests</font> con la API OpenAI compatible.',
         'Compatible con cualquier servidor LLM'),
        ('<b>Sensor láser VL53L0X</b> — Mayor precisión que ultrasónico. I2C, 3–13 cm.',
         'Alta precisión'),
        ('<b>Escalable por prompt</b> — Añadir una fruta nueva solo requiere editar el system prompt.',
         'Sin recompilación'),
        ('<b>Arquitectura modular</b> — Cada módulo es independiente y reemplazable.',
         'Mantenibilidad'),
    ]
    for feat, _ in features:
        story.append(bullet(feat, S))
    story.append(sp(2))

    story.append(h2('1.3 Evolución: V3 → V4', S))
    story.append(data_table(
        ['Aspecto', 'V3', 'V4 (este proyecto)'],
        [
            ['Sensor de detección',     'HC-SR04 (ultrasónico, pines 6/7)',   'VL53L0X (láser I2C, A4/A5)'],
            ['Comunicación con LLM',    'LMStudio SDK (WebSocket)',             'requests HTTP (estándar OpenAI)'],
            ['API Key',                 'No requerida',                         'Bearer token explícito'],
            ['Tool-calling',            'Manejado por el SDK',                  'Loop agéntico manual'],
            ['Firmware Arduino',        'Lógica de doble servo (push)',         'Movimiento simple por servo'],
            ['Compatibilidad LLM',      'Solo LMStudio SDK',                    'Cualquier API OpenAI-compatible'],
        ],
        widths=[CW*0.28, CW*0.31, CW*0.41],
        S=S,
    ))
    story.append(pb())
    return story


def build_hardware(S, circuit_img_path=None):
    story = [h1('2. Hardware', S)]
    story.append(lead(
        'El sistema utiliza componentes de bajo costo y fácil adquisición. El elemento clave '
        'es el sensor <b>VL53L0X</b>, que usa tecnología de tiempo de vuelo (ToF) láser para '
        'detectar la presencia de frutas con mayor precisión y menor ruido que los sensores ultrasónicos.',
        S))

    story.append(h2('2.1 Lista de Componentes', S))
    story.append(data_table(
        ['Componente', 'Modelo', 'Función'],
        [
            ['Microcontrolador', 'Arduino UNO R3',         'Controla servos y lee el sensor láser'],
            ['Cámara',           'Webcam USB',              'Captura imágenes para el agente de IA'],
            ['Sensor distancia', 'VL53L0X (Adafruit)',     'Detección de fruta por láser ToF'],
            ['Servomotores ×2',  'MG995 (alto torque)',    'Accionan las compuertas de clasificación'],
            ['Estructura',       'Triplay / MDF',           'Rampa con compuertas y contenedores'],
        ],
        widths=[CW*0.28, CW*0.28, CW*0.44],
        S=S,
    ))
    story.append(sp(2))

    story.append(h2('2.2 Sensor Láser VL53L0X', S))
    story.append(p(
        'El <b>VL53L0X</b> es un sensor de distancia de <b>Tiempo de Vuelo (ToF)</b>. Emite '
        'pulsos de láser infrarrojo (940 nm) y mide el tiempo que tarda en regresar el reflejo, '
        'calculando la distancia con precisión milimétrica. A diferencia del HC-SR04 (ultrasónico), '
        'no necesita pines de Trig/Echo — se comunica por <b>I2C</b> con solo dos cables (SDA/SCL), '
        'es insensible al ángulo de la superficie y funciona bien con objetos blandos como frutas.',
        S))
    story.append(data_table(
        ['Parámetro', 'Valor'],
        [
            ['Protocolo de comunicación', 'I2C (dirección 0x29)'],
            ['Rango físico del sensor',   '30 mm – 2000 mm'],
            ['Rango configurado (firmware)', '30 mm – 130 mm (3–13 cm)'],
            ['Modo de medición',          'VL53L0X_SENSE_HIGH_ACCURACY'],
            ['Valor fuera de rango',      '999.0 (ausencia de objeto o error)'],
            ['Librería Arduino',          'Adafruit_VL53L0X'],
            ['Umbral de detección (Python)', '13.0 cm (configurable con --threshold)'],
        ],
        widths=[CW*0.5, CW*0.5],
        S=S,
    ))
    story.append(sp(2))

    story.append(h2('2.3 Conexiones de Pines', S))
    story.append(data_table(
        ['Pin Arduino', 'Componente', 'Función'],
        [
            ['A4 (SDA)', 'VL53L0X → SDA',    'Datos I2C (protocolo bidireccional)'],
            ['A5 (SCL)', 'VL53L0X → SCL',    'Reloj I2C'],
            ['3.3V',     'VL53L0X → VCC',    'Alimentación del sensor (regulador onboard)'],
            ['9',        'Servo MG995 #1',    'Compuerta IZQUIERDA (manzanas)'],
            ['10',       'Servo MG995 #2',    'Compuerta DERECHA (naranjas)'],
            ['5V',       'Servos → VCC',      'Alimentación de los servomotores'],
            ['GND',      'VL53L0X / Servos',  'Tierra común del sistema'],
        ],
        widths=[CW*0.18, CW*0.28, CW*0.54],
        S=S, mono_cols=[0],
    ))

    if circuit_img_path and os.path.exists(circuit_img_path):
        story.append(sp(2))
        story.append(h2('2.4 Diagrama del Circuito', S))
        img = Image(circuit_img_path, width=CW, height=8*cm, kind='proportional')
        story.append(img)
        story.append(caption('Figura 1 — Diagrama de conexiones del circuito', S))

    story.append(pb())
    return story


def build_architecture(S):
    story = [h1('3. Arquitectura del Sistema', S)]
    story.append(lead(
        'El sistema sigue una arquitectura de <b>agente autónomo</b>: Python orquesta el hardware '
        'pero <i>no toma decisiones de clasificación</i> — esas las toma el LLM mediante tool-calling.',
        S))

    story.append(h2('3.1 Diagrama de Componentes', S))

    # Diagrama visual como tabla de colores
    def cbox(text, bg=LIGHT2, fg=DARK, bold=False):
        fname = 'Helvetica-Bold' if bold else 'Helvetica'
        return Paragraph(text, ParagraphStyle(
            '_box', fontName=fname, fontSize=9, leading=13, textColor=fg,
            backColor=bg, alignment=TA_CENTER,
            leftPadding=6, rightPadding=6, topPadding=5, bottomPadding=5,
        ))

    arch_rows = [
        [
            cbox('service.py\nOrquestador', PRIMARY, white, bold=True),
            cbox('→ Detecta fruta\n→ Captura foto\n→ Llama al agente', LIGHT2, DARK),
            cbox('LMStudio :1234\nQwen3-VL-4B', SECONDARY, white, bold=True),
        ],
        [
            cbox('arduino.py\nSerial 115200 baud', HexColor('#1565C0'), white, bold=True),
            cbox('→ Envía comandos:\nAPPLE / ORANGE\n→ Lee distancia VL53L0X', LIGHT2, DARK),
            cbox('llm.py\nHTTP POST\n/v1/chat/completions', SECONDARY, white, bold=True),
        ],
        [
            cbox('camera.py\nWebcam USB', HexColor('#6A1B9A'), white, bold=True),
            cbox('→ Frame → JPEG\n→ Base64\n→ Envía al LLM', LIGHT2, DARK),
            cbox('tools.py\nsort_to_left()\nsort_to_right()', HexColor('#BF360C'), white, bold=True),
        ],
        [
            cbox('Hardware\nArduino UNO R3', HexColor('#E65100'), white, bold=True),
            cbox('VL53L0X (I2C)\nServos MG995 ×2\nProtocolo serial 115200', LIGHT2, DARK),
            cbox('mcp_service.py\n(Opcional)\nFastMCP SSE :8000', GRAY, white),
        ],
    ]

    arch_t = Table(arch_rows, colWidths=[CW*0.28, CW*0.44, CW*0.28])
    arch_t.setStyle(TableStyle([
        ('TOPPADDING',    (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING',   (0,0), (-1,-1), 4),
        ('RIGHTPADDING',  (0,0), (-1,-1), 4),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('GRID',          (0,0), (-1,-1), 1, white),
        ('BACKGROUND',    (0,0), (-1,-1), white),
    ]))
    story.append(arch_t)
    story.append(caption('Figura 2 — Relación entre módulos del sistema', S))
    story.append(sp(2))

    story.append(h2('3.2 Flujo de un Ciclo Completo', S))
    story.append(data_table(
        ['Paso', 'Módulo', 'Acción', 'Resultado'],
        [
            ['1', 'arduino.py',  'Polling GET_DISTANCE cada 0.3s',          'Espera distancia < 13 cm'],
            ['2', 'arduino.py',  'Detecta objeto en rango 3–13 cm',          'Retorna distancia en cm'],
            ['3', 'camera.py',   'Captura frame de webcam',                   'JPEG 384px → Base64'],
            ['4', 'llm.py',      'POST /v1/chat/completions + imagen + tools','LLM procesa la imagen'],
            ['5', 'llm.py',      'LLM devuelve tool_calls JSON',             'sort_to_left / sort_to_right'],
            ['6', 'tools.py',    'Ejecuta la función Python de la tool',      'Llama arduino.classify_*()'],
            ['7', 'arduino.py',  'Envía APPLE\\n o ORANGE\\n por serial',     'Arduino activa servo'],
            ['8', 'Arduino',     'Servo: 90° → 135°/45° → 90° (2.5s)',       'Fruta desviada al contenedor'],
            ['9', 'service.py',  'Imprime resultado y reinicia ciclo',        'SUCCESS:FruitName:SIDE'],
        ],
        widths=[CW*0.07, CW*0.18, CW*0.43, CW*0.32],
        S=S,
    ))
    story.append(pb())
    return story


def build_software(S):
    story = [h1('4. Módulos de Software', S)]
    story.append(lead(
        'El sistema está dividido en 6 módulos Python, cada uno con responsabilidad única. '
        'Solo <font name="Courier">service.py</font> se ejecuta directamente — los demás son '
        'importados como librerías internas.',
        S))

    # service.py
    story.append(h2('4.1 service.py — Punto de Entrada', S))
    story.append(p(
        'Es el <b>orquestador principal</b>. Contiene el loop de clasificación, maneja la '
        'señal SIGINT para cierre limpio y muestra el resultado en consola con colores ANSI. '
        '<b>No toma decisiones de clasificación</b> — delega todo al agente LLM.',
        S))
    story += code_block(
        '''def sorting_loop(threshold_cm: float = 13.0) -> None:
    while _running:
        result = arduino.wait_for_fruit(threshold_cm=threshold_cm, timeout_seconds=30)
        if not result["success"]:
            log("⏳ Tiempo agotado sin detección.", YELLOW)
            continue
        img_b64 = camera.get_camera_data()
        agent_status = llm.act_on_fruit(img_b64, on_message=_on_agent_message)
        print_result_box(agent_status)
        time.sleep(1.0)''',
        title='service.py — sorting_loop()', S=S,
    )

    # llm.py
    story.append(h2('4.2 llm.py — Agente de IA', S))
    story.append(p(
        'Implementa el <b>loop agéntico</b>: envía la imagen al LLM, recibe tool_calls, '
        'ejecuta las tools y repite hasta que la fruta queda clasificada. Máximo 5 iteraciones. '
        'Si el LLM pide <font name="Courier">get_camera_image()</font>, Python <i>reemplaza</i> '
        'la imagen en el historial (no la añade) para ahorrar tokens de contexto.',
        S))
    story += code_block(
        '''def act_on_fruit(image_b64: str, on_message=None) -> str:
    headers = {"Authorization": f"Bearer {LMSTUDIO_API_KEY}"}
    messages = [
        {"role": "system",  "content": SYSTEM_PROMPT},
        {"role": "user",    "content": [
            {"type": "text",      "text": "Sort this fruit."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
        ]}
    ]
    for _ in range(5):
        payload = {"model": LMSTUDIO_MODEL, "messages": messages,
                   "tools": tools.TOOLS_SCHEMA, "tool_choice": "auto"}
        response = requests.post(API_URL, headers=headers, json=payload)
        msg = response.json()["choices"][0]["message"]
        messages.append(msg)
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            return msg.get("content", "Process finished.")
        for tc in tool_calls:
            func_name = tc["function"]["name"]
            args      = json.loads(tc["function"].get("arguments", "{}"))
            result    = tools.AVAILABLE_FUNCTIONS[func_name](**args)
            messages.append({"role": "tool", "content": result,
                             "tool_call_id": tc["id"]})
            if result.startswith("SUCCESS") or result.startswith("DISCARD"):
                return result
    return "ERROR:Max turns reached"''',
        title='llm.py — act_on_fruit() — Loop agéntico completo', S=S,
    )

    # tools.py
    story.append(h2('4.3 tools.py — Herramientas del Agente', S))
    story.append(p(
        'Define las tools disponibles para el LLM en dos partes: la <b>implementación Python</b> '
        '(lo que se ejecuta) y el <b>schema JSON</b> (lo que se le describe al modelo para que '
        'sepa cuándo y cómo llamarla). El argumento <font name="Courier">fruit_name</font> '
        'permite al LLM reportar explícitamente qué fruta identificó.',
        S))
    story.append(data_table(
        ['Tool', 'Argumento', 'Acción en Hardware', 'Devuelve'],
        [
            ['sort_to_left()',    'fruit_name (str)', 'arduino.classify_as_apple() → APPLE\\n',  'SUCCESS:Nombre:LEFT'],
            ['sort_to_right()',   'fruit_name (str)', 'arduino.classify_as_orange() → ORANGE\\n', 'SUCCESS:Nombre:RIGHT'],
            ['discard_fruit()',   '—',                'Sin acción',                               'DISCARD:Unknown Item'],
            ['get_camera_image()','—',                'Captura nueva foto (retry)',               'NEW_IMAGE_READY'],
        ],
        widths=[CW*0.22, CW*0.20, CW*0.31, CW*0.27],
        S=S,
    ))
    story.append(sp(2))

    # arduino.py
    story.append(h2('4.4 arduino.py — Comunicación Serial', S))
    story.append(p(
        'Gestiona la conexión serial con el Arduino. La conexión es <b>persistente</b> '
        '(se abre una vez y se reutiliza), <b>thread-safe</b> (con '
        '<font name="Courier">threading.Lock</font>) y <b>auto-reconectable</b> '
        '(si el puerto falla, el siguiente comando intenta reconectar). '
        'Incluye auto-detección del puerto en Linux y Windows.',
        S))
    story += code_block(
        '''def wait_for_fruit(threshold_cm=13.0, timeout_seconds=30) -> dict:
    """Poll VL53L0X each 0.3s until object < threshold_cm or timeout."""
    start = time.time()
    while time.time() - start < timeout_seconds:
        distance = get_distance()   # Sends GET_DISTANCE\\n → returns float
        if distance < threshold_cm:
            return {"detected": True, "distance_cm": distance,
                    "message": "Fruit detected. Ready to classify."}
        time.sleep(SENSOR_POLL_INTERVAL)   # 0.3s
    return {"detected": False, "distance_cm": 999.0,
            "message": "Timeout: no fruit detected."}''',
        title='arduino.py — wait_for_fruit()', S=S,
    )

    # camera.py
    story.append(h2('4.5 camera.py — Captura de Imágenes', S))
    story.append(p(
        'Mantiene la webcam abierta de forma persistente. Incluye un warmup de 2 frames '
        'para evitar capturas oscuras o inestables al inicio. Las imágenes se '
        '<b>redimensionan a ≤384px</b> antes de enviarlas al LLM para reducir tokens y '
        'acelerar la inferencia.',
        S))

    # mcp_service.py
    story.append(h2('4.6 mcp_service.py — Servidor MCP (Opcional)', S))
    story.append(callout(
        '⚙  Este módulo es OPCIONAL. service.py NO lo requiere para funcionar. '
        'Solo es necesario si quieres conectar un cliente MCP externo (Claude Desktop, '
        'LMStudio con MCP, etc.) para controlar la máquina desde otro agente.',
        S))
    story.append(p(
        'Usa <b>FastMCP</b> para exponer las mismas funciones de hardware como herramientas '
        'MCP con transporte <b>SSE (Server-Sent Events)</b> en el puerto 8000. '
        'Ejecutar este módulo y <font name="Courier">service.py</font> al mismo tiempo '
        'causará conflicto en el puerto serial.',
        S))
    story.append(pb())
    return story


def build_requests_section(S):
    story = [h1('5. Comunicación HTTP con requests', S)]
    story.append(lead(
        'La librería <b>requests</b> reemplaza al SDK propietario de LMStudio V3. Cada consulta '
        'al LLM es un HTTP POST estándar — el mismo formato que usa la API oficial de OpenAI. '
        'Esto hace el sistema compatible con <b>cualquier servidor LLM local o remoto</b>.',
        S))

    story.append(h2('5.1 ¿Qué hace exactamente?', S))
    story += code_block(
        '''# Cada iteración del loop agéntico envía exactamente esto:
response = requests.post(
    url     = "http://127.0.0.1:1234/v1/chat/completions",
    headers = {
        "Content-Type":  "application/json",
        "Authorization": "Bearer lm-studio"     # ← API Key
    },
    json = {
        "model":       "qwen/qwen3-vl-4b",
        "messages":    [                         # ← Historial completo
            {"role": "system",  "content": SYSTEM_PROMPT},
            {"role": "user",    "content": [imagen_base64]},
            # ...resultados de tools anteriores...
        ],
        "tools":       TOOLS_SCHEMA,             # ← Definición JSON de tools
        "tool_choice": "auto"                    # ← LLM decide si usar tools
    }
)
# La respuesta tiene el mismo formato que la API de OpenAI:
msg = response.json()["choices"][0]["message"]
tool_calls = msg.get("tool_calls")               # ← Qué tools quiere llamar''',
        title='llm.py — Anatomía de la petición HTTP', S=S,
    )

    story.append(h2('5.2 ¿Por qué requests en lugar del SDK?', S))
    story.append(data_table(
        ['Aspecto', 'SDK LMStudio (V3)', 'requests HTTP (V4)'],
        [
            ['Protocolo',      'WebSocket propietario',          'HTTP estándar REST'],
            ['API Key',        'No requerida',                   'Bearer token explícito'],
            ['Compatibilidad', 'Solo LMStudio SDK',              'Cualquier API OpenAI-compatible'],
            ['Transparencia',  'Oculta el protocolo',            'Se ve exactamente qué se envía'],
            ['Debuggear',      'Difícil (WebSocket binario)',     'Fácil (JSON legible en logs)'],
            ['Dependencias',   'lmstudio Python SDK',            'Solo requests (stdlib casi)'],
        ],
        widths=[CW*0.22, CW*0.35, CW*0.43],
        S=S,
    ))
    story.append(pb())
    return story


def build_tool_calling(S):
    story = [h1('6. Loop Agéntico y Tool-Calling', S)]
    story.append(lead(
        'El <b>tool-calling</b> es el mecanismo que permite al LLM invocar funciones Python '
        'durante su proceso de razonamiento. En lugar de solo generar texto, el modelo puede '
        '"llamar" una función con argumentos estructurados. Python ejecuta la función y devuelve '
        'el resultado al modelo para que continúe.',
        S))

    story.append(h2('6.1 Cómo funciona el loop', S))
    story.append(data_table(
        ['Iteración', 'Python envía', 'LLM responde', 'Python hace'],
        [
            ['1', 'Imagen + TOOLS_SCHEMA', 'tool_calls: sort_to_left("Red Gala Apple")',
             'Ejecuta sort_to_left()'],
            ['—', 'Tool result: SUCCESS:Red Gala Apple:LEFT', '(fin — no más tool_calls)',
             'Termina el loop ✅'],
        ],
        widths=[CW*0.13, CW*0.28, CW*0.37, CW*0.22],
        S=S,
    ))
    story.append(sp(2))

    story.append(h2('6.2 Estructura del Schema JSON (OpenAI format)', S))
    story += code_block(
        '''# tools.py — Así se describe sort_to_left() al LLM:
{
    "type": "function",
    "function": {
        "name": "sort_to_left",
        "description": "Sort the detected fruit to the LEFT bin (e.g., for apples).",
        "parameters": {
            "type": "object",
            "properties": {
                "fruit_name": {
                    "type": "string",
                    "description": "The specific name of the fruit (e.g., 'Red Gala Apple')."
                }
            },
            "required": ["fruit_name"]
        }
    }
}''',
        title='tools.py — TOOLS_SCHEMA (formato OpenAI)', S=S, lang='json',
    )

    story.append(h2('6.3 Caso especial: imagen poco clara', S))
    story.append(p(
        'Si la primera foto no es suficientemente clara, el LLM puede llamar '
        '<font name="Courier">get_camera_image()</font> para pedir otra. En ese caso, Python '
        'captura un nuevo frame y <b>reemplaza</b> la imagen original en el historial de '
        'mensajes (en lugar de añadir un mensaje nuevo). Esto evita duplicar tokens de imagen '
        'en el contexto.',
        S))
    story.append(sp(2))

    story.append(h2('6.4 Condición de terminación', S))
    story.append(callout(
        'El loop termina cuando el resultado de una tool empieza con '
        '"SUCCESS:" o "DISCARD:". Si ninguna tool devuelve uno de estos prefijos '
        'en 5 iteraciones, se devuelve "ERROR:Max turns reached".',
        S))
    story.append(pb())
    return story


def build_lmstudio(S):
    story = [h1('7. Conexión con LMStudio', S)]
    story.append(lead(
        'LMStudio actúa como un servidor HTTP local que expone una API <b>100% compatible '
        'con OpenAI</b> en el puerto 1234. No hay ninguna diferencia en el código Python '
        'entre conectarse a LMStudio local o a la API de OpenAI real.',
        S))

    story.append(h2('7.1 Configuración', S))
    story.append(data_table(
        ['Parámetro', 'Valor', 'Dónde se define'],
        [
            ['URL base',       'http://127.0.0.1:1234/v1', 'llm.py → API_URL'],
            ['Modelo',         'qwen/qwen3-vl-4b',          'llm.py → LMSTUDIO_MODEL'],
            ['API Key',        'lm-studio',                 'llm.py → LMSTUDIO_API_KEY'],
            ['Endpoint usado', '/v1/chat/completions',      'llm.py → act_on_fruit()'],
            ['Puerto del server', '1234',                   'LMStudio Desktop → Developer'],
        ],
        widths=[CW*0.28, CW*0.36, CW*0.36],
        S=S,
    ))
    story.append(sp(2))

    story.append(h2('7.2 Requisitos del modelo', S))
    story.append(p(
        'El modelo debe soportar <b>visión (VLM)</b> y <b>tool-calling</b>. '
        'Qwen3-VL-4B es el modelo recomendado por su balance entre precisión y velocidad '
        'de inferencia local.',
        S))

    for txt in [
        'El servidor LMStudio debe estar activo antes de ejecutar service.py.',
        'En LMStudio Desktop: <b>Developer → Local Server → Start Server</b> (puerto 1234).',
        'El sistema verifica la conexión con <font name="Courier">llm.test_connection()</font> '
        'antes de iniciar el loop.',
        'Si LMStudio no responde, service.py muestra error y sale con código 1.',
    ]:
        story.append(bullet(txt, S, icon='▶'))
    story.append(pb())
    return story


def build_serial_protocol(S):
    story = [h1('8. Protocolo Serial Arduino', S)]
    story.append(lead(
        'La comunicación entre Python y el Arduino es texto plano a <b>115200 baud</b>. '
        'Cada comando es una línea terminada en <font name="Courier">\\n</font>. '
        'La respuesta también es una línea terminada en <font name="Courier">\\n</font>.',
        S))

    story.append(data_table(
        ['Comando enviado', 'Respuesta esperada', 'Acción en Arduino'],
        [
            ['PING',          'PONG',       'Verificación de conexión'],
            ['GET_DISTANCE',  '"12.34"',    'Lee VL53L0X, devuelve distancia en cm (float)'],
            ['APPLE',         'OK',         'Servo izq.: 90°→135°, espera 2.5s, →90°'],
            ['ORANGE',        'OK',         'Servo der.: 90°→45°, espera 2.5s, →90°'],
            ['(cualquier otro)', 'ERROR:UNKNOWN_COMMAND', 'Comando no reconocido'],
        ],
        widths=[CW*0.22, CW*0.22, CW*0.56],
        S=S, mono_cols=[0, 1],
    ))
    story.append(sp(2))

    story.append(h2('8.1 Casos especiales del sensor VL53L0X', S))
    story.append(data_table(
        ['Condición', 'Valor devuelto', 'Significado'],
        [
            ['RangeStatus == 4',      '999.0', 'Objeto fuera del campo visual del sensor'],
            ['Lectura < 30 mm',       '999.0', 'Muy cerca — fuera del rango mínimo configurado'],
            ['Lectura > 130 mm',      '999.0', 'Muy lejos — fuera del rango máximo configurado'],
            ['Lectura 30–130 mm',     'X.X cm', 'Objeto detectado en zona válida'],
        ],
        widths=[CW*0.33, CW*0.22, CW*0.45],
        S=S, mono_cols=[0, 1],
    ))
    story.append(sp(2))

    story.append(warn(
        '⚠  Al encender el Arduino, espera el mensaje READY en el monitor serial antes '
        'de ejecutar service.py. Si el VL53L0X no inicializa, el firmware envía '
        'ERROR:SENSOR_INIT y entra en loop infinito — revisa las conexiones I2C.',
        S))
    story.append(pb())
    return story


def build_quick_setup(S):
    story = [h1('9. Configuración Rápida', S)]

    story.append(h2('9.1 Paso 1 — LMStudio', S))
    for txt in [
        'Descarga e instala LMStudio desde <b>lmstudio.ai</b>.',
        'Carga el modelo con soporte de visión y tool-calling: <font name="Courier">qwen/qwen3-vl-4b</font>.',
        'En LMStudio Desktop: <b>Developer → Local Server → Start Server</b> (puerto 1234).',
    ]:
        story.append(bullet(txt, S))

    story.append(h2('9.2 Paso 2 — Arduino', S))
    for txt in [
        'Instala la librería <font name="Courier">Adafruit_VL53L0X</font> desde el Library Manager del IDE de Arduino.',
        'Conecta los componentes según la tabla de pines (Sección 2.3).',
        'Carga <font name="Courier">fruit_sorter_nuevo.ino</font> en el Arduino UNO.',
        'Verifica en el Monitor Serial (115200 baud) que aparezca <font name="Courier">READY</font>.',
    ]:
        story.append(bullet(txt, S))

    story.append(h2('9.3 Paso 3 — Python', S))
    story += code_block(
        '''# Instalar dependencias
python3 -m pip install -r requirements.txt

# Ejecutar el sistema
python3 service.py --port /dev/ttyUSB0 --camera 0 --threshold 13.0''',
        lang='bash', title='Terminal — Instalación y ejecución', S=S,
    )

    story.append(h2('9.4 Argumentos de Línea de Comandos', S))
    story.append(data_table(
        ['Argumento', 'Default', 'Descripción'],
        [
            ['--port PORT',       'Auto-detect', 'Puerto serial (ej. /dev/ttyUSB0 o COM5)'],
            ['--camera INDEX',    '0',           'Índice de cámara USB'],
            ['--threshold CM',    '13.0',        'Distancia máxima de detección en cm'],
        ],
        widths=[CW*0.28, CW*0.18, CW*0.54],
        S=S, mono_cols=[0, 1],
    ))
    story.append(pb())
    return story


def build_maqueta(S, maqueta_path):
    story = [h1('10. Prototipo Físico', S)]
    story.append(lead(
        'La maqueta está construida en triplay/MDF con una rampa central, dos compuertas '
        'laterales accionadas por los servos MG995, y dos contenedores: izquierdo para manzanas '
        'y derecho para naranjas. La cámara se monta sobre la rampa apuntando hacia abajo, '
        'y el sensor VL53L0X se coloca en el punto de detección.',
        S))

    if maqueta_path and os.path.exists(maqueta_path):
        img = Image(maqueta_path, width=CW * 0.75, height=10*cm, kind='proportional')
        # Center the image using a table
        story.append(Table([[img]], colWidths=[CW]))
        story.append(caption(
            'Figura 3 — Prototipo físico del Clasificador de Frutas con IA', S))
    else:
        story.append(warn(
            'Imagen de la maqueta no encontrada en assets/maqueta.jpeg', S))

    story.append(sp(3))

    story.append(h2('10.1 Estructura del Repositorio', S))
    story += code_block(
        '''Clasificador-de-frutas-/
│
├── service.py             # ▶ PUNTO DE ENTRADA — loop de detección
├── llm.py                 # Agente HTTP — loop agéntico via requests
├── tools.py               # Tools del LLM — schemas JSON + funciones Python
├── arduino.py             # Comunicación serial persistente (VL53L0X + servos)
├── camera.py              # Captura de imágenes webcam (conexión persistente)
├── mcp_service.py         # (Opcional) Servidor MCP via FastMCP SSE :8000
│
├── fruit_sorter_nuevo.ino # Firmware Arduino: VL53L0X I2C + 2x servo MG995
├── generate_pdf.py        # Este script — genera el reporte técnico
├── requirements.txt       # Dependencias Python
│
└── assets/
    ├── circuit_diagram.png
    ├── maqueta.jpeg
    └── demo.gif''',
        lang='bash', title='Estructura de directorios', S=S,
    )
    story.append(pb())
    return story


def build_glossary(S):
    story = [h1('11. Glosario', S)]
    story.append(lead(
        'Definición de los términos técnicos utilizados en el proyecto.',
        S))

    terms = [
        ('VL53L0X',
         'Sensor de distancia de Tiempo de Vuelo (ToF) fabricado por STMicroelectronics. '
         'Emite pulsos láser infrarrojos de 940 nm y mide la distancia calculando el tiempo '
         'que tarda la luz en regresar. Interfaz I2C, dirección 0x29.'),
        ('ToF (Time of Flight)',
         'Técnica de medición de distancia que calcula el tiempo que tarda una señal '
         '(luz, sonido) en ir al objeto y regresar. Ofrece alta precisión y es insensible '
         'al color o material de la superficie.'),
        ('I2C (Inter-Integrated Circuit)',
         'Protocolo de comunicación serial de dos cables: SDA (datos) y SCL (reloj). '
         'Permite conectar múltiples dispositivos en el mismo bus con distintas direcciones. '
         'En Arduino UNO: SDA = A4, SCL = A5.'),
        ('LMStudio',
         'Aplicación de escritorio para ejecutar modelos de lenguaje grande (LLM) '
         'localmente en la PC. Expone una API HTTP compatible con el estándar OpenAI '
         'en el puerto 1234.'),
        ('LLM (Large Language Model)',
         'Modelo de inteligencia artificial entrenado en grandes volúmenes de texto. '
         'Capaz de entender y generar lenguaje natural, razonar y, en versiones modernas, '
         'interpretar imágenes y llamar funciones (tool-calling).'),
        ('VLM (Vision Language Model)',
         'LLM con capacidad de procesar imágenes además de texto. En este proyecto se usa '
         'Qwen3-VL-4B, que recibe la imagen de la fruta codificada en Base64.'),
        ('Tool-Calling',
         'Mecanismo que permite a un LLM "llamar" funciones externas durante su respuesta. '
         'El modelo devuelve JSON con el nombre de la función y sus argumentos; Python lo '
         'ejecuta y devuelve el resultado al modelo para que continúe.'),
        ('MCP (Model Context Protocol)',
         'Estándar abierto de Anthropic para exponer herramientas, recursos y prompts '
         'a modelos de IA. Permite que agentes externos controlen el sistema sin modificar '
         'el código Python principal.'),
        ('SSE (Server-Sent Events)',
         'Protocolo HTTP unidireccional donde el servidor envía eventos al cliente en '
         'tiempo real. Usado por mcp_service.py como transporte para el servidor MCP.'),
        ('Base64',
         'Esquema de codificación que convierte datos binarios (como imágenes JPEG) '
         'a texto ASCII. Permite enviar imágenes dentro de un JSON sin caracteres especiales.'),
        ('PWM (Pulse Width Modulation)',
         'Señal de control para servomotores. El ancho del pulso (entre 1ms y 2ms) '
         'codifica el ángulo deseado. La librería Servo de Arduino genera esta señal '
         'automáticamente en los pines 9 y 10.'),
        ('Baud Rate',
         'Velocidad de comunicación serial en bits por segundo. El Arduino y Python '
         'deben usar el mismo valor. En este proyecto: 115200 bps.'),
        ('API Key (Bearer Token)',
         'Credencial de autenticación enviada en el encabezado HTTP Authorization. '
         'LMStudio acepta cualquier valor cuando corre localmente; se usa "lm-studio" '
         'para cumplir con el estándar.'),
    ]

    for term, definition in terms:
        story.append(Paragraph(f'<b>{term}</b>', S['GlossTerm']))
        story.append(Paragraph(definition, S['GlossDef']))

    return story


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    base    = Path(__file__).parent
    maqueta = str(base / 'assets' / 'maqueta.jpeg')
    circuit = str(base / 'assets' / 'circuit_diagram.png')
    output  = str(base / 'Reporte_Tecnico_FruitSorter_V4.pdf')

    print(f"Generando PDF: {output}")
    print(f"  Maqueta   : {'✓' if os.path.exists(maqueta) else '✗ no encontrada'}")
    print(f"  Circuito  : {'✓' if os.path.exists(circuit) else '✗ no encontrado'}")
    print(f"  Pygments  : {'✓' if HAS_PYGMENTS else '✗ sin syntax highlighting'}")

    maqueta_ok = maqueta if os.path.exists(maqueta) else None
    circuit_ok = circuit if os.path.exists(circuit) else None
    S = build_styles()

    # ── Secciones de contenido (iguales en ambos passes) ─────────────
    def content_sections():
        return (
            build_intro(S) +
            build_hardware(S, circuit_img_path=circuit_ok) +
            build_architecture(S) +
            build_software(S) +
            build_requests_section(S) +
            build_tool_calling(S) +
            build_lmstudio(S) +
            build_serial_protocol(S) +
            build_quick_setup(S) +
            build_maqueta(S, maqueta) +
            build_glossary(S)
        )

    # ── PASS 1: construir sin portada ni TOC para obtener páginas ─────
    print("  Pase 1: calculando números de página...")
    tmp_path = tempfile.mktemp(suffix='.pdf')
    tmp_doc  = FruitDoc(tmp_path, maqueta_path=maqueta_ok)
    tmp_doc.build([NextPageTemplate('Body')] + content_sections())
    section_pages = tmp_doc.section_pages
    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    # ── PASS 2: PDF final con portada + TOC estático + contenido ─────
    # Cover = página 1, TOC = página 2 → offset de +2
    print("  Pase 2: generando PDF final...")
    final_doc = FruitDoc(
        output,
        maqueta_path=maqueta_ok,
        title='Reporte Técnico — Clasificador de Frutas con IA V4',
        author='Jesús Andrés Mondragón Tenorio',
        subject='Arquitectura V4: HTTP requests + VL53L0X + Tool-Calling',
    )

    cover_pages = [
        NextPageTemplate('Cover'),
        Spacer(1, 1),
        NextPageTemplate('Body'),
        pb(),
    ]

    final_story = (
        cover_pages +
        build_toc(section_pages, S, page_offset=2) +
        content_sections()
    )
    final_doc.build(final_story)
    print(f"\n✅ PDF generado: {output}")


if __name__ == '__main__':
    main()
