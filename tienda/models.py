from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. MODELO CATEGORIA
class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name_plural = "Categorías"


# 2. MODELO PRODUCTO
class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    imagen = models.URLField(max_length=500, blank=True, null=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='productos')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


# 3. MODELO USUARIO PERSONALIZADO (Con los campos extra)
class Usuario(AbstractUser):
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    rol = models.CharField(max_length=20, choices=[('admin', 'Administrador'), ('user', 'Cliente')], default='user')

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='tienda_usuario_set',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='tienda_usuario_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    def __str__(self):
        return self.username


# 4. MODELO PEDIDO
class Pedido(models.Model):
    ESTADOS = [
        ('Pendiente', 'Pendiente'),
        ('En preparación', 'En preparación'),
        ('Enviado', 'Enviado'),
        ('Entregado', 'Entregado'),
        ('Cancelado', 'Cancelado'),
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='pedidos')
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='Pendiente')
    metodo_pago = models.CharField(max_length=50, blank=True, null=True)
    cancelable_hasta = models.DateTimeField(blank=True, null=True)
    fecha_comprobacion = models.DateTimeField(blank=True, null=True)
    fecha_pagado = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Pedido #{self.id} - {self.usuario.username}"


# 5. MODELO ITEM PEDIDO (Detalle de cada producto en el pedido)
class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"


# 6. MODELO CARRITO (Para guardar carrito en el servidor) - NUEVO
class Carrito(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='carrito_items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'producto')  # Un usuario solo puede tener un registro por producto

    def __str__(self):
        return f"{self.usuario.username} - {self.producto.nombre} x{self.cantidad}"