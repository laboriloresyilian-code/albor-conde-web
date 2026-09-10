from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from tienda import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/productos/', views.catalogo_api, name='catalogo_api'),
    path('api/crear-pedido/', views.crear_pedido, name='crear_pedido'),
    path('api/pedidos/', views.pedidos_usuario, name='pedidos_usuario'),
    path('api/registro/', views.registrar_usuario, name='registro'),
    path('api/login/', views.login_usuario, name='login'),
    path('api/cancelar-pedido/', views.cancelar_pedido, name='cancelar_pedido'),
    path('api/guardar-carrito/', views.guardar_carrito, name='guardar_carrito'),
    path('api/obtener-carrito/', views.obtener_carrito, name='obtener_carrito'),
    path('api/contacto/', views.enviar_contacto, name='enviar_contacto'),
    
    path('index.html', TemplateView.as_view(template_name='index.html')),
    path('catalogo.html', TemplateView.as_view(template_name='catalogo.html')),
    path('carrito.html', TemplateView.as_view(template_name='carrito.html')),
    path('checkout.html', TemplateView.as_view(template_name='checkout.html')),
    path('confirmacion.html', TemplateView.as_view(template_name='confirmacion.html')),
    path('contacto.html', TemplateView.as_view(template_name='contacto.html')),
    path('detalle-producto.html', TemplateView.as_view(template_name='detalle-producto.html')),
    path('historial-pedidos.html', TemplateView.as_view(template_name='historial-pedidos.html')),
    path('perfil.html', TemplateView.as_view(template_name='perfil.html')),
    path('admin.html', TemplateView.as_view(template_name='admin.html')),
    path('', TemplateView.as_view(template_name='index.html')),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])