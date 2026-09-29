from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction

# Rest Framework y JWT
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView  # <-- ¡ESTA LÍNEA FALTABA!

# Formularios
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

# Modelos y Serializadores
from .models import Insumo, CarroInsumos, CarroItem, SolicitudAbastecimiento, SolicitudItem, Usuario
from .serializers import (
    CustomTokenObtainPairSerializer, InsumoSerializer, 
    CarroInsumosSerializer, CarroItemSerializer, SolicitudAbastecimientoSerializer
)
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class EsGestorBodega(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'GESTOR'

class InsumoViewSet(viewsets.ModelViewSet):
    queryset = Insumo.objects.all()
    serializer_class = InsumoSerializer
    filterset_fields = ['categoria', 'principio_activo']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [EsGestorBodega()]

class CarroViewSet(viewsets.ModelViewSet):
    serializer_class = CarroInsumosSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CarroInsumos.objects.filter(usuario=self.request.user)

    @action(detail=False, methods=['post'])
    def agregar_item(self, request):
        carro, _ = CarroInsumos.objects.get_or_create(usuario=request.user)
        insumo_id = request.data.get('insumo')
        cantidad = int(request.data.get('cantidad_cajas', 1))

        item, created = CarroItem.objects.get_or_create(carro=carro, insumo_id=insumo_id)
        if not created:
            item.cantidad_cajas += cantidad
        else:
            item.cantidad_cajas = cantidad
        item.save()

        return Response({"mensaje": "Insumo agregado al carro persistente"}, status=status.HTTP_200_OK)

class SolicitudViewSet(viewsets.ModelViewSet):
    serializer_class = SolicitudAbastecimientoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.rol == 'GESTOR':
            return SolicitudAbastecimiento.objects.all()
        return SolicitudAbastecimiento.objects.filter(usuario=self.request.user)

    @action(detail=False, methods=['post'])
    def confirmar(self, request):
        carro, _ = CarroInsumos.objects.get_or_create(usuario=request.user)
        items_carro = carro.items.all()

        if not items_carro.exists():
            return Response({"error": "El carro está vacío"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            solicitud = SolicitudAbastecimiento.objects.create(
                usuario=request.user,
                estado='PENDIENTE',
                total=sum(i.insumo.precio_caja * i.cantidad_cajas for i in items_carro)
            )

            for item in items_carro:
                SolicitudItem.objects.create(
                    solicitud=solicitud,
                    insumo=item.insumo,
                    cantidad_cajas=item.cantidad_cajas,
                    precio_historico=item.insumo.precio_caja
                )

            items_carro.delete()

        return Response({"mensaje": "Solicitud creada exitosamente", "id": solicitud.id}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], permission_classes=[EsGestorBodega])
    def estado(self, request, pk=None):
        solicitud = self.get_object()
        nuevo_estado = request.data.get('estado')

        if nuevo_estado not in ['PAGADO', 'ENTREGADO', 'CANCELADO']:
            return Response({"error": "Estado inválido"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Descuento atómico de stock al pasar a PAGADO
            if nuevo_estado == 'PAGADO' and solicitud.estado != 'PAGADO':
                for item in solicitud.items.all():
                    if item.insumo.stock < item.cantidad_cajas:
                        return Response(
                            {"error": f"Stock insuficiente para {item.insumo.nombre_comercial}"}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    item.insumo.stock -= item.cantidad_cajas
                    item.insumo.save()

            # Reintegración de stock al CANCELAR
            elif nuevo_estado == 'CANCELADO' and solicitud.estado == 'PAGADO':
                for item in solicitud.items.all():
                    item.insumo.stock += item.cantidad_cajas
                    item.insumo.save()

            solicitud.estado = nuevo_estado
            solicitud.save()

        return Response({"mensaje": f"Estado actualizado a {nuevo_estado}"})

# Registro de Usuario
def registro_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "¡Registro exitoso! Bienvenido a Farmacia Salud.")
            return redirect('catalogo')
    else:
        form = UserCreationForm()
    return render(request, 'registro.html', {'form': form})

# Inicio de Sesión
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('catalogo')
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

# Cerrar Sesión
def logout_view(request):
    logout(request)
    return redirect('login')

# Catálogo de Productos
def catalogo_view(request):
    insumos = Insumo.objects.all()
    return render(request, 'catalogo.html', {'insumos': insumos})

# Agregar al Carro
@login_required
def agregar_al_carro(request, insumo_id):
    insumo = get_object_or_404(Insumo, id=insumo_id)
    carro, _ = CarroInsumos.objects.get_or_create(usuario=request.user)
    
    item, created = CarroItem.objects.get_or_create(carro=carro, insumo=insumo)
    if not created:
        item.cantidad_cajas += 1
    item.save()
    
    messages.success(request, f"{insumo.nombre_comercial} añadido al carro.")
    return redirect('catalogo')

# Ver Carro de Compras
@login_required
def ver_carro(request):
    carro, _ = CarroInsumos.objects.get_or_create(usuario=request.user)
    items = carro.items.all()
    
    total = sum(item.insumo.precio_caja * item.cantidad_cajas for item in items)
    return render(request, 'carro.html', {'items': items, 'total': total})

# Procesar Pago y Descontar Stock
@login_required
def procesar_pago(request):
    carro = get_object_or_404(CarroInsumos, usuario=request.user)
    items = carro.items.all()
    
    if not items.exists():
        messages.error(request, "Tu carro está vacío.")
        return redirect('ver_carro')
    
    with transaction.atomic():
        # 1. Validar Stock suficiente para todos los ítems antes de procesar
        for item in items:
            if item.insumo.stock < item.cantidad_cajas:
                messages.error(request, f"Stock insuficiente para {item.insumo.nombre_comercial}. Disponible: {item.insumo.stock}")
                return redirect('ver_carro')
        
        # 2. Crear la Solicitud / Orden de Compra en estado PAGADO
        total_orden = sum(item.insumo.precio_caja * item.cantidad_cajas for item in items)
        solicitud = SolicitudAbastecimiento.objects.create(
            usuario=request.user,
            estado='PAGADO',
            total=total_orden
        )
        
        # 3. Descontar Stock de los productos en PostgreSQL
        for item in items:
            SolicitudItem.objects.create(
                solicitud=solicitud,
                insumo=item.insumo,
                cantidad_cajas=item.cantidad_cajas,
                precio_historico=item.insumo.precio_caja
            )
            # Descuento de stock
            item.insumo.stock -= item.cantidad_cajas
            item.insumo.save()
            
        # 4. Vaciar el carro persistente
        items.delete()
        
    messages.success(request, f"¡Pago exitoso! Se ha generado tu pedido #{solicitud.id} y el stock fue actualizado.")
    return redirect('catalogo')