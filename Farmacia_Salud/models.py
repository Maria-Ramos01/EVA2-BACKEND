from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. Modelo de Usuario con Roles
class Usuario(AbstractUser):
    ROLES = (
        ('INSTITUCION', 'Institución Médica'),
        ('GESTOR', 'Gestor de Bodega Farmacéutica'),
    )
    rol = models.CharField(max_length=20, choices=ROLES, default='INSTITUCION')

# 2. Categorías de Insumos
class Categoria(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

# 3. Catálogo de Insumos Médicos
class Insumo(models.Model):
    nombre_comercial = models.CharField(max_length=150)
    principio_activo = models.CharField(max_length=150)
    lote = models.CharField(max_length=50)
    fecha_vencimiento = models.DateField()
    precio_caja = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='insumos')

    def __str__(self):
        return f"{self.nombre_comercial} (Lote: {self.lote})"

# 4. Carro de Compras Persistente (1 a 1 con Usuario)
class CarroInsumos(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='carro')
    creado_en = models.DateTimeField(auto_now_add=True)

class CarroItem(models.Model):
    carro = models.ForeignKey(CarroInsumos, on_delete=models.CASCADE, related_name='items')
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad_cajas = models.PositiveIntegerField(default=1)

# 5. Solicitud de Abastecimiento / Orden
class SolicitudAbastecimiento(models.Model):
    ESTADOS = (
        ('PENDIENTE', 'Pendiente'),
        ('PAGADO', 'Pagado'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    )
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='solicitudes')
    creado_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

class SolicitudItem(models.Model):
    solicitud = models.ForeignKey(SolicitudAbastecimiento, on_delete=models.CASCADE, related_name='items')
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad_cajas = models.PositiveIntegerField()
    precio_historico = models.DecimalField(max_digits=10, decimal_places=2)