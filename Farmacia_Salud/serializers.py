from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Usuario, Categoria, Insumo, CarroInsumos, CarroItem, SolicitudAbastecimiento, SolicitudItem

# Claim Personalizado de Rol en Token JWT
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        token['username'] = user.username
        return token

class InsumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insumo
        fields = '__all__'

class CarroItemSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.ReadOnlyField(source='insumo.nombre_comercial')

    class Meta:
        model = CarroItem
        fields = ['id', 'insumo', 'insumo_nombre', 'cantidad_cajas']

class CarroInsumosSerializer(serializers.ModelSerializer):
    items = CarroItemSerializer(many=True, read_only=True)

    class Meta:
        model = CarroInsumos
        fields = ['id', 'usuario', 'items', 'creado_en']

class SolicitudItemSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.ReadOnlyField(source='insumo.nombre_comercial')
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = SolicitudItem
        fields = ['id', 'insumo', 'insumo_nombre', 'cantidad_cajas', 'precio_unitario', 'subtotal']

class SolicitudAbastecimientoSerializer(serializers.ModelSerializer):
    items = SolicitudItemSerializer(many=True, read_only=True)

    class Meta:
        model = SolicitudAbastecimiento
        fields = ['id', 'institucion', 'fecha_creacion', 'estado', 'total', 'items']
        read_only_fields = ['institucion', 'estado', 'total']