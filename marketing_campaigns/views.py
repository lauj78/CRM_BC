# marketing_campaigns/views.py - Optimized Version
import csv
import re
import json
import logging
import traceback
from io import StringIO

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse

from .models import (
    MessageTemplate, CampaignCategory, TenantCampaignSettings, 
    CustomAudience, Campaign, CampaignMessage, CampaignTarget
)
from .forms import MessageTemplateForm, CampaignForm   
from .tasks import process_campaign_messages
from whatsapp_messaging.models import WhatsAppInstance

logger = logging.getLogger(__name__)

# ================================
# Helper Functions
# ================================

def get_tenant_context(request, tenant_id):
    """Get tenant context safely with fallback"""
    if not hasattr(request, 'tenant') or not request.tenant:
        logger.warning(f"No tenant context for tenant_id: {tenant_id}")
        return None
    return request.tenant

def ensure_default_category():
    """Ensure there's always a default 'General' category"""
    default_category, created = CampaignCategory.objects.get_or_create(
        name='General',
        defaults={
            'description': 'Default category for all campaigns and templates',
            'color': '#007bff',
            'icon': 'folder',
            'is_system_default': True,
            'is_active': True
        }
    )
    return default_category

# ================================
# AJAX Endpoints
# ================================

@login_required
def get_audience_variables(request, tenant_id, pk):
    """AJAX endpoint to get variables from selected audience + sample data for preview"""
    try:
        audience = get_object_or_404(CustomAudience, pk=pk)
        
        variables = {}
        sample_data = {}
        
        if audience.members and len(audience.members) > 0:
            # Get all unique keys from member data
            all_keys = set()
            for member in audience.members:
                if isinstance(member, dict):
                    all_keys.update(member.keys())
            
            # Convert to variable format
            for key in all_keys:
                if key not in ['is_flagged', 'whatsapp_status', 'country_code']:
                    variables[key] = {
                        'type': 'text',
                        'description': f'From audience: {audience.name}'
                    }
            
            # Get sample data from first member for live preview
            first_member = audience.members[0]
            if isinstance(first_member, dict):
                sample_data = {
                    key: str(value) for key, value in first_member.items() 
                    if key not in ['is_flagged', 'whatsapp_status'] and value is not None
                }
                
                # Ensure we have basic fields
                if 'name' not in sample_data and 'phone_number' in sample_data:
                    phone = sample_data.get('phone_number', '')
                    if phone.startswith('+62'):
                        sample_data['name'] = 'Ahmad'
                    elif phone.startswith('+60'):
                        sample_data['name'] = 'Ali'
                    else:
                        sample_data['name'] = 'Member'
        
        return JsonResponse({
            'success': True,
            'variables': variables,
            'audience_name': audience.name,
            'total_numbers': audience.total_numbers,
            'sample_data': sample_data
        })
        
    except Exception as e:
        logger.error(f"Error in get_audience_variables: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def get_audience_whatsapp_stats(request, tenant_id, pk):
    """AJAX endpoint to get WhatsApp verification stats for an audience"""
    try:
        audience = get_object_or_404(CustomAudience, pk=pk)
        
        stats = {
            'total': len(audience.members) if audience.members else 0,
            'whatsapp_verified': 0,
            'non_whatsapp': 0,
            'unverified': 0,
            'flagged': 0
        }
        
        if audience.members:
            for member in audience.members:
                whatsapp_status = member.get('whatsapp_status', 'unknown')
                
                if whatsapp_status == 'confirmed':
                    stats['whatsapp_verified'] += 1
                elif whatsapp_status == 'not_available':
                    stats['non_whatsapp'] += 1
                else:
                    stats['unverified'] += 1
                
                if member.get('is_flagged', False):
                    stats['flagged'] += 1
        
        # Add percentage calculations
        if stats['total'] > 0:
            stats['whatsapp_verified_pct'] = round(stats['whatsapp_verified'] / stats['total'] * 100, 1)
            stats['non_whatsapp_pct'] = round(stats['non_whatsapp'] / stats['total'] * 100, 1)
            stats['unverified_pct'] = round(stats['unverified'] / stats['total'] * 100, 1)
        else:
            stats['whatsapp_verified_pct'] = 0
            stats['non_whatsapp_pct'] = 0
            stats['unverified_pct'] = 0
        
        return JsonResponse({
            'success': True,
            'stats': stats,
            'verification_status': audience.whatsapp_verification_status,
            'has_verification': audience.has_whatsapp_data
        })
        
    except Exception as e:
        logger.error(f"Error in get_audience_whatsapp_stats: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# ================================
# Dashboard
# ================================

@login_required
def dashboard_home(request, tenant_id):
    """Dashboard with dynamic stats"""
    context = {
        'total_templates': MessageTemplate.objects.filter(is_active=True).count(),
        'active_campaigns': Campaign.objects.filter(status='running').count(),
        'total_audiences': CustomAudience.objects.count(),
        'total_campaigns': Campaign.objects.count(),
    }
    return render(request, 'marketing_campaigns/marketing_dashboard.html', context)

# ================================
# Template Management
# ================================

@login_required
def templates_list(request, tenant_id):
    """List all message templates"""
    search_filter = request.GET.get('search')
    
    templates = MessageTemplate.objects.filter(is_active=True)
    
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
    
    context = {
        'templates': templates_page,
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
    
    # Use get_instance() method
    settings = TenantCampaignSettings.get_instance()
    available_variables = settings.get_default_variables()
    
    context = {
        'form': form,
        'available_variables': available_variables,
        'audiences': CustomAudience.objects.all(),
        'page_title': 'Create Template',
    }
    
    return render(request, 'marketing_campaigns/template_form_simple.html', context)

@login_required
def template_edit(request, tenant_id, pk):
    """Edit existing template"""
    template = get_object_or_404(MessageTemplate, pk=pk)
    
    if request.method == 'POST':
        form = MessageTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, f'Template "{template.name}" updated successfully!')
            return redirect('marketing_campaigns:templates_list', tenant_id=tenant_id)
    else:
        form = MessageTemplateForm(instance=template)
    
    settings = TenantCampaignSettings.get_instance()
    available_variables = settings.get_default_variables()
    
    context = {
        'form': form,
        'template': template,
        'available_variables': available_variables,
        'audiences': CustomAudience.objects.all(),
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
    
    sample_data = {
        'name': 'Ahmad',
        'phone_number': '+628123456789',
        'bonus': '50000',
        'coupon_code': 'WELCOME50'
    }
    
    preview_content = template.render_message(sample_data)
    
    context = {
        'template': template,
        'preview_content': preview_content,
        'sample_data': sample_data,
    }
    
    return render(request, 'marketing_campaigns/template_preview_simple.html', context)

# ================================
# Audience Management
# ================================

@login_required
def audiences_list(request, tenant_id):
    """List all custom audiences"""
    audiences = CustomAudience.objects.order_by('-created_at')
    
    paginator = Paginator(audiences, 10)
    page_number = request.GET.get('page')
    audiences_page = paginator.get_page(page_number)
    
    context = {
        'audiences': audiences_page,
    }
    
    return render(request, 'marketing_campaigns/audiences_list_simple.html', context)

@login_required
def audience_upload(request, tenant_id):
    """Upload audience via textbox with optional WhatsApp verification"""
    tenant = get_tenant_context(request, tenant_id)
    if not tenant:
        messages.error(request, 'Tenant context not available. Please contact support.')
        return redirect('marketing_campaigns:audiences_list', tenant_id=tenant_id)
    
    database_alias = tenant.db_alias
    tenant_numeric_id = getattr(tenant, 'id', None) or getattr(tenant, 'pk', None)
    
    if request.method == 'POST':
        return _handle_audience_upload_post(request, tenant_id, tenant, database_alias, tenant_numeric_id)
    else:
        return _handle_audience_upload_get(request, tenant_id, tenant, database_alias, tenant_numeric_id)

# [Keep existing helper functions _handle_audience_upload_post, _handle_audience_upload_get, 
#  _start_whatsapp_verification, _check_whatsapp_availability as they are]

@login_required
def audience_view(request, tenant_id, pk):
    """View audience details"""
    audience = get_object_or_404(CustomAudience, pk=pk)
    
    flagged_summary = [
        member for member in audience.members 
        if member.get('is_flagged', False)
    ]
    
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
    """Edit audience details"""
    audience = get_object_or_404(CustomAudience, pk=pk)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        textbox_data = request.POST.get('textbox_data', '').strip()
        reprocess_data = request.POST.get('reprocess_data') == '1'
        
        if not name:
            messages.error(request, 'Audience name is required')
        else:
            audience.name = name
            audience.description = description
            
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

# ================================
# Campaign Management
# ================================

@login_required
def campaigns_list(request, tenant_id):
    """List all campaigns"""
    campaigns = Campaign.objects.order_by('-created_at')
    
    status_filter = request.GET.get('status')
    search_filter = request.GET.get('search')
    
    if status_filter:
        campaigns = campaigns.filter(status=status_filter)
    
    if search_filter:
        campaigns = campaigns.filter(
            Q(name__icontains=search_filter) | 
            Q(description__icontains=search_filter)
        )
    
    paginator = Paginator(campaigns, 10)
    page_number = request.GET.get('page')
    campaigns_page = paginator.get_page(page_number)
    
    context = {
        'campaigns': campaigns_page,
        'status_choices': Campaign.STATUS_CHOICES,
        'current_status': status_filter,
        'search_query': search_filter,
    }
    
    return render(request, 'marketing_campaigns/campaigns_list.html', context)

@login_required
def campaign_view(request, tenant_id, pk):
    """View campaign details"""
    campaign = get_object_or_404(Campaign, pk=pk)
    
    targets = campaign.targets.all()
    
    # Get status breakdown
    status_breakdown = {}
    for status_choice in CampaignTarget.STATUS_CHOICES:
        status_key = status_choice[0]
        count = targets.filter(status=status_key).count()
        status_breakdown[status_key] = {
            'count': count,
            'label': status_choice[1]
        }
    
    # Get recent targets
    recent_targets = targets.order_by('-created_at')[:20]
    
    # Calculate progress
    total_targets = campaign.total_targeted
    sent_targets = campaign.total_sent
    progress_percentage = (sent_targets / total_targets * 100) if total_targets > 0 else 0
    
    context = {
        'campaign': campaign,
        'targets': recent_targets,
        'status_breakdown': status_breakdown,
        'campaign_messages': campaign.campaign_messages.all(),
        'progress_percentage': round(progress_percentage, 1),
    }
    
    return render(request, 'marketing_campaigns/campaign_view.html', context)

@login_required
def campaign_create(request, tenant_id):
    """Create new campaign"""
    tenant = get_tenant_context(request, tenant_id)
    if not tenant:
        messages.error(request, 'Tenant context not available.')
        return redirect('marketing_campaigns:campaigns_list', tenant_id=tenant_id)
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, tenant_id=tenant.id)
        if form.is_valid():
            try:
                with transaction.atomic():
                    campaign = form.save(commit=False)
                    campaign.created_by = request.user.username if hasattr(request.user, 'username') else 'admin'
                    
                    # Ensure instance_strategy has a default
                    if not campaign.instance_strategy:
                        campaign.instance_strategy = 'random_pool'
                    
                    
                    campaign = form.save(commit=True)
                    
                    # Generate targets
                    targets_created = campaign.generate_targets()
                    campaign.total_queued = targets_created
                    campaign.total_targeted = targets_created
                    campaign.save()
                    
                    logger.info(f"Created campaign {campaign.name} with {targets_created} targets")
                    
                    # Auto-start if requested
                    if form.cleaned_data.get('start_immediately'):
                        try:
                            task_result = process_campaign_messages.delay(campaign.pk)
                            messages.success(
                                request, 
                                f'Campaign "{campaign.name}" created with {targets_created} targets and started!'
                            )
                        except Exception as e:
                            logger.error(f"Failed to start campaign task: {str(e)}")
                            messages.warning(
                                request, 
                                f'Campaign created with {targets_created} targets, but auto-start failed.'
                            )
                    else:
                        messages.success(
                            request, 
                            f'Campaign "{campaign.name}" created with {targets_created} targets!'
                        )
                    
                    return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=campaign.pk)
                    
            except Exception as e:
                logger.error(f"Error creating campaign: {str(e)}")
                messages.error(request, f"Error creating campaign: {str(e)}")
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = CampaignForm(tenant_id=tenant.id)
    
    context = {
        'form': form,
        'total_templates': MessageTemplate.objects.filter(is_active=True).count(),
        'total_audiences': CustomAudience.objects.count(),
        'total_instances': WhatsAppInstance.objects.filter(is_active=True).count(),
        'page_title': 'Create Campaign',
    }
    
    return render(request, 'marketing_campaigns/campaign_create.html', context)

@login_required
def campaign_edit(request, tenant_id, pk):
    """Edit campaign"""
    campaign = get_object_or_404(Campaign, pk=pk)
    
    if campaign.status not in ['draft', 'scheduled']:
        messages.error(request, "Cannot edit campaign that is running or completed")
        return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)
    
    tenant = get_tenant_context(request, tenant_id)
    if not tenant:
        messages.error(request, 'Tenant context not available.')
        return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, instance=campaign, tenant_id=tenant.id)
        if form.is_valid():
            form.save()
            messages.success(request, f'Campaign "{campaign.name}" updated successfully!')
            return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)
    else:
        form = CampaignForm(instance=campaign, tenant_id=tenant.id)
    
    context = {
        'form': form,
        'campaign': campaign,
        'page_title': 'Edit Campaign',
    }
    
    return render(request, 'marketing_campaigns/campaign_create.html', context)

@login_required
def campaign_start(request, tenant_id, pk):
    """Start/resume a campaign"""
    campaign = get_object_or_404(Campaign, pk=pk)
    
    if request.method == 'POST':
        if campaign.status in ['draft', 'scheduled', 'paused']:
            # Generate targets if needed
            if campaign.targets.count() == 0:
                try:
                    targets_created = campaign.generate_targets()
                    campaign.total_targeted = targets_created
                    campaign.total_queued = targets_created
                    campaign.save()
                except Exception as e:
                    logger.error(f"Error generating targets: {str(e)}")
                    messages.error(request, f"Error preparing campaign: {str(e)}")
                    return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)
            
            # Start campaign
            campaign.status = 'running'
            campaign.start_date = timezone.now()
            campaign.save()
            
            # Start processing
            try:
                task_result = process_campaign_messages.delay(campaign.pk)
                messages.success(request, f'Campaign "{campaign.name}" started!')
            except Exception as e:
                logger.error(f"Failed to start campaign task: {str(e)}")
                messages.warning(request, f'Campaign started but background processing failed: {str(e)}')
        else:
            messages.error(request, f'Cannot start campaign with status: {campaign.get_status_display()}')
    
    return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)

@login_required
def campaign_pause(request, tenant_id, pk):
    """Pause a running campaign"""
    campaign = get_object_or_404(Campaign, pk=pk)
    
    if request.method == 'POST':
        if campaign.status == 'running':
            campaign.status = 'paused'
            campaign.save()
            messages.success(request, f'Campaign "{campaign.name}" paused!')
        else:
            messages.error(request, f'Cannot pause campaign with status: {campaign.get_status_display()}')
    
    return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)

@login_required
def campaign_delete(request, tenant_id, pk):
    """Delete campaign"""
    campaign = get_object_or_404(Campaign, pk=pk)
    
    if request.method == 'POST':
        campaign_name = campaign.name
        campaign.delete()
        messages.success(request, f'Campaign "{campaign_name}" deleted successfully!')
        return redirect('marketing_campaigns:campaigns_list', tenant_id=tenant_id)
    
    context = {'campaign': campaign}
    return render(request, 'marketing_campaigns/campaign_delete.html', context)
# At the bottom of views.py, replace the placeholder functions with these:

def _handle_audience_upload_post(request, tenant_id, tenant, database_alias, tenant_numeric_id):
    """Handle POST request for audience upload"""
    
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    textbox_data = request.POST.get('textbox_data', '').strip()
    verify_whatsapp = request.POST.get('verify_whatsapp') == '1'
    verification_speed = request.POST.get('verification_speed', 'slow')
    
    # Validate input
    if not name:
        messages.error(request, 'Audience name is required')
        return redirect('marketing_campaigns:audience_upload', tenant_id=tenant_id)
    
    if not textbox_data:
        messages.error(request, 'CSV data is required')
        return redirect('marketing_campaigns:audience_upload', tenant_id=tenant_id)
    
    try:
        # Create audience
        audience = CustomAudience.objects.create(
            name=name,
            description=description,
            upload_method='textbox',
            raw_data=textbox_data,
            created_by=request.user.username if hasattr(request.user, 'username') else 'admin'
        )
        
        logger.info(f"Created audience {audience.pk} for tenant {tenant.tenant_id}")
        
        # Process CSV data
        audience.process_csv_data(textbox_data)
        logger.info(f"Processed CSV data for audience {audience.pk}: {audience.total_numbers} numbers")
        
        # Show processing results
        if audience.processing_errors:
            messages.warning(request, 
                f'Audience created with {len(audience.processing_errors)} CSV processing errors. '
                f'Check the audience details for more information.'
            )
        else:
            messages.success(request, 
                f'Audience "{audience.name}" created successfully with {audience.total_numbers} numbers!'
            )
        
        # Handle WhatsApp verification if requested
        if verify_whatsapp and audience.total_numbers > 0:
            verification_result = _start_whatsapp_verification(
                audience, tenant_numeric_id, database_alias, verification_speed, tenant
            )
            
            if verification_result['success']:
                messages.success(request, verification_result['message'])
            else:
                messages.error(request, verification_result['message'])
        
        return redirect('marketing_campaigns:audience_view', tenant_id=tenant_id, pk=audience.pk)
        
    except Exception as e:
        logger.error(f"Error creating audience for tenant {tenant.tenant_id}: {str(e)}")
        messages.error(request, f'Error creating audience: {str(e)}')
        return redirect('marketing_campaigns:audience_upload', tenant_id=tenant_id)


def _handle_audience_upload_get(request, tenant_id, tenant, database_alias, tenant_numeric_id):
    """Handle GET request for audience upload form"""
    
    # Check WhatsApp instances availability
    whatsapp_status = _check_whatsapp_availability(tenant_numeric_id, database_alias, tenant)
    
    context = {
        'page_title': 'Upload Audience',
        'whatsapp_instances_available': whatsapp_status['available'],
        'whatsapp_instances_count': whatsapp_status['count'],
        'tenant_info': {
            'tenant_id': tenant.tenant_id,
            'database': database_alias,
            'numeric_id': tenant_numeric_id
        }
    }
    
    return render(request, 'marketing_campaigns/audience_upload_simple.html', context)


def _start_whatsapp_verification(audience, tenant_numeric_id, database_alias, verification_speed, tenant):
    """Start WhatsApp verification for an audience"""
    
    try:
        from marketing_campaigns.tasks import verify_audience_whatsapp_task
        from whatsapp_messaging.whatsapp_verification import WhatsAppVerificationService
        from django.utils import timezone
        
        # Validate tenant numeric ID
        if not tenant_numeric_id:
            logger.error(f"No numeric tenant ID found for tenant {tenant.tenant_id}")
            return {
                'success': False,
                'message': 'Tenant configuration error. Please contact support.'
            }
        
        # Initialize verification service to check availability
        verifier = WhatsAppVerificationService(tenant_id=tenant_numeric_id, database_alias=database_alias)
        available_instances = verifier.get_available_instances()
        
        if not available_instances:
            return {
                'success': False,
                'message': f'WhatsApp verification requested but no active instances available for tenant {tenant.tenant_id}.'
            }
        
        # Set verification speed delay
        delay_map = {'fast': 1, 'medium': 3, 'slow': 5}
        delay = delay_map.get(verification_speed, 3)
        
        # Update audience status with explicit database routing
        audience.whatsapp_verification_status = 'in_progress'
        audience.verification_started_at = timezone.now()
        audience.save(using=database_alias, update_fields=[
            'whatsapp_verification_status', 
            'verification_started_at'
        ])
        
        logger.info(f"Updated audience {audience.pk} status to in_progress for tenant {tenant.tenant_id}")
        
        # Start background verification task
        task_result = verify_audience_whatsapp_task.delay(
            audience_id=audience.pk,
            tenant_id=tenant_numeric_id,
            database_alias=database_alias
        )
        
        logger.info(f"Started WhatsApp verification task {task_result.id} for audience {audience.pk}, tenant {tenant.tenant_id}")
        
        estimated_time_seconds = audience.total_numbers * delay
        estimated_time_minutes = round(estimated_time_seconds / 60, 1)
        
        return {
            'success': True,
            'message': (
                f'WhatsApp verification started in background using {len(available_instances)} instances. '
                f'Estimated completion time: {estimated_time_minutes} minutes. '
                f'Check the audience view page for real-time progress updates.'
            )
        }
        
    except Exception as e:
        logger.error(f"Failed to start WhatsApp verification for audience {audience.pk}, tenant {tenant.tenant_id}: {str(e)}")
        return {
            'success': False,
            'message': f'Failed to start WhatsApp verification: {str(e)}'
        }


def _check_whatsapp_availability(tenant_numeric_id, database_alias, tenant):
    """Check WhatsApp instances availability for tenant"""
    
    try:
        # Validate tenant numeric ID
        if not tenant_numeric_id:
            logger.warning(f"No numeric tenant ID found for tenant {tenant.tenant_id}")
            return {
                'available': False,
                'count': 0,
                'instances': []
            }
        
        from whatsapp_messaging.whatsapp_verification import WhatsAppVerificationService
        
        verifier = WhatsAppVerificationService(tenant_id=tenant_numeric_id, database_alias=database_alias)
        available_instances = verifier.get_available_instances()
        
        logger.debug(f"WhatsApp instances for tenant {tenant.tenant_id}: {available_instances}")
        
        return {
            'available': len(available_instances) > 0,
            'count': len(available_instances),
            'instances': available_instances
        }
        
    except Exception as e:
        logger.warning(f"Could not check WhatsApp instances for tenant {tenant.tenant_id}: {str(e)}")
        return {
            'available': False,
            'count': 0,
            'instances': []
        }