from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.core.mail import EmailMessage
from django.conf import settings
import json
from .models import Producto, Pedido, ItemPedido, Usuario, Categoria, Carrito

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
            estado='Pendiente'
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
        # GENERAR PDF CON REPORTLAB
        # ============================================================
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4,
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            textColor=colors.HexColor('#c9a84c'),
            alignment=1,
            spaceAfter=10,
        )
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=colors.HexColor('#1a1a1a'),
            alignment=1,
            spaceAfter=20,
        )
        
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=4,
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
        
        elements.append(Paragraph("ALBOR CONDE", title_style))
        elements.append(Paragraph("Factura Electrónica", subtitle_style))
        elements.append(Spacer(1, 0.5*cm))
        
        elements.append(Paragraph(f"<b>Cliente:</b> {customer_data.get('name', '')}", info_style))
        elements.append(Paragraph(f"<b>Email:</b> {customer_data.get('email', '')}", info_style))
        elements.append(Paragraph(f"<b>Dirección:</b> {customer_data.get('address', '')}", info_style))
        elements.append(Paragraph(f"<b>Teléfono:</b> {customer_data.get('phone', '')}", info_style))
        elements.append(Paragraph(f"<b>Fecha:</b> {pedido.fecha.strftime('%d/%m/%Y %H:%M')}", info_style))
        elements.append(Paragraph(f"<b>Método de pago:</b> {metodo_pago}", info_style))
        elements.append(Spacer(1, 0.5*cm))
        
        table_data = [['Producto', 'Cantidad', 'Precio', 'Subtotal']]
        for item in items:
            subtotal = float(item['precio']) * int(item['cantidad'])
            table_data.append([
                item['nombre'],
                str(item['cantidad']),
                f"${float(item['precio']):.2f}",
                f"${subtotal:.2f}"
            ])
        
        table_data.append(['', '', 'TOTAL:', f"${total:.2f}"])
        
        product_table = Table(table_data, colWidths=[5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        product_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c9a84c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
            ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (2, -1), (-1, -1), colors.HexColor('#c9a84c')),
        ]))
        elements.append(product_table)
        elements.append(Spacer(1, 0.5*cm))
        
        elements.append(Paragraph("¡Gracias por tu confianza!", footer_style))
        elements.append(Paragraph("ALBOR CONDE S.U.R.L - Baracoa, Guantánamo, Cuba", footer_style))
        elements.append(Paragraph("Teléfono: +53 5 662 0861 | Email: alborconde@gmail.com", footer_style))
        
        doc.build(elements)
        pdf_buffer.seek(0)
        
        # Enviar al cliente
        subject = f"Confirmación de pedido #{pedido.id} - ALBOR CONDE"
        body = f"Gracias por tu pedido #{pedido.id}. Adjuntamos el detalle."
        email = EmailMessage(subject, body, 'alborconde@gmail.com', [user_email])
        email.attach(f'pedido_{pedido.id}.pdf', pdf_buffer.getvalue(), 'application/pdf')
        email.send()
        
        # Enviar a administradores
        administradores = Usuario.objects.filter(rol='admin')
        admin_emails = [admin.email for admin in administradores if admin.email]
        
        if admin_emails:
            pdf_buffer.seek(0)
            email_admin = EmailMessage(
                subject=f"Nuevo pedido #{pedido.id} - ALBOR CONDE",
                body=f"El cliente {customer_data.get('name', '')} ha realizado un nuevo pedido. Adjuntamos el detalle.",
                from_email='alborconde@gmail.com',
                to=admin_emails
            )
            email_admin.attach(f'pedido_{pedido.id}.pdf', pdf_buffer.getvalue(), 'application/pdf')
            email_admin.send()
        
        return JsonResponse({'mensaje': 'Pedido creado exitosamente', 'pedido_id': pedido.id})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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