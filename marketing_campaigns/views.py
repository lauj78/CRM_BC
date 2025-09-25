# marketing_campaigns/views.py - TEMPLATES ONLY (Phase 1)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction

from .models import MessageTemplate, CampaignCategory, TenantCampaignSettings, CustomAudience, Campaign, CampaignMessage, CampaignTarget
from .forms import MessageTemplateForm, CampaignForm   
from .tasks import process_campaign_messages
from whatsapp_messaging.models import WhatsAppInstance

import csv
from io import StringIO
import re

import logging
logger = logging.getLogger(__name__)

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


# ================================
# CAMPAIGN MANAGEMENT 
# ================================

@login_required
def campaigns_list(request, tenant_id):
    """List all campaigns"""
    
    # Filter campaigns - no direct tenant filtering since campaigns are in tenant DB
    campaigns = Campaign.objects.order_by('-created_at')
    
    # Add search and status filters
    status_filter = request.GET.get('status')
    search_filter = request.GET.get('search')
    
    if status_filter:
        campaigns = campaigns.filter(status=status_filter)
    
    if search_filter:
        campaigns = campaigns.filter(
            Q(name__icontains=search_filter) | 
            Q(description__icontains=search_filter)
        )
    
    # Pagination
    paginator = Paginator(campaigns, 10)
    page_number = request.GET.get('page')
    campaigns_page = paginator.get_page(page_number)
    
    # Get status choices for filter dropdown
    status_choices = Campaign.STATUS_CHOICES
    
    context = {
        'campaigns': campaigns_page,
        'status_choices': status_choices,
        'current_status': status_filter,
        'search_query': search_filter,
    }
    
    return render(request, 'marketing_campaigns/campaigns_list.html', context)

@login_required
def campaign_edit(request, tenant_id, pk):
    """Edit campaign (only if not started)"""
    
    campaign = get_object_or_404(Campaign, pk=pk)
    
    # Only allow editing of draft/scheduled campaigns
    if campaign.status not in ['draft', 'scheduled']:
        messages.error(request, "Cannot edit campaign that is running or completed")
        return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, instance=campaign, tenant_id=request.tenant.id)
        if form.is_valid():
            form.save()
            messages.success(request, f'Campaign "{campaign.name}" updated successfully!')
            return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)
    else:
        form = CampaignForm(instance=campaign, tenant_id=request.tenant.id)
    
    context = {
        'form': form,
        'campaign': campaign,
        'page_title': 'Edit Campaign',
    }
    
    return render(request, 'marketing_campaigns/campaign_create.html', context)

@login_required
def campaign_delete(request, tenant_id, pk):
    """Delete campaign - recommended to stop running campaigns first"""
    
    campaign = get_object_or_404(Campaign, pk=pk)
    
    if request.method == 'POST':
        campaign_name = campaign.name
        campaign_status = campaign.status
        
        # Delete the campaign (this will cascade delete targets, etc.)
        campaign.delete()
        
        messages.success(request, f'Campaign "{campaign_name}" deleted successfully!')
        return redirect('marketing_campaigns:campaigns_list', tenant_id=tenant_id)
    
    context = {'campaign': campaign}
    return render(request, 'marketing_campaigns/campaign_delete.html', context)

@login_required
def campaign_pause(request, tenant_id, pk):
    """Pause a running campaign with debug logging"""
    
    campaign = get_object_or_404(Campaign, pk=pk)
    logger.info(f"[CAMPAIGN DEBUG] Attempting to pause campaign {campaign.pk} '{campaign.name}'")
    logger.info(f"[CAMPAIGN DEBUG] Current status: {campaign.status}")
    
    if request.method == 'POST':
        if campaign.status == 'running':
            old_status = campaign.status
            campaign.status = 'paused'
            campaign.save()
            
            logger.info(f"[CAMPAIGN DEBUG] Status changed: {old_status} -> {campaign.status}")
            
            # TODO: Signal Celery tasks to pause processing
            logger.warning(f"[CAMPAIGN DEBUG] Campaign paused but NO CELERY TASK PAUSING IMPLEMENTED YET!")
            
            messages.success(request, f'Campaign "{campaign.name}" paused!')
        else:
            logger.warning(f"[CAMPAIGN DEBUG] Cannot pause campaign with status: {campaign.status}")
            messages.error(request, f'Cannot pause campaign with status: {campaign.get_status_display()}')
    
    return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)

@login_required
def campaign_view(request, tenant_id, pk):
    """View campaign details with debug info"""
    
    campaign = get_object_or_404(Campaign, pk=pk)
    logger.info(f"[CAMPAIGN DEBUG] Viewing campaign {campaign.pk} '{campaign.name}' - Status: {campaign.status}")
    
    # Get campaign targets with status breakdown
    targets = campaign.targets.all()
    logger.info(f"[CAMPAIGN DEBUG] Total targets in view: {targets.count()}")
    
    # Get status breakdown
    status_breakdown = {}
    for status_choice in CampaignTarget.STATUS_CHOICES:
        status_key = status_choice[0]
        count = targets.filter(status=status_key).count()
        status_breakdown[status_key] = {
            'count': count,
            'label': status_choice[1]
        }
        if count > 0:
            logger.info(f"[CAMPAIGN DEBUG] Status '{status_key}': {count} targets")
    
    # Get recent targets (last 20)
    recent_targets = targets.order_by('-created_at')[:20]
    
    # Get campaign messages (templates)
    campaign_messages = campaign.campaign_messages.all()
    logger.info(f"[CAMPAIGN DEBUG] Campaign uses {campaign_messages.count()} templates")
    
    # Calculate progress percentage
    total_targets = campaign.total_targeted
    sent_targets = campaign.total_sent
    progress_percentage = (sent_targets / total_targets * 100) if total_targets > 0 else 0
    
    logger.info(f"[CAMPAIGN DEBUG] Progress: {sent_targets}/{total_targets} = {progress_percentage}%")
    
    context = {
        'campaign': campaign,
        'targets': recent_targets,
        'status_breakdown': status_breakdown,
        'campaign_messages': campaign_messages,
        'progress_percentage': round(progress_percentage, 1),
    }
    
    return render(request, 'marketing_campaigns/campaign_view.html', context)

@login_required
def campaign_start(request, tenant_id, pk):
    """Start/resume a campaign and trigger message processing"""
    
    campaign = get_object_or_404(Campaign, pk=pk)
    logger.info(f"Starting campaign {campaign.pk} '{campaign.name}' - Status: {campaign.status}")
    
    if request.method == 'POST':
        if campaign.status in ['draft', 'scheduled', 'paused']:
            # Check if we have targets
            targets_count = campaign.targets.count()
            queued_count = campaign.targets.filter(status='queued').count()
            
            logger.info(f"Campaign has {targets_count} total targets, {queued_count} queued")
            
            # Regenerate targets if none exist
            if targets_count == 0:
                logger.warning("No targets found, regenerating...")
                try:
                    targets_created = campaign.generate_targets()
                    campaign.total_targeted = targets_created
                    campaign.total_queued = targets_created
                    campaign.save()
                    logger.info(f"Generated {targets_created} new targets")
                except Exception as e:
                    logger.error(f"Error generating targets: {str(e)}")
                    messages.error(request, f"Error preparing campaign: {str(e)}")
                    return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)
            
            # Update campaign status to running
            old_status = campaign.status
            campaign.status = 'running'
            campaign.start_date = timezone.now()
            campaign.save()
            
            logger.info(f"Campaign status: {old_status} → {campaign.status}")
            
            # TRIGGER CELERY TASK FOR MESSAGE PROCESSING
            try:
                task_result = process_campaign_messages.delay(campaign.pk)
                logger.info(f"Celery task started: {task_result.id}")
                messages.success(request, f'Campaign "{campaign.name}" started! Messages processing in background.')
            except Exception as e:
                logger.error(f"Failed to start Celery task: {str(e)}")
                # Campaign is still running, but warn user
                messages.warning(request, f'Campaign started but background processing failed: {str(e)}')
            
        else:
            logger.warning(f"Cannot start campaign with status: {campaign.status}")
            messages.error(request, f'Cannot start campaign with status: {campaign.get_status_display()}')
    
    return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=pk)

@login_required
def campaign_create(request, tenant_id):
    """Create new campaign - SIMPLIFIED for clean tenant architecture"""
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, tenant_id=request.tenant.id)
        if form.is_valid():
            try:
                with transaction.atomic():
                    campaign = form.save(commit=False)
                    campaign.created_by = request.user.username if hasattr(request.user, 'username') else 'admin'
                    
                    logger.info(f"[CAMPAIGN] Creating '{campaign.name}' for {tenant_id}")
                    campaign.save()
                    
                    # Save the form to create CampaignMessage relation
                    form.save()
                    
                    # Generate campaign targets from audience
                    targets_created = campaign.generate_targets()
                    campaign.total_queued = targets_created
                    campaign.total_targeted = targets_created
                    campaign.save()
                    
                    logger.info(f"[CAMPAIGN] Created {targets_created} targets for campaign {campaign.pk}")
                    
                    # Auto-start campaign if requested - SIMPLIFIED!
                    if form.cleaned_data.get('start_immediately'):
                        logger.info(f"[CAMPAIGN] Auto-starting campaign {campaign.pk}")
                        
                        try:
                            # Import here to avoid circular imports
                            from marketing_campaigns.tasks import process_campaign_messages
                            
                            # Simple task call - no tenant_db parameter needed!
                            task_result = process_campaign_messages.delay(campaign.pk)
                            logger.info(f"[CAMPAIGN] Task scheduled: {task_result.id}")
                            
                            messages.success(
                                request, 
                                f'Campaign "{campaign.name}" created with {targets_created} targets and started automatically!'
                            )
                        except Exception as task_error:
                            logger.error(f"[CAMPAIGN] Failed to start task: {str(task_error)}")
                            messages.warning(
                                request, 
                                f'Campaign "{campaign.name}" created with {targets_created} targets, but auto-start failed. You can start it manually.'
                            )
                    else:
                        messages.success(
                            request, 
                            f'Campaign "{campaign.name}" created with {targets_created} targets. Start it when ready!'
                        )
                    
                    return redirect('marketing_campaigns:campaign_view', tenant_id=tenant_id, pk=campaign.pk)
                    
            except Exception as e:
                logger.error(f"[CAMPAIGN] Error creating campaign: {str(e)}")
                messages.error(request, f"Error creating campaign: {str(e)}")
                
        else:
            logger.error(f"[CAMPAIGN] Form validation failed: {form.errors}")
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = CampaignForm(tenant_id=request.tenant.id)
    
    # Get counts for dashboard info - simplified queries
    total_templates = MessageTemplate.objects.filter(is_active=True).count()
    total_audiences = CustomAudience.objects.count()
    total_instances = WhatsAppInstance.objects.filter(is_active=True).count()
    
    context = {
        'form': form,
        'total_templates': total_templates,
        'total_audiences': total_audiences,
        'total_instances': total_instances,
        'page_title': 'Create Campaign',
    }
    
    return render(request, 'marketing_campaigns/campaign_create.html', context)