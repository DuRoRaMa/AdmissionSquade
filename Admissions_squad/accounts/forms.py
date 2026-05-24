from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from phonenumber_field.formfields import PhoneNumberField

class CustomUserCreationForm(UserCreationForm):
    phone = PhoneNumberField(
        widget=forms.TextInput(attrs={'placeholder': '+7 (999) 123-45-67'})
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 
                  'middle_name', 'phone', 'password1', 'conf_password']