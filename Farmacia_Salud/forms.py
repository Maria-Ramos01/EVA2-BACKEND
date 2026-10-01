from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

# Obtener el modelo de usuario activo en el proyecto
Usuario = get_user_model()

class RegistroUsuarioForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        # Especifica los campos que deseas solicitar en el formulario de registro
        fields = ('username', 'email', 'first_name', 'last_name')