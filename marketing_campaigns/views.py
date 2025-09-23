# marketing_campaigns/views.py - TEMPLATES ONLY (Phase 1)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required

from .models import MessageTemplate, CampaignCategory, TenantCampaignSettings, CustomAudience
from .forms import MessageTemplateForm 

import csv
from io import StringIO
import re


# ================================
# DASHBOARD HOME (Temporary)
# ================================

@login_required
def dashboard_home(request, tenant_id):
    """Temporary dashboard - just show basic info"""
    
    total_templates = MessageTemplate.objects.count()
    categories = CampaignCategory.objects.count()
    
    context = {
        'total_templates': total_templates,
        'total_categories': categories,
    }
    
    return render(request, 'marketing_campaigns/marketing_dashboard.html', context)

# ================================
# TEMPLATE MANAGEMENT
# ================================

@login_required
def templates_list(request, tenant_id):
    """List all message templates"""
    
    # Filters
    category_filter = request.GET.get('category')
    search_filter = request.GET.get('search')
    
    templates = MessageTemplate.objects.filter(is_active=True)
    
    if category_filter:
        templates = templates.filter(category_id=category_filter)
    
    if search_filter:
        templates = templates.filter(
            Q(name__icontains=search_filter) | 
            Q(content__icontains=search_filter)
        )
    
    templates = templates.order_by('-usage_count', 'name')
    
    # Pagination
    paginator = Paginator(templates, 10)
    page_number = request.GET.get('page')
    templates_page = paginator.get_page(page_number)
    
    # Get categories for filter
    categories = CampaignCategory.objects.filter(is_active=True)
    
    context = {
        'templates': templates_page,
        'categories': categories,
        'current_category': category_filter,
        'search_query': search_filter,
    }
    
    return render(request, 'marketing_campaigns/templates_list.html', context)

@login_required
def template_create(request, tenant_id):
    """Create new message template"""
    
    if request.method == 'POST':
        form = MessageTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = request.user.username if hasattr(request.user, 'username') else 'admin'
            template.save()
            
            messages.success(request, f'Template "{template.name}" created successfully!')
            return redirect('marketing_campaigns:templates_list', tenant_id=tenant_id)
    else:
        form = MessageTemplateForm()
    
    # Get available variables from tenant settings
    try:
        settings = TenantCampaignSettings.objects.get(id=1)
        available_variables = settings.get_default_variables()
    except TenantCampaignSettings.DoesNotExist:
        available_variables = {
            "phone_number": {"type": "text", "description": "Phone number"},
            "name": {"type": "text", "description": "Member name"},
        }
    
    context = {
        'form': form,
        'available_variables': available_variables,
        'page_title': 'Create Template',
    }
    
    return render(request, 'marketing_campaigns/template_form_simple.html', context)

@login_required
def template_edit(request, tenant_id, pk):
    """Edit existing template"""
    
    template = get_object_or_404(MessageTemplate, pk=pk)
    
    if request.method == 'POST':
        # We'll implement form processing after creating forms.py
        messages.success(request, f'Template "{template.name}" edit coming soon!')
        return redirect('marketing_campaigns:templates_list', tenant_id=tenant_id)
    
    # Get available variables
    try:
        settings = TenantCampaignSettings.objects.get(id=1)
        available_variables = settings.get_default_variables()
    except TenantCampaignSettings.DoesNotExist:
        available_variables = {
            "phone_number": {"type": "text", "description": "Phone number"},
            "name": {"type": "text", "description": "Member name"},
        }
    
    context = {
        'template': template,
        'available_variables': available_variables,
        'page_title': 'Edit Template',
    }
    
    return render(request, 'marketing_campaigns/template_form_simple.html', context)

@login_required
def template_delete(request, tenant_id, pk):
    """Delete template"""
    
    template = get_object_or_404(MessageTemplate, pk=pk)
    
    if request.method == 'POST':
        template_name = template.name
        template.delete()
        messages.success(request, f'Template "{template_name}" deleted successfully!')
        return redirect('marketing_campaigns:templates_list', tenant_id=tenant_id)
    
    context = {'template': template}
    return render(request, 'marketing_campaigns/template_delete_simple.html', context)

@login_required
def template_preview(request, tenant_id, pk):
    """Preview template with sample data"""
    
    template = get_object_or_404(MessageTemplate, pk=pk)
    
    # Sample data for preview
    sample_data = {
        'name': 'Ahmad',
        'phone_number': '+628123456789',
        'bonus': '50000',
        'coupon_code': 'WELCOME50'
    }
    
    # Render preview
    preview_content = template.render_message(sample_data)
    
    context = {
        'template': template,
        'preview_content': preview_content,
        'sample_data': sample_data,
    }
    
    return render(request, 'marketing_campaigns/template_preview_simple.html', context)



@login_required
def audiences_list(request, tenant_id):
    """List all custom audiences"""
    
    audiences = CustomAudience.objects.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(audiences, 10)
    page_number = request.GET.get('page')
    audiences_page = paginator.get_page(page_number)
    
    context = {
        'audiences': audiences_page,
    }
    
    return render(request, 'marketing_campaigns/audiences_list_simple.html', context)

@login_required
def audience_upload(request, tenant_id):
    """Upload audience via textbox"""
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        textbox_data = request.POST.get('textbox_data', '').strip()
        
        if not name:
            messages.error(request, 'Audience name is required')
        elif not textbox_data:
            messages.error(request, 'CSV data is required')
        else:
            # Create audience
            audience = CustomAudience.objects.create(
                name=name,
                description=description,
                upload_method='textbox',
                raw_data=textbox_data,
                created_by=request.user.username if hasattr(request.user, 'username') else 'admin'
            )
            
            # Process CSV data
            audience.process_csv_data(textbox_data)
            
            if audience.processing_errors:
                messages.warning(request, f'Audience created with {len(audience.processing_errors)} errors. Check details below.')
            else:
                messages.success(request, f'Audience "{audience.name}" created successfully!')
            
            return redirect('marketing_campaigns:audience_view', tenant_id=tenant_id, pk=audience.pk)
    
    context = {
        'page_title': 'Upload Audience',
    }
    
    return render(request, 'marketing_campaigns/audience_upload_simple.html', context)

@login_required
def audience_view(request, tenant_id, pk):
    """View audience details"""
    
    audience = get_object_or_404(CustomAudience, pk=pk)
    
    # Get flagged numbers summary
    flagged_summary = [
        member for member in audience.members 
        if member.get('is_flagged', False)
    ]
    
    # Pagination for members
    paginator = Paginator(audience.members, 20)
    page_number = request.GET.get('page')
    members_page = paginator.get_page(page_number)
    
    context = {
        'audience': audience,
        'flagged_summary': flagged_summary,
        'members': members_page,
        'processing_errors': audience.processing_errors,
    }
    
    return render(request, 'marketing_campaigns/audience_view_simple.html', context)

@login_required
def audience_delete(request, tenant_id, pk):
    """Delete audience"""
    
    audience = get_object_or_404(CustomAudience, pk=pk)
    
    if request.method == 'POST':
        audience_name = audience.name
        audience.delete()
        messages.success(request, f'Audience "{audience_name}" deleted successfully!')
        return redirect('marketing_campaigns:audiences_list', tenant_id=tenant_id)
    
    context = {'audience': audience}
    return render(request, 'marketing_campaigns/audience_delete_simple.html', context)

@login_required
def audience_edit(request, tenant_id, pk):
    """Edit audience details and optionally reprocess data"""
    
    audience = get_object_or_404(CustomAudience, pk=pk)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        textbox_data = request.POST.get('textbox_data', '').strip()
        reprocess_data = request.POST.get('reprocess_data') == '1'
        
        if not name:
            messages.error(request, 'Audience name is required')
        else:
            # Update basic info
            audience.name = name
            audience.description = description
            
            # If textbox data provided and reprocess requested
            if textbox_data and reprocess_data and audience.upload_method == 'textbox':
                audience.raw_data = textbox_data
                audience.process_csv_data(textbox_data)
                
                if audience.processing_errors:
                    messages.warning(request, f'Audience updated with {len(audience.processing_errors)} processing errors.')
                else:
                    messages.success(request, f'Audience "{audience.name}" updated and data reprocessed successfully!')
            else:
                audience.save()
                messages.success(request, f'Audience "{audience.name}" updated successfully!')
            
            return redirect('marketing_campaigns:audience_view', tenant_id=tenant_id, pk=audience.pk)
    
    context = {
        'audience': audience,
        'page_title': 'Edit Audience',
    }
    
    return render(request, 'marketing_campaigns/audience_edit_simple.html', context)
