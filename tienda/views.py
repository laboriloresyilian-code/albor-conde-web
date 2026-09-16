from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.core.mail import EmailMessage
from django.conf import settings
import json
from .models import Producto, Pedido, ItemPedido, Usuario, Categoria, Carrito
from django.utils import timezone
# ============================================================
# REPORTLAB PARA PDF
# ============================================================
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from io import BytesIO


# ============================================================
# API: CATÁLOGO DE PRODUCTOS
# ============================================================
def catalogo_api(request):
    productos = Producto.objects.all().select_related('categoria')
    data = []
    for p in productos:
        data.append({
            'id': p.id,
            'nombre': p.nombre,
            'descripcion': p.descripcion,
            'precio': float(p.precio),
            'stock': p.stock,
            'imagen': p.imagen,
            'categoria': p.categoria.nombre,
        })
    return JsonResponse(data, safe=False)


# ============================================================
# API: CREAR PEDIDO (CON PDF)
# ============================================================
def crear_pedido(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        user_email = data.get('user_email')
        items = data.get('items', [])
        total = data.get('total', 0)
        metodo_pago = data.get('metodo_pago', '')
        customer_data = data.get('customer', {})
        
        if not user_email or not items:
            return JsonResponse({'error': 'Faltan datos del usuario o items'}, status=400)
        
        usuario = Usuario.objects.filter(email=user_email).first()
        if not usuario:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
        
        # Crear el pedido
        pedido = Pedido.objects.create(
    usuario=usuario,
    total=total,
    metodo_pago=metodo_pago,
    estado='Pendiente',
    fecha_comprobacion=timezone.now(),
    fecha_pagado=timezone.now()
)
        
        # Crear los items del pedido y actualizar stock
        for item in items:
            producto = Producto.objects.filter(id=item['id']).first()
            if producto:
                ItemPedido.objects.create(
                    pedido=pedido,
                    producto=producto,
                    cantidad=item['cantidad'],
                    precio_unitario=item['precio']
                )
                producto.stock -= item['cantidad']
                producto.save()
        
     # ============================================================
# GENERAR PDF CON REPORTLAB (ESTRUCTURA TIPO FACTURA)
# ============================================================
from reportlab.platypus import Image as RLImage
import os
from django.conf import settings

pdf_buffer = BytesIO()
doc = SimpleDocTemplate(pdf_buffer, pagesize=A4,
                       rightMargin=1.5*cm, leftMargin=1.5*cm,
                       topMargin=1.5*cm, bottomMargin=1.5*cm)

styles = getSampleStyleSheet()

# Estilos
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontName='Helvetica-Bold',
    fontSize=16,
    textColor=colors.HexColor('#c9a84c'),
    alignment=0,
    spaceAfter=5,
)

company_style = ParagraphStyle(
    'CompanyStyle',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9,
    textColor=colors.HexColor('#888888'),
    alignment=0,
    spaceAfter=2,
)

section_title_style = ParagraphStyle(
    'SectionTitle',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=10,
    textColor=colors.HexColor('#1a1a1a'),
    spaceAfter=5,
    spaceBefore=10,
)

info_style = ParagraphStyle(
    'InfoStyle',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9,
    textColor=colors.HexColor('#1a1a1a'),
    spaceAfter=3,
)

footer_style = ParagraphStyle(
    'FooterStyle',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=8,
    textColor=colors.HexColor('#888888'),
    alignment=1,
    spaceAfter=4,
)

elements = []

# ============================================================
# ENCABEZADO CON LOGO
# ============================================================
logo_path = os.path.join(settings.BASE_DIR, 'static', 'Imagenes', 'logo.png')
if os.path.exists(logo_path):
    logo = RLImage(logo_path, width=3*cm, height=3*cm)
    header_table = Table([[logo, Paragraph("INMOBILIARIA ALBOR-CONDE<br/>Microempresa Privada", title_style)]],
                         colWidths=[3.5*cm, 13*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
else:
    elements.append(Paragraph("INMOBILIARIA ALBOR-CONDE", title_style))
    elements.append(Paragraph("Microempresa Privada", company_style))

elements.append(Spacer(1, 0.3*cm))

# ============================================================
# DATOS DEL CLIENTE Y OTROS DATOS
# ============================================================
fecha_str = pedido.fecha.strftime('%d/%m/%Y %H:%M')

cliente_data = [
    [Paragraph("<b>CLIENTE</b>", section_title_style), Paragraph("<b>OTROS DATOS</b>", section_title_style)],
    [Paragraph(f"{customer_data.get('name', '')}", info_style), Paragraph(f"{customer_data.get('email', '')}", info_style)],
    [Paragraph(f"{fecha_str}", info_style), Paragraph(f"MIPYME: Albor-Conde SURL", info_style)],
    [Paragraph(f"Factura No: {pedido.id}", info_style), Paragraph(f"Método: {metodo_pago}", info_style)],
]

cliente_table = Table(cliente_data, colWidths=[9*cm, 7.5*cm])
cliente_table.setStyle(TableStyle([
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ('LEFTPADDING', (0, 0), (-1, -1), 0),
]))
elements.append(cliente_table)

elements.append(Spacer(1, 0.5*cm))

# ============================================================
# TABLA DE PRODUCTOS
# ============================================================
table_data = [['Producto', 'Cantidad', 'Precio', 'Subtotal']]
for item in items:
    subtotal = float(item['precio']) * int(item['cantidad'])
    table_data.append([
        item['nombre'],
        str(item['cantidad']),
        f"${float(item['precio']):.2f}",
        f"${subtotal:.2f}"
    ])

product_table = Table(table_data, colWidths=[8*cm, 2.5*cm, 3*cm, 3*cm])
product_table.setStyle(TableStyle([
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e8e8e8')),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fcfcfc')]),
    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
]))
elements.append(product_table)

elements.append(Spacer(1, 0.7*cm))

# ============================================================
# DATOS DEL PAGO
# ============================================================
elements.append(Paragraph("<b>DATOS DEL PAGO</b>", section_title_style))
elements.append(Spacer(1, 0.2*cm))

# Determinar datos según método de pago
if metodo_pago and 'efectivo' in metodo_pago.lower():
    # Efectivo: nombre del cliente
    dato_pago = customer_data.get('name', '')
    label_pago = "Cliente"
else:
    # Transferencia: datos del cliente
    dato_pago = customer_data.get('name', '')
    label_pago = "Cliente"

pago_data = [
    [Paragraph("<b>No. cuenta / Cliente</b>", info_style), Paragraph("<b>Dirección / Método</b>", info_style), Paragraph("<b>Moneda</b>", info_style)],
    [Paragraph(dato_pago, info_style), Paragraph(metodo_pago or 'N/A', info_style), Paragraph("CUP", info_style)],
    [Paragraph("<b>Comprobación de pago</b>", info_style), Paragraph("<b>Pagado</b>", info_style), Paragraph("<b>Total</b>", info_style)],
    [Paragraph(pedido.fecha_comprobacion.strftime('%d/%m/%Y %H:%M') if pedido.fecha_comprobacion else 'Pendiente', info_style),
     Paragraph(pedido.fecha_pagado.strftime('%d/%m/%Y %H:%M') if pedido.fecha_pagado else fecha_str, info_style),
     Paragraph(f"${total:.2f}", info_style)],
]

pago_table = Table(pago_data, colWidths=[5*cm, 5.5*cm, 6*cm])
pago_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#1a1a1a')),
    ('TEXTCOLOR', (0, 2), (-1, 2), colors.white),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e8e8e8')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ('TOPPADDING', (0, 0), (-1, -1), 6),
]))
elements.append(pago_table)

elements.append(Spacer(1, 0.5*cm))

# ============================================================
# TOTAL DESTACADO
# ============================================================
total_data = [
    ['', 'TOTAL:', f"${total:.2f}"]
]
total_table = Table(total_data, colWidths=[10*cm, 3*cm, 3.5*cm])
total_table.setStyle(TableStyle([
    ('FONTNAME', (1, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (1, 0), (-1, 0), 14),
    ('TEXTCOLOR', (1, 0), (-1, 0), colors.HexColor('#c9a84c')),
    ('ALIGN', (1, 0), (-1, 0), 'RIGHT'),
    ('LINEABOVE', (1, 0), (-1, 0), 2, colors.HexColor('#c9a84c')),
    ('TOPPADDING', (0, 0), (-1, -1), 10),
]))
elements.append(total_table)

elements.append(Spacer(1, 1*cm))

# ============================================================
# PIE DE PÁGINA CON FIRMAS
# ============================================================
elements.append(Paragraph("Muchas gracias", ParagraphStyle('Thanks', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#c9a84c'), spaceAfter=10)))

firmas_data = [
    ['RESPONSABLE DE CARGA', 'FACTURADOR'],
    ['Firma: _____________________', 'Firma: _____________________'],
]
firmas_table = Table(firmas_data, colWidths=[8.5*cm, 8.5*cm])
firmas_table.setStyle(TableStyle([
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 9),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
    ('TOPPADDING', (0, 0), (-1, -1), 15),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
]))
elements.append(firmas_table)

elements.append(Spacer(1, 0.5*cm))

elements.append(Paragraph("ALBOR CONDE S.U.R.L - Baracoa, Guantánamo, Cuba", footer_style))
elements.append(Paragraph("Teléfono: +53 5 662 0861 | Email: alborconde@gmail.com", footer_style))

doc.build(elements)
pdf_buffer.seek(0)  
        

# ============================================================
# API: OBTENER HISTORIAL DE PEDIDOS
# ============================================================
def pedidos_usuario(request):
    user_email = request.GET.get('email')
    if not user_email:
        return JsonResponse({'error': 'Falta el email'}, status=400)
    
    usuario = Usuario.objects.filter(email=user_email).first()
    if not usuario:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
    
    pedidos = Pedido.objects.filter(usuario=usuario).order_by('-fecha')
    data = []
    for pedido in pedidos:
        items = []
        for item in pedido.items.all():
            items.append({
                'producto_nombre': item.producto.nombre,
                'cantidad': item.cantidad,
                'precio': float(item.precio_unitario)
            })
        data.append({
            'id': str(pedido.id),
            'fecha': pedido.fecha.isoformat(),
            'total': float(pedido.total),
            'estado': pedido.estado,
            'items': items
        })
    
    return JsonResponse(data, safe=False)


# ============================================================
# API: REGISTRAR USUARIO
# ============================================================
def registrar_usuario(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        email = data.get('email')
        nombre = data.get('nombre')
        password = data.get('password')
        telefono = data.get('telefono', '')
        direccion = data.get('direccion', '')
        
        if not email or not nombre or not password:
            return JsonResponse({'error': 'Faltan datos obligatorios'}, status=400)
        
        if Usuario.objects.filter(email=email).exists():
            return JsonResponse({'error': 'Este correo ya está registrado'}, status=400)
        
        usuario = Usuario.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=nombre,
            telefono=telefono,
            direccion=direccion
        )

        usuario.rol = 'user'
        usuario.save()
        return JsonResponse({'mensaje': 'Usuario registrado exitosamente', 'id': usuario.id})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
# API: LOGIN DE USUARIO
# ============================================================
def login_usuario(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        email = data.get('email')
        password = data.get('password')
        
        user = authenticate(username=email, password=password)
        
        if user is None:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user_obj = User.objects.filter(email=email).first()
                if user_obj:
                    user = authenticate(username=user_obj.username, password=password)
            except:
                pass
        
        if user is None:
            return JsonResponse({'error': 'Credenciales incorrectas'}, status=400)
        
        return JsonResponse({
            'mensaje': 'Login exitoso',
            'id': user.id,
            'nombre': user.first_name,
            'email': user.email if user.email else user.username,
            'role': user.rol,
            'telefono': user.telefono,
            'direccion': user.direccion,
            'creado': user.date_joined.isoformat()
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
# API: CANCELAR PEDIDO
# ============================================================
def cancelar_pedido(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        pedido_id = data.get('pedido_id')
        user_email = data.get('user_email')
        
        if not pedido_id or not user_email:
            return JsonResponse({'error': 'Faltan datos del pedido o usuario'}, status=400)
        
        usuario = Usuario.objects.filter(email=user_email).first()
        if not usuario:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
        
        pedido = Pedido.objects.filter(id=pedido_id, usuario=usuario).first()
        if not pedido:
            return JsonResponse({'error': 'Pedido no encontrado'}, status=404)
        
        if pedido.estado != 'Pendiente':
            return JsonResponse({'error': 'Solo se pueden cancelar pedidos en estado "Pendiente"'}, status=400)
        
        pedido.estado = 'Cancelado'
        pedido.save()
        
        items = ItemPedido.objects.filter(pedido=pedido)
        for item in items:
            producto = item.producto
            producto.stock += item.cantidad
            producto.save()
        
        return JsonResponse({'mensaje': 'Pedido cancelado exitosamente', 'pedido_id': pedido.id})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
# API: GUARDAR CARRITO EN EL SERVIDOR
# ============================================================
def guardar_carrito(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_email = data.get('email')
        items = data.get('items', [])
        
        if not user_email:
            return JsonResponse({'error': 'Falta el email del usuario'}, status=400)
        
        usuario = Usuario.objects.filter(email=user_email).first()
        if not usuario:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
        
        Carrito.objects.filter(usuario=usuario).delete()
        
        for item in items:
            producto = Producto.objects.filter(id=item['id']).first()
            if producto:
                Carrito.objects.create(
                    usuario=usuario,
                    producto=producto,
                    cantidad=item['cantidad']
                )
        
        return JsonResponse({'mensaje': 'Carrito guardado exitosamente'})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
# API: OBTENER CARRITO DESDE EL SERVIDOR
# ============================================================
def obtener_carrito(request):
    user_email = request.GET.get('email')
    if not user_email:
        return JsonResponse({'error': 'Falta el email'}, status=400)
    
    usuario = Usuario.objects.filter(email=user_email).first()
    if not usuario:
        return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
    
    carrito_items = Carrito.objects.filter(usuario=usuario).select_related('producto')
    data = []
    for item in carrito_items:
        data.append({
            'id': item.producto.id,
            'nombre': item.producto.nombre,
            'precio': float(item.producto.precio),
            'cantidad': item.cantidad,
            'imagen': item.producto.imagen
        })
    
    return JsonResponse(data, safe=False)


# ============================================================
# API: ENVIAR CORREO DE CONTACTO (CORREGIDO)
# ============================================================
def enviar_contacto(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        nombre = data.get('nombre')
        email = data.get('email')
        telefono = data.get('telefono', '')
        asunto = data.get('asunto')
        mensaje = data.get('mensaje')
        
        if not nombre or not email or not asunto or not mensaje:
            return JsonResponse({'error': 'Faltan datos obligatorios'}, status=400)
        
        email_message = EmailMessage(
            subject=f"Contacto ALBOR CONDE: {asunto}",
            body=f"Nombre: {nombre}\nEmail: {email}\nTeléfono: {telefono}\n\nMensaje:\n{mensaje}",
            from_email='alborconde@gmail.com',
            to=['laboriloresyilian@gmail.com']
        )
        email_message.send()
        
        return JsonResponse({'mensaje': 'Mensaje enviado correctamente'})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)