from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


# 1. Modelo de Usuario con Roles
class Usuario(AbstractUser):
    ROLES = (
        ('INSTITUCION_MEDICA', 'Institución Médica'),
        ('GESTOR_BODEGA', 'Gestor de Bodega Farmacéutica'),
    )
    rol = models.CharField(max_length=30, choices=ROLES, default='INSTITUCION_MEDICA')

    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"


# 2. Categorías de Insumos
class Categoria(models.Model):
    nombre = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'

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
        return f"{self.nombre_comercial} (Lote: {self.lote}) - Stock: {self.stock}"


# 4. Carro de Compras Persistente (1 a 1 con Usuario)
class CarroInsumos(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='carro')
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Carro de {self.usuario.username}"


class CarroItem(models.Model):
    carro = models.ForeignKey(CarroInsumos, on_delete=models.CASCADE, related_name='items')
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad_cajas = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('carro', 'insumo')

    def __str__(self):
        return f"{self.cantidad_cajas} cajas de {self.insumo.nombre_comercial}"


# 5. Solicitud de Abastecimiento / Orden
class SolicitudAbastecimiento(models.Model):
    # Permite que el usuario sea nulo para compras anónimas
    usuario = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    estado = models.CharField(max_length=50, default='PENDIENTE')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)


class SolicitudItem(models.Model):
    solicitud = models.ForeignKey(SolicitudAbastecimiento, on_delete=models.CASCADE, related_name='items')
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    cantidad_cajas = models.PositiveIntegerField()
    precio_historico = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad_cajas} cajas de {self.insumo.nombre_comercial} (Solicitud #{self.solicitud.id})"