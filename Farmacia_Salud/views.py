from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import F

# Rest Framework y JWT
from rest_framework import viewsets, permissions, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView  
from rest_framework.permissions import IsAuthenticated

# Modelos y Serializadores
from .models import Insumo, CarroInsumos, CarroItem, SolicitudAbastecimiento, SolicitudItem, Usuario, Categoria
from .serializers import (
    CustomTokenObtainPairSerializer, InsumoSerializer, 
    CarroInsumosSerializer, CarroItemSerializer, SolicitudAbastecimientoSerializer
)

User = get_user_model()

# ==========================================
# 1. AUTENTICACIÓN & VISTAS WEB
# ==========================================

def registro_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'registro.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está registrado.')
            return render(request, 'registro.html')

        # Crear el usuario en la BD (contraseña encriptada)
        usuario = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Generar Tokens JWT
        refresh = RefreshToken.for_user(usuario)
        request.session['jwt_token'] = str(refresh.access_token)

        login(request, usuario)
        messages.success(request, f'¡Cuenta creada con éxito! Bienvenido/a {usuario.username}.')
        return redirect('catalogo')

    return render(request, 'registro.html')


def login_jwt_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            
            refresh = RefreshToken.for_user(user)
            request.session['jwt_token'] = str(refresh.access_token)

            messages.success(request, f'Sesión iniciada correctamente.')
            return redirect('catalogo')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# ==========================================
# 2. VISTAS DEL CATÁLOGO Y PEDIDOS
# ==========================================

def catalogo_view(request):
    categorias = Categoria.objects.all()
    insumos = Insumo.objects.select_related('categoria').all()
    
    return render(request, 'catalogo.html', {
        'categorias': categorias,
        'insumos': insumos,
    })


def agregar_al_carro(request, insumo_id):
    insumo = get_object_or_404(Insumo, id=insumo_id)

    if request.user.is_authenticated:
        carro, _ = CarroInsumos.objects.get_or_create(usuario=request.user)
        item, created = CarroItem.objects.get_or_create(carro=carro, insumo=insumo)
        if not created:
            item.cantidad_cajas += 1
        item.save()
    else:
        carro = request.session.get('carro', {})
        insumo_id_str = str(insumo_id)
        carro[insumo_id_str] = carro.get(insumo_id_str, 0) + 1
        request.session['carro'] = carro

    return redirect('catalogo')


def ver_carro(request):
    items_carro = []
    total = 0

    if request.user.is_authenticated:
        carro, _ = CarroInsumos.objects.get_or_create(usuario=request.user)
        if hasattr(carro, 'items'):
            for item in carro.items.all():
                precio_unitario = getattr(item.insumo, 'precio_caja', 0)
                subtotal = precio_unitario * item.cantidad_cajas
                total += subtotal
                items_carro.append({
                    'insumo': item.insumo,
                    'cantidad': item.cantidad_cajas,
                    'precio_unitario': precio_unitario,
                    'subtotal': subtotal
                })
    else:
        session_carro = request.session.get('carro', {})
        for insumo_id, cantidad in session_carro.items():
            try:
                insumo = Insumo.objects.get(id=insumo_id)
                precio_unitario = getattr(insumo, 'precio_caja', 0)
                subtotal = precio_unitario * cantidad
                total += subtotal
                items_carro.append({
                    'insumo': insumo,
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario, 
                    'subtotal': subtotal
                })
            except Insumo.DoesNotExist:
                continue

    return render(request, 'carro.html', {'items_carro': items_carro, 'total': total})


def confirmar_pago(request):
    carro_items = {}
    
    if request.user.is_authenticated:
        carro_bd = getattr(request.user, 'carroinsumos', None)
        if carro_bd and hasattr(carro_bd, 'items'):
            for item in carro_bd.items.all():
                carro_items[item.insumo.id] = item.cantidad_cajas
    else:
        carro_items = request.session.get('carro', {})

    if not carro_items:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect('catalogo')

    usuario_pedido = request.user if request.user.is_authenticated else User.objects.first()

    with transaction.atomic():
        solicitud = SolicitudAbastecimiento.objects.create(
            usuario=usuario_pedido,
            estado='PAGADO',
            total=0
        )
        total = 0

        for insumo_id, cantidad in carro_items.items():
            try:
                insumo = Insumo.objects.select_for_update().get(id=insumo_id)
                precio_unitario = getattr(insumo, 'precio_caja', 0)
                subtotal = precio_unitario * cantidad
                total += subtotal

                SolicitudItem.objects.create(
                    solicitud=solicitud,
                    insumo=insumo,
                    cantidad_cajas=cantidad,
                    precio_historico=precio_unitario
                )

                # Descontar stock
                if hasattr(insumo, 'stock'):
                    Insumo.objects.filter(id=insumo.id).update(stock=F('stock') - cantidad)
                elif hasattr(insumo, 'stock_cajas'):
                    Insumo.objects.filter(id=insumo.id).update(stock_cajas=F('stock_cajas') - cantidad)

            except Insumo.DoesNotExist:
                continue

        solicitud.total = total
        solicitud.save()

    request.session['carro'] = {}
    if request.user.is_authenticated and hasattr(request.user, 'carroinsumos'):
        request.user.carroinsumos.items.all().delete()

    if request.user.is_authenticated:
        messages.success(request, f"¡Solicitud #{solicitud.id} procesada con éxito!")
        return redirect('mis_solicitudes')
    
    messages.success(request, "¡Compra realizada con éxito!")
    return redirect('catalogo')


@login_required(login_url='login')  
def mis_solicitudes(request):
    solicitudes = SolicitudAbastecimiento.objects.filter(usuario=request.user).order_by('-id')
    return render(request, 'mis_solicitudes.html', {'solicitudes': solicitudes})


@login_required(login_url='login')
def cambiar_estado_solicitud(request, solicitud_id, nuevo_estado):
    solicitud = get_object_or_404(SolicitudAbastecimiento, id=solicitud_id, usuario=request.user)

    if request.method == 'POST':
        if nuevo_estado == 'ENTREGADO' and solicitud.estado not in ['CANCELADO', 'ENTREGADO']:
            solicitud.estado = 'ENTREGADO'
            solicitud.save()
            messages.success(request, f"Solicitud #{solicitud.id} marcada como ENTREGADA.")

        elif nuevo_estado == 'CANCELADO' and solicitud.estado not in ['CANCELADO', 'ENTREGADO']:
            with transaction.atomic():
                solicitud.estado = 'CANCELADO'
                solicitud.save()

                for item in solicitud.items.all():
                    insumo = item.insumo
                    if hasattr(insumo, 'stock'):
                        Insumo.objects.filter(id=insumo.id).update(stock=F('stock') + item.cantidad_cajas)
                    elif hasattr(insumo, 'stock_cajas'):
                        Insumo.objects.filter(id=insumo.id).update(stock_cajas=F('stock_cajas') + item.cantidad_cajas)

            messages.info(request, f"Solicitud #{solicitud.id} cancelada. Stock reintegrado.")

    return redirect('mis_solicitudes')


def estado_compra(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudAbastecimiento, id=solicitud_id)
    return render(request, 'estado_compra.html', {'solicitud': solicitud})


def gestor_bodega(request):
    solicitudes = SolicitudAbastecimiento.objects.all().order_by('-id')
    return render(request, 'gestor_bodega.html', {'solicitudes': solicitudes})


# ==========================================
# 3. API REST FRAMEWORK & ENDPOINTS JWT
# ==========================================

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class EsGestorBodega(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, 'rol', '') == 'GESTOR'

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
        if getattr(self.request.user, 'rol', '') == 'GESTOR':
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
            if nuevo_estado == 'PAGADO' and solicitud.estado != 'PAGADO':
                for item in solicitud.items.all():
                    if item.insumo.stock < item.cantidad_cajas:
                        return Response(
                            {"error": f"Stock insuficiente para {item.insumo.nombre_comercial}"}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    item.insumo.stock -= item.cantidad_cajas
                    item.insumo.save()

            elif nuevo_estado == 'CANCELADO' and solicitud.estado == 'PAGADO':
                for item in solicitud.items.all():
                    item.insumo.stock += item.cantidad_cajas
                    item.insumo.save()

            solicitud.estado = nuevo_estado
            solicitud.save()

        return Response({"mensaje": f"Estado actualizado a {nuevo_estado}"})


class ProcesarPagoSolicitudAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        solicitud = get_object_or_404(SolicitudAbastecimiento, pk=pk, usuario=request.user)

        if solicitud.estado != 'PENDIENTE':
            return Response(
                {"error": "La solicitud ya ha sido procesada o cancelada previamente."},
                status=status.HTTP_400_BAD_REQUEST
            )

        for item in solicitud.items.all():
            if item.insumo.stock < item.cantidad_cajas:
                return Response(
                    {"error": f"Stock insuficiente para '{item.insumo.nombre_comercial}'."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        for item in solicitud.items.all():
            insumo = item.insumo
            insumo.stock -= item.cantidad_cajas
            insumo.save()

        solicitud.estado = 'PAGADO'
        solicitud.save()

        return Response(
            {"mensaje": "Pago procesado exitosamente.", "solicitud_id": solicitud.id},
            status=status.HTTP_200_OK
        )

class ActualizarEstadoGestorAPIView(views.APIView):
    permission_classes = [IsAuthenticated]  # Requiere autenticación (y rol Gestor si aplica)

    @transaction.atomic
    def patch(self, request, pk):
        solicitud = get_object_or_404(SolicitudAbastecimiento, pk=pk)
        nuevo_estado = request.data.get('estado')

        if nuevo_estado not in ['ENTREGADO', 'CANCELADO']:
            return Response(
                {"error": "Estado no válido. Use 'ENTREGADO' o 'CANCELADO'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Transición a ENTREGADO
        if nuevo_estado == 'ENTREGADO':
            solicitud.estado = 'ENTREGADO'
            solicitud.save()
            return Response({"mensaje": "Orden finalizada y entregada con éxito."})

        # Transición a CANCELADO (Reincorporar stock)
        if nuevo_estado == 'CANCELADO':
            if solicitud.estado == 'PAGADO':
                for item in solicitud.items.all():
                    insumo = item.insumo
                    if hasattr(insumo, 'stock'):
                        Insumo.objects.filter(id=insumo.id).update(stock=F('stock') + item.cantidad_cajas)
                    elif hasattr(insumo, 'stock_cajas'):
                        Insumo.objects.filter(id=insumo.id).update(stock_cajas=F('stock_cajas') + item.cantidad_cajas)

            solicitud.estado = 'CANCELADO'
            solicitud.save()
            return Response({"mensaje": "Orden cancelada. Existencias reincorporadas al inventario de bodega."})