from rest_framework import permissions

class EsGestorBodega(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            (getattr(request.user, 'rol', None) == 'GESTOR_BODEGA' or request.user.is_staff)
        )

class EsInstitucionMedica(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            getattr(request.user, 'rol', None) == 'INSTITUCION_MEDICA'
        )