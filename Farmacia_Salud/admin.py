from django.contrib import admin
from .models import Categoria, Insumo

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')

@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('nombre_comercial', 'principio_activo', 'categoria', 'lote', 'fecha_vencimiento', 'precio_caja', 'stock')
    list_editable = ('stock', 'precio_caja') # Permite editar stock y precio directamente desde la lista