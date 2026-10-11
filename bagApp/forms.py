# bagApp/forms.py
from django import forms
from django.contrib.auth.models import User

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full border border-gray-300 px-4 py-3 rounded-md focus:ring-black focus:border-black',
        'placeholder': 'Create a password'
    }))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full border border-gray-300 px-4 py-3 rounded-md focus:ring-black focus:border-black',
        'placeholder': 'Confirm password'
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'w-full border border-gray-300 px-4 py-3 rounded-md focus:ring-black focus:border-black',
        'placeholder': 'Email address'
    }))
    first_name = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'w-full border border-gray-300 px-4 py-3 rounded-md focus:ring-black focus:border-black',
        'placeholder': 'First Name'
    }))
    last_name = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'w-full border border-gray-300 px-4 py-3 rounded-md focus:ring-black focus:border-black',
        'placeholder': 'Last Name'
    }))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password != password_confirm:
            raise forms.ValidationError("Passwords do not match.")