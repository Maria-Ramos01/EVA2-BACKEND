from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import Insumo, CarroInsumos, CarroItem, SolicitudAbastecimiento, SolicitudItem
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