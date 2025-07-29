from django.shortcuts import render, redirect  # Added redirect
from django.urls import reverse_lazy , reverse
from django.contrib.auth import get_user_model
from django.views.generic import ListView, CreateView, UpdateView, FormView
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from tenants.models import Tenant
from django.contrib.auth.views import PasswordChangeView
from .forms import TenantUserForm, TenantUserCreateForm, AdminPasswordResetForm
from .mixins import MasterUserRequiredMixin


User = get_user_model()

# Create a custom user update form
class UserUpdateForm(MasterUserRequiredMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active']

class TenantListView(MasterUserRequiredMixin, ListView):
    model = Tenant
    template_name = 'tenant_management/tenant_list.html'
    ordering = ['-subscription_end']
    paginate_by = 20

class TenantCreateView(MasterUserRequiredMixin, CreateView):
    model = Tenant
    fields = ['tenant_id', 'name', 'db_alias', 'subscription_end', 'is_active', 'contact_email', 'contact_phone']
    template_name = 'tenant_management/tenant_form.html'
    success_url = reverse_lazy('tenant_management:tenant_list')

class TenantUpdateView(MasterUserRequiredMixin, UpdateView):
    model = Tenant
    fields = ['name', 'subscription_end', 'is_active', 'contact_email', 'contact_phone']
    template_name = 'tenant_management/tenant_form.html'
    success_url = reverse_lazy('tenant_management:tenant_list')
    
    def form_valid(self, form):
        # Add audit logging here later
        return super().form_valid(form)
    
class TenantUserListView(MasterUserRequiredMixin, ListView):
    template_name = 'tenant_management/user_list.html'  # Updated template path
    context_object_name = 'users'
    
    def get_queryset(self):
        tenant = Tenant.objects.get(pk=self.kwargs['tenant_id'])
        return User.objects.using(tenant.db_alias).all()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = Tenant.objects.get(pk=self.kwargs['tenant_id'])
        return context

class TenantUserCreateView(MasterUserRequiredMixin, CreateView):
    form_class = TenantUserCreateForm  # Use custom form
    template_name = 'tenant_management/user_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = Tenant.objects.get(pk=self.kwargs['tenant_id'])
        return context
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = Tenant.objects.get(pk=self.kwargs['tenant_id'])
        return kwargs
    
    def form_valid(self, form):
        tenant = Tenant.objects.get(pk=self.kwargs['tenant_id'])
        form.save(using=tenant.db_alias)
        return redirect('tenant_management:manage_users', tenant_id=tenant.pk)

class TenantUserUpdateView(MasterUserRequiredMixin, UpdateView):
    form_class = UserUpdateForm
    template_name = 'tenant_management/user_form.html'
    
    def get_object(self):
        self.tenant = Tenant.objects.get(pk=self.kwargs['tenant_id'])  # Store tenant in view
        return User.objects.using(self.tenant.db_alias).get(pk=self.kwargs['pk'])
    
    def form_valid(self, form):
        form.save(using=self.tenant.db_alias)
        return redirect('tenant_management:manage_users', tenant_id=self.tenant.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.tenant  # Make tenant available in template
        return context
    
        
class TenantUserPasswordView(MasterUserRequiredMixin, PasswordChangeView):
    template_name = 'tenant_management/password_form.html'
    success_url = reverse_lazy('tenant_management:manage_users')
    
    def get_object(self):
        tenant = Tenant.objects.get(pk=self.kwargs['tenant_id'])
        return User.objects.using(tenant.db_alias).get(pk=self.kwargs['pk'])
    
    def get_success_url(self):
        tenant_id = self.kwargs['tenant_id']
        return reverse('tenant_management:manage_users', kwargs={'tenant_id': tenant_id})
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Add email validation to password change if needed
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = Tenant.objects.get(pk=self.kwargs['tenant_id'])
        context['object'] = self.get_object()
        return context
    
class AdminPasswordResetView(MasterUserRequiredMixin, FormView):
    form_class = AdminPasswordResetForm
    template_name = 'tenant_management/password_form.html'
    
    def get_object(self):
        self.tenant = Tenant.objects.get(pk=self.kwargs['tenant_id'])
        return User.objects.using(self.tenant.db_alias).get(pk=self.kwargs['pk'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.get_object()
        context['tenant'] = self.tenant
        return context
    
    def form_valid(self, form):
        user = self.get_object()
        new_password = form.cleaned_data['new_password1']
        user.password = make_password(new_password)
        user.save(using=self.tenant.db_alias)
        
        messages.success(self.request, f"Password for {user.username} has been reset")
        return redirect('tenant_management:manage_users', tenant_id=self.tenant.pk)