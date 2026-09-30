"""drf URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from Farmacia_Salud.views import ProcesarPagoSolicitudAPIView, ActualizarEstadoGestorAPIView
from Farmacia_Salud.views import (
    catalogo_view, login_view, logout_view, registro_view,
    agregar_al_carro, ver_carro, procesar_pago
)

from Farmacia_Salud.views import (
    CustomTokenObtainPairView, InsumoViewSet, CarroViewSet, SolicitudViewSet
)

router = DefaultRouter()
router.register(r'insumos', InsumoViewSet, basename='insumo')
router.register(r'carro-insumos', CarroViewSet, basename='carro-insumos')
router.register(r'solicitudes', SolicitudViewSet, basename='solicitud')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Endpoints JWT
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Rutas API
    path('api/', include(router.urls)),
    
    # Swagger / OpenAPI Docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Vista principal del Catálogo
    path('', catalogo_view, name='catalogo'),
    # Ruta del Login Propio
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    # Ruta de Cierre de Sesión (Redirige al catálogo)
    path('logout/', LogoutView.as_view(next_page='catalogo'), name='logout'),
    # Registro de usuarios
    path('registro/', registro_view, name='registro'),
    path('carro/', ver_carro, name='ver_carro'),
    path('carro/agregar/<int:insumo_id>/', agregar_al_carro, name='agregar_al_carro'),
    path('carro/pagar/', procesar_pago, name='procesar_pago'),
    path('api/solicitud/<int:pk>/pagar/', ProcesarPagoSolicitudAPIView.as_view(), name='api_pagar_solicitud'),
    path('api/solicitud/<int:pk>/cambiar-estado/', ActualizarEstadoGestorAPIView.as_view(), name='api_cambiar_estado'),
]