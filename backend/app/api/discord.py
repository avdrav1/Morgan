"""Discord bot integration endpoints."""
import logging
import random
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.user import User
from app.services.discord_adapter import DiscordAdapter
from app.services.intent_classifier import IntentClassifier, IntentType
from app.services.project_plan_service import ProjectPlanService
from app.services.discord_project_plan_formatter import DiscordProjectPlanFormatter
from app.services.project_plan_conversation_manager import ProjectPlanConversationManager
from app.services.milestone_generator import MilestoneGenerator
from app.services.timeline_adjuster import TimelineAdjuster
from app.services.input_validators import DateParser
from app.services.llm_service import llm_service
from app.services.project_plan_metrics import get_metrics_instance

logger = logging.getLogger(__name__)

router = APIRouter()


class DiscordMessageRequest(BaseModel):
    """Request model for sending messages through Discord."""
    discord_user_id: str
    message: str
    metadata: Dict[str, Any] = {}


class DiscordIncomingMessage(BaseModel):
    """Model for incoming messages from Discord bot."""
    discord_user_id: str
    message: str
    author_name: str = ""


class DiscordMessageResponse(BaseModel):
    """Response model for Discord message operations."""
    status: str
    message: str = ""


@router.post("/send", response_model=DiscordMessageResponse)
async def send_discord_message(
    request: DiscordMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to a Discord user.
    
    This endpoint is used by the backend to send proactive check-ins
    and responses to Discord users through the Discord bot.
    
    Args:
        request: Discord message request containing user ID and message
        db: Database session
        
    Returns:
        DiscordMessageResponse with status
        
    Raises:
        HTTPException: If message sending fails
    """
    try:
        # Verify user exists and has Discord linked
        user = db.query(User).filter(
            User.discord_user_id == request.discord_user_id
        ).first()
        
        if not user:
            logger.warning(f"User with Discord ID {request.discord_user_id} not found")
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Check if user has messaging paused
        if user.messaging_paused:
            logger.info(f"Messaging paused for user {user.id}, skipping message")
            return DiscordMessageResponse(
                status="skipped",
                message="User has messaging paused"
            )
        
        # Initialize Discord adapter and send message
        discord_adapter = DiscordAdapter()
        success = await discord_adapter.send_message_with_retry(
            user_identifier=request.discord_user_id,
            message=request.message,
            metadata=request.metadata
        )
        
        if success:
            logger.info(f"Successfully sent Discord message to user {user.id}")
            return DiscordMessageResponse(
                status="sent",
                message="Message sent successfully"
            )
        else:
            logger.error(f"Failed to send Discord message to user {user.id}")
            raise HTTPException(
                status_code=500,
                detail="Failed to send message"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending Discord message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/message", response_model=Dict[str, str])
async def handle_incoming_discord_message(
    message: DiscordIncomingMessage,
    db: Session = Depends(get_db)
):
    """
    Handle incoming messages from Discord bot.
    
    This endpoint receives messages from the Discord bot when users
    send DMs. It routes the message to the appropriate handler based
    on the user's current state.
    
    Args:
        message: Incoming Discord message
        db: Database session
        
    Returns:
        Dict with reply message for the user
        
    Raises:
        HTTPException: If message handling fails
    """
    try:
        # Find or create user
        user = db.query(User).filter(
            User.discord_user_id == message.discord_user_id
        ).first()
        
        if not user:
            # New user - start onboarding
            logger.info(f"New Discord user {message.discord_user_id}, starting onboarding")
            return {
                "reply": (
                    f"Welcome {message.author_name}! 👋\n\n"
                    "I'm your accountability assistant. I'll help you break down your goals "
                    "into actionable tasks and check in with you to keep you on track.\n\n"
                    "To get started, tell me about a project or goal you're working on!"
                )
            }
        
        # Handle message based on context
        # For now, provide a simple acknowledgment
        # TODO: Integrate with ConversationManager and check-in response handler
        
        logger.info(f"Received message from user {user.id}: {message.message}")
        
        return {
            "reply": (
                "Thanks for your message! I'm processing it and will respond shortly. "
                "This feature is still being enhanced."
            )
        }
    
    except Exception as e:
        logger.error(f"Error handling incoming Discord message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/start")
async def start_discord_onboarding(
    request: DiscordIncomingMessage,
    db: Session = Depends(get_db)
):
    """
    Start onboarding process for a Discord user.
    
    Args:
        request: Discord user information
        db: Database session
        
    Returns:
        Dict with welcome message
    """
    try:
        # Check if user already exists
        user = db.query(User).filter(
            User.discord_user_id == request.discord_user_id
        ).first()
        
        if user:
            return {
                "message": (
                    f"Welcome back, {user.full_name or request.author_name}! 👋\n\n"
                    "I'm ready to help you stay on track with your projects."
                )
            }
        
        # New user
        return {
            "message": (
                f"Welcome {request.author_name}! 👋\n\n"
                "I'm your accountability assistant. Let's get started!\n\n"
                "Tell me about a project or goal you're working on, and I'll help you "
                "break it down into manageable tasks."
            )
        }
    
    except Exception as e:
        logger.error(f"Error starting Discord onboarding: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/status/{discord_user_id}")
async def get_discord_user_status(
    discord_user_id: str,
    db: Session = Depends(get_db)
):
    """
    Get status for a Discord user.
    
    Args:
        discord_user_id: Discord user ID
        db: Database session
        
    Returns:
        Dict with user status information
    """
    try:
        user = db.query(User).filter(
            User.discord_user_id == discord_user_id
        ).first()
        
        if not user:
            return {
                "status": "No account found. Use !start to get started!"
            }
        
        # Get active projects
        active_projects = [p for p in user.projects if p.status == "active"]
        
        if not active_projects:
            return {
                "status": (
                    "You don't have any active projects yet.\n"
                    "Tell me about a goal you're working on to get started!"
                )
            }
        
        # Build status message
        status_lines = ["📊 Your Active Projects:\n"]
        for project in active_projects:
            incomplete_tasks = [t for t in project.tasks if t.status != "completed"]
            status_lines.append(
                f"• **{project.name}** - {len(incomplete_tasks)} tasks remaining"
            )
        
        return {
            "status": "\n".join(status_lines)
        }
    
    except Exception as e:
        logger.error(f"Error getting Discord user status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


class ProjectPlanMessageRequest(BaseModel):
    """Request model for project plan messages."""
    user_id: str
    discord_user_id: str
    message: str


@router.post("/project-plan/message")
async def handle_project_plan_message(
    request: ProjectPlanMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Handle incoming project plan messages from Discord bot.
    
    This endpoint processes messages about project plans, classifies intent,
    and executes the appropriate action. Handles multi-project scenarios.
    
    Args:
        request: Project plan message request
        db: Database session
        
    Returns:
        Dict with reply message for the user
        
    Raises:
        HTTPException: If message handling fails
        
    Validates: Requirements 1.1, 2.1, 3.1, 6.1, 7.1, 7.2, 7.3
    """
    try:
        # Log incoming request
        logger.info(
            "Project plan message received",
            extra={
                'extra_fields': {
                    'event': 'project_plan_message_received',
                    'user_id': request.user_id,
                    'discord_user_id': request.discord_user_id,
                    'message_length': len(request.message)
                }
            }
        )
        
        # Parse user_id
        try:
            user_uuid = UUID(request.user_id)
        except ValueError:
            logger.warning(
                "Invalid user_id format",
                extra={
                    'extra_fields': {
                        'event': 'invalid_user_id',
                        'user_id': request.user_id
                    }
                }
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid user_id format"
            )
        
        # Verify user exists
        user = db.query(User).filter(User.id == user_uuid).first()
        if not user:
            logger.warning(
                "User not found",
                extra={
                    'extra_fields': {
                        'event': 'user_not_found',
                        'user_id': str(user_uuid)
                    }
                }
            )
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Initialize services
        project_plan_service = ProjectPlanService(db)
        intent_classifier = IntentClassifier(llm_service)
        formatter = DiscordProjectPlanFormatter()
        conversation_manager = ProjectPlanConversationManager(db)
        milestone_generator = MilestoneGenerator(db, llm_service)
        metrics = get_metrics_instance(db)
        
        # Get all projects for the user
        all_projects = project_plan_service.get_all_projects(user_uuid)
        
        if not all_projects:
            logger.warning(f"No project found for user {user_uuid}")
            raise HTTPException(
                status_code=404,
                detail="No project found"
            )
        
        # Determine which project to use
        project = None
        project_id = None
        
        # Check if user has multiple projects
        if len(all_projects) > 1:
            # Try to extract project reference from message
            project = _extract_project_from_message(
                message=request.message,
                projects=all_projects,
                project_plan_service=project_plan_service,
                user_uuid=user_uuid
            )
            
            if not project:
                # Ask user to specify which project
                project_list = "\n".join([
                    f"{i+1}. **{p.title}**"
                    for i, p in enumerate(all_projects)
                ])
                
                return {
                    "reply": (
                        "You have multiple projects. Which one would you like to work with?\n\n"
                        f"{project_list}\n\n"
                        "Please specify the project name or number, or say 'current project' for your most recent one."
                    )
                }
        else:
            # Only one project, use it
            project = all_projects[0]
        
        project_id = project.id
        
        # Get project plan
        project_plan = await project_plan_service.get_project_plan(user_uuid, project_id)
        
        if not project_plan:
            logger.warning(f"No project found for user {user_uuid}")
            raise HTTPException(
                status_code=404,
                detail="No project found"
            )
        
        project = project_plan['project']
        milestones = project_plan['milestones']
        
        # Get conversation history
        conversation_history = conversation_manager.get_conversation_history(
            user_uuid,
            project.id
        )
        
        # Build project context for intent classification
        project_context = {
            'project_id': str(project.id),
            'project_name': project.title,
            'project_goal': project.goal,
            'deadline': project.target_completion_date.isoformat() if project.target_completion_date else None,
            'has_multiple_projects': len(all_projects) > 1
        }
        
        # Classify intent
        intent = await intent_classifier.classify_intent(
            message=request.message,
            conversation_history=conversation_history,
            project_context=project_context
        )
        
        # Record intent in metrics
        metrics.record_intent(
            intent_type=intent.type.value,
            user_id=user_uuid,
            project_id=project.id
        )
        
        # Add user message to conversation history
        conversation_manager.add_message(
            user_id=user_uuid,
            project_id=project.id,
            role="user",
            content=request.message,
            metadata={"intent": intent.type.value, "confidence": intent.confidence}
        )
        
        # Update last intent
        conversation_manager.set_last_intent(
            user_id=user_uuid,
            project_id=project.id,
            intent=intent.type.value
        )
        
        # Record conversation activity
        metrics.record_conversation_activity(
            user_id=user_uuid,
            project_id=project.id,
            message_count=1
        )
        
        # Route based on intent
        reply = await _handle_intent(
            intent=intent,
            project=project,
            milestones=milestones,
            user_uuid=user_uuid,
            project_plan_service=project_plan_service,
            formatter=formatter,
            conversation_manager=conversation_manager,
            milestone_generator=milestone_generator,
            db=db
        )
        
        # Add assistant response to conversation history
        conversation_manager.add_message(
            user_id=user_uuid,
            project_id=project.id,
            role="assistant",
            content=reply
        )
        
        logger.info(
            "Project plan message handled successfully",
            extra={
                'extra_fields': {
                    'event': 'project_plan_message_handled',
                    'user_id': str(user_uuid),
                    'project_id': str(project.id),
                    'intent_type': intent.type.value,
                    'intent_confidence': intent.confidence,
                    'reply_length': len(reply)
                }
            }
        )
        
        return {"reply": reply}
    
    except HTTPException:
        raise
    except Exception as e:
        # Record error in metrics
        try:
            user_uuid = UUID(request.user_id)
            metrics = get_metrics_instance(db)
            metrics.record_error(
                intent_type='unknown',
                error_type=type(e).__name__,
                user_id=user_uuid
            )
        except:
            pass  # Don't let metrics recording fail the error handling
        
        logger.error(
            "Error handling project plan message",
            extra={
                'extra_fields': {
                    'event': 'project_plan_message_error',
                    'user_id': request.user_id,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


def _extract_project_from_message(
    message: str,
    projects: List[Any],
    project_plan_service: ProjectPlanService,
    user_uuid: UUID
) -> Optional[Any]:
    """
    Extract project reference from user message.
    
    Handles references like:
    - "current project" or "active project" -> most recently updated
    - Project name (exact or partial match)
    - Project number (1-indexed)
    
    Args:
        message: User's message
        projects: List of user's projects
        project_plan_service: Project plan service instance
        user_uuid: User UUID
        
    Returns:
        Project object if found, None otherwise
        
    Validates: Requirements 7.1, 7.2, 7.3
    """
    message_lower = message.lower()
    
    # Check for "current project" or "active project" references
    if any(phrase in message_lower for phrase in ['current project', 'active project', 'my project', 'this project']):
        # Return most recently updated project
        return projects[0] if projects else None
    
    # Try to find project by name (exact or partial match)
    for project in projects:
        if project.title.lower() in message_lower:
            logger.info(f"Found project by name match: {project.title}")
            return project
    
    # Try to find by number (e.g., "project 1", "project 2")
    import re
    number_match = re.search(r'project\s+(\d+)', message_lower)
    if number_match:
        try:
            project_index = int(number_match.group(1)) - 1
            if 0 <= project_index < len(projects):
                logger.info(f"Found project by number: {project_index + 1}")
                return projects[project_index]
        except (ValueError, IndexError):
            pass
    
    # Try standalone number at start of message
    number_match = re.match(r'^(\d+)', message.strip())
    if number_match:
        try:
            project_index = int(number_match.group(1)) - 1
            if 0 <= project_index < len(projects):
                logger.info(f"Found project by standalone number: {project_index + 1}")
                return projects[project_index]
        except (ValueError, IndexError):
            pass
    
    return None


async def _handle_view_plan(
    project: Any,
    milestones: List[Any],
    formatter: DiscordProjectPlanFormatter,
    milestone_generator: MilestoneGenerator
) -> str:
    """
    Handle VIEW_PLAN intent.
    
    Retrieves project and milestones, generates initial milestones if none exist,
    and formats the response for Discord. Includes project name in response.
    
    Args:
        project: Project object
        milestones: List of milestones
        formatter: Discord formatter instance
        milestone_generator: Milestone generator instance
        
    Returns:
        Formatted project plan message
        
    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 7.4
    """
    logger.info(f"Handling VIEW_PLAN for project {project.id}")
    
    # Generate initial milestones if none exist
    if not milestones:
        logger.info(f"Generating initial milestones for project {project.id}")
        milestones = await milestone_generator.generate_milestones(project)
    
    # Format and return the project plan (includes project name in header)
    messages = formatter.format_project_plan(project, milestones)
    return "\n\n".join(messages)


async def _handle_edit_deadline(
    intent: Any,
    project: Any,
    milestones: List[Any],
    user_uuid: UUID,
    project_plan_service: ProjectPlanService,
    formatter: DiscordProjectPlanFormatter,
    conversation_manager: ProjectPlanConversationManager,
    db: Session
) -> str:
    """
    Handle EDIT_DEADLINE intent.
    
    Parses new deadline, calculates timeline adjustments, requests user confirmation,
    and applies changes after confirmation.
    
    Args:
        intent: Classified intent with parameters
        project: Project object
        milestones: List of milestones
        user_uuid: User UUID
        project_plan_service: Project plan service instance
        formatter: Discord formatter instance
        conversation_manager: Conversation manager instance
        db: Database session
        
    Returns:
        Response message with deadline change confirmation or request
        
    Validates: Requirements 3.1, 4.1, 4.2, 4.3, 4.5
    """
    from datetime import datetime
    from app.services.timeline_adjuster import TimelineAdjuster
    
    logger.info(f"Handling EDIT_DEADLINE for project {project.id}")
    
    # Check if there's a pending confirmation
    pending = conversation_manager.get_pending_confirmation(user_uuid, project.id)
    
    if pending and pending.get('type') == 'deadline_change':
        # User is confirming or rejecting the change
        user_message = intent.parameters.get('confirmation', '').lower()
        
        if any(word in user_message for word in ['yes', 'confirm', 'ok', 'sure', 'proceed']):
            # Apply the deadline change
            new_deadline = datetime.fromisoformat(pending['new_deadline'])
            adjusted_milestones = pending.get('adjusted_milestones', [])
            
            # Update project deadline
            project.target_completion_date = new_deadline
            db.commit()
            
            # Update milestone dates if adjustments were proposed
            if adjusted_milestones:
                for adjustment in adjusted_milestones:
                    milestone_id = UUID(adjustment['milestone_id'])
                    new_date = datetime.fromisoformat(adjustment['new_date'])
                    await project_plan_service.update_milestone(
                        milestone_id=milestone_id,
                        updates={'target_date': new_date}
                    )
            
            # Clear pending confirmation
            conversation_manager.clear_pending_confirmation(user_uuid, project.id)
            
            logger.info(f"Deadline updated for project {project.id}")
            
            return (
                f"✅ Great! I've updated the deadline for **{project.title}** to **{new_deadline.strftime('%B %d, %Y')}**.\n\n"
                + (f"I've also adjusted {len(adjusted_milestones)} milestone(s) to fit the new timeline.\n\n" if adjusted_milestones else "")
                + "Your updated plan:\n\n"
                + formatter.format_timeline_summary(project, milestones)
            )
        else:
            # User rejected the change
            conversation_manager.clear_pending_confirmation(user_uuid, project.id)
            return "No problem! I've kept your original deadline. Let me know if you'd like to make any other changes."
    
    # Parse new deadline from parameters
    new_deadline_str = intent.parameters.get('new_deadline')
    
    if not new_deadline_str:
        return (
            "I understand you want to change your deadline, but I need to know the new date. "
            "Could you tell me when you'd like your new deadline to be? "
            "For example: 'Change my deadline to December 31st' or 'Move my deadline to next Friday'"
        )
    
    # Parse the date
    parse_result = DateParser.parse(new_deadline_str)
    
    if not parse_result.is_valid:
        logger.warning(f"Failed to parse deadline: {new_deadline_str}")
        return (
            f"I couldn't understand the date '{new_deadline_str}'. "
            "Could you provide it in a clearer format? For example: 'December 31, 2024' or '2024-12-31'"
        )
    
    new_deadline = parse_result.value
    
    # Calculate timeline adjustments
    timeline_adjuster = TimelineAdjuster(db)
    
    if milestones:
        adjusted_milestones = await timeline_adjuster.adjust_milestone_dates(
            project=project,
            new_deadline=new_deadline,
            milestones=milestones
        )
        
        # Check if deadline is being shortened significantly
        old_deadline = project.target_completion_date
        if old_deadline and new_deadline < old_deadline:
            days_shortened = (old_deadline - new_deadline).days
            
            if days_shortened > 7:  # Significant shortening
                # Store pending confirmation
                pending_data = {
                    'type': 'deadline_change',
                    'new_deadline': new_deadline.isoformat(),
                    'old_deadline': old_deadline.isoformat(),
                    'adjusted_milestones': [
                        {
                            'milestone_id': str(m.id),
                            'milestone_title': m.title,
                            'old_date': m.target_date.isoformat(),
                            'new_date': adj_date.isoformat()
                        }
                        for m, adj_date in zip(milestones, adjusted_milestones)
                    ]
                }
                conversation_manager.set_pending_confirmation(user_uuid, project.id, pending_data)
                
                # Build confirmation message
                changes_text = "\n".join([
                    f"• **{adj['milestone_title']}**: {datetime.fromisoformat(adj['old_date']).strftime('%b %d')} → {datetime.fromisoformat(adj['new_date']).strftime('%b %d')}"
                    for adj in pending_data['adjusted_milestones']
                ])
                
                return (
                    f"⚠️ You're shortening your deadline by **{days_shortened} days** "
                    f"(from {old_deadline.strftime('%B %d')} to {new_deadline.strftime('%B %d')}).\n\n"
                    f"This will adjust your milestones:\n\n{changes_text}\n\n"
                    "This is a tight timeline! Are you sure you want to proceed? (yes/no)"
                )
        
        # Store pending confirmation for normal changes
        pending_data = {
            'type': 'deadline_change',
            'new_deadline': new_deadline.isoformat(),
            'old_deadline': old_deadline.isoformat() if old_deadline else None,
            'adjusted_milestones': [
                {
                    'milestone_id': str(m.id),
                    'milestone_title': m.title,
                    'old_date': m.target_date.isoformat(),
                    'new_date': adj_date.isoformat()
                }
                for m, adj_date in zip(milestones, adjusted_milestones)
            ]
        }
        conversation_manager.set_pending_confirmation(user_uuid, project.id, pending_data)
        
        # Build confirmation message
        changes_text = "\n".join([
            f"• **{adj['milestone_title']}**: {datetime.fromisoformat(adj['old_date']).strftime('%b %d')} → {datetime.fromisoformat(adj['new_date']).strftime('%b %d')}"
            for adj in pending_data['adjusted_milestones']
        ])
        
        return (
            f"I can update your deadline to **{new_deadline.strftime('%B %d, %Y')}**.\n\n"
            f"This will adjust your milestones:\n\n{changes_text}\n\n"
            "Does this look good? (yes/no)"
        )
    else:
        # No milestones, just update the deadline
        project.target_completion_date = new_deadline
        db.commit()
        
        return f"✅ I've updated your project deadline to **{new_deadline.strftime('%B %d, %Y')}**!"


async def _handle_add_milestone(
    intent: Any,
    project: Any,
    user_uuid: UUID,
    project_plan_service: ProjectPlanService,
    formatter: DiscordProjectPlanFormatter,
    db: Session
) -> str:
    """
    Handle ADD_MILESTONE intent.
    
    Extracts milestone details, validates date is before deadline,
    adds milestone to database, and confirms addition.
    
    Args:
        intent: Classified intent with parameters
        project: Project object
        user_uuid: User UUID
        project_plan_service: Project plan service instance
        formatter: Discord formatter instance
        db: Database session
        
    Returns:
        Confirmation message for milestone addition
        
    Validates: Requirements 3.3
    """
    from datetime import datetime
    
    logger.info(f"Handling ADD_MILESTONE for project {project.id}")
    
    # Extract milestone details
    milestone_title = intent.parameters.get('milestone_title')
    target_date_str = intent.parameters.get('target_date')
    
    if not milestone_title:
        return (
            "I understand you want to add a milestone, but I need to know what it's called. "
            "What would you like to name this milestone?"
        )
    
    if not target_date_str:
        return (
            f"Great! I'll add a milestone called **{milestone_title}**. "
            "When should this milestone be completed? Please provide a date."
        )
    
    # Parse target date
    parse_result = DateParser.parse(target_date_str)
    
    if not parse_result.is_valid:
        logger.warning(f"Failed to parse milestone date: {target_date_str}")
        return (
            f"I couldn't understand the date '{target_date_str}'. "
            "Could you provide it in a clearer format? For example: 'December 15' or '2024-12-15'"
        )
    
    target_date = parse_result.value
    
    # Validate milestone date is before project deadline
    if project.target_completion_date and target_date > project.target_completion_date:
        return (
            f"⚠️ The milestone date ({target_date.strftime('%B %d, %Y')}) is after your project deadline "
            f"({project.target_completion_date.strftime('%B %d, %Y')}). "
            "Milestones should be completed before the project deadline. "
            "Would you like to choose a different date or extend your project deadline?"
        )
    
    # Add milestone
    from app.models.milestone import Milestone
    
    # Get the highest order number
    existing_milestones = db.query(Milestone).filter(
        Milestone.project_id == project.id
    ).all()
    max_order = max([m.order for m in existing_milestones], default=0)
    
    new_milestone = Milestone(
        project_id=project.id,
        title=milestone_title,
        target_date=target_date,
        status='PENDING',
        order=max_order + 1
    )
    
    db.add(new_milestone)
    db.commit()
    db.refresh(new_milestone)
    
    logger.info(f"Added milestone {new_milestone.id} to project {project.id}")
    
    # Format the new milestone
    milestone_text = formatter.format_milestone(new_milestone)
    
    return (
        f"✅ I've added a new milestone to **{project.title}**:\n\n"
        f"{milestone_text}\n\n"
        "Your project plan has been updated!"
    )


async def _handle_edit_milestone(
    intent: Any,
    project: Any,
    milestones: List[Any],
    user_uuid: UUID,
    project_plan_service: ProjectPlanService,
    formatter: DiscordProjectPlanFormatter,
    db: Session
) -> str:
    """
    Handle EDIT_MILESTONE intent.
    
    Identifies which milestone to edit, extracts changes,
    updates milestone in database, and confirms changes.
    
    Args:
        intent: Classified intent with parameters
        project: Project object
        milestones: List of milestones
        user_uuid: User UUID
        project_plan_service: Project plan service instance
        formatter: Discord formatter instance
        db: Database session
        
    Returns:
        Confirmation message for milestone edit
        
    Validates: Requirements 3.2
    """
    from datetime import datetime
    
    logger.info(f"Handling EDIT_MILESTONE for project {project.id}")
    
    # Extract milestone identifier
    milestone_identifier = intent.parameters.get('milestone_identifier')
    
    if not milestone_identifier:
        # List available milestones
        milestone_list = "\n".join([
            f"{i+1}. {m.title}"
            for i, m in enumerate(milestones)
        ])
        return (
            "Which milestone would you like to edit? Here are your milestones:\n\n"
            f"{milestone_list}\n\n"
            "Please specify which one you'd like to change."
        )
    
    # Find the milestone
    target_milestone = None
    
    # Try to match by title (case-insensitive)
    for milestone in milestones:
        if milestone_identifier.lower() in milestone.title.lower():
            target_milestone = milestone
            break
    
    # Try to match by number (1-indexed)
    if not target_milestone:
        try:
            milestone_index = int(milestone_identifier) - 1
            if 0 <= milestone_index < len(milestones):
                target_milestone = milestones[milestone_index]
        except ValueError:
            pass
    
    if not target_milestone:
        milestone_list = "\n".join([
            f"{i+1}. {m.title}"
            for i, m in enumerate(milestones)
        ])
        return (
            f"I couldn't find a milestone matching '{milestone_identifier}'. "
            "Here are your milestones:\n\n"
            f"{milestone_list}\n\n"
            "Please specify which one you'd like to edit."
        )
    
    # Extract changes
    new_title = intent.parameters.get('new_title')
    new_date_str = intent.parameters.get('new_date')
    
    if not new_title and not new_date_str:
        return (
            f"What would you like to change about **{target_milestone.title}**? "
            "You can change the title or the date."
        )
    
    # Apply changes
    updates = {}
    changes_description = []
    
    if new_title:
        updates['title'] = new_title
        changes_description.append(f"title to **{new_title}**")
    
    if new_date_str:
        parse_result = DateParser.parse(new_date_str)
        
        if not parse_result.is_valid:
            logger.warning(f"Failed to parse new date: {new_date_str}")
            return (
                f"I couldn't understand the date '{new_date_str}'. "
                "Could you provide it in a clearer format?"
            )
        
        new_date = parse_result.value
        updates['target_date'] = new_date
        changes_description.append(f"date to **{new_date.strftime('%B %d, %Y')}**")
    
    # Update the milestone
    await project_plan_service.update_milestone(
        milestone_id=target_milestone.id,
        updates=updates
    )
    
    logger.info(f"Updated milestone {target_milestone.id}")
    
    changes_text = " and ".join(changes_description)
    
    return (
        f"✅ I've updated **{target_milestone.title}** in **{project.title}** - changed {changes_text}.\n\n"
        "Your project plan has been updated!"
    )


async def _handle_delete_milestone(
    intent: Any,
    project: Any,
    milestones: List[Any],
    user_uuid: UUID,
    project_plan_service: ProjectPlanService,
    conversation_manager: ProjectPlanConversationManager,
    db: Session
) -> str:
    """
    Handle DELETE_MILESTONE intent.
    
    Identifies which milestone to delete, requests confirmation,
    deletes milestone after confirmation, and confirms deletion.
    
    Args:
        intent: Classified intent with parameters
        project: Project object
        milestones: List of milestones
        user_uuid: User UUID
        project_plan_service: Project plan service instance
        conversation_manager: Conversation manager instance
        db: Database session
        
    Returns:
        Confirmation request or deletion confirmation message
        
    Validates: Requirements 3.4
    """
    logger.info(f"Handling DELETE_MILESTONE for project {project.id}")
    
    # Check if there's a pending confirmation
    pending = conversation_manager.get_pending_confirmation(user_uuid, project.id)
    
    if pending and pending.get('type') == 'milestone_deletion':
        # User is confirming or rejecting the deletion
        user_message = intent.parameters.get('confirmation', '').lower()
        
        if any(word in user_message for word in ['yes', 'confirm', 'delete', 'remove']):
            # Delete the milestone
            milestone_id = UUID(pending['milestone_id'])
            milestone_title = pending['milestone_title']
            
            from app.models.milestone import Milestone
            milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
            
            if milestone:
                db.delete(milestone)
                db.commit()
                
                logger.info(f"Deleted milestone {milestone_id}")
                
                conversation_manager.clear_pending_confirmation(user_uuid, project.id)
                
                return f"✅ I've removed **{milestone_title}** from **{project.title}**."
            else:
                conversation_manager.clear_pending_confirmation(user_uuid, project.id)
                return "That milestone no longer exists."
        else:
            # User rejected the deletion
            conversation_manager.clear_pending_confirmation(user_uuid, project.id)
            return "No problem! I've kept the milestone in your plan."
    
    # Extract milestone identifier
    milestone_identifier = intent.parameters.get('milestone_identifier')
    
    if not milestone_identifier:
        # List available milestones
        milestone_list = "\n".join([
            f"{i+1}. {m.title}"
            for i, m in enumerate(milestones)
        ])
        return (
            "Which milestone would you like to remove? Here are your milestones:\n\n"
            f"{milestone_list}\n\n"
            "Please specify which one you'd like to delete."
        )
    
    # Find the milestone
    target_milestone = None
    
    # Try to match by title (case-insensitive)
    for milestone in milestones:
        if milestone_identifier.lower() in milestone.title.lower():
            target_milestone = milestone
            break
    
    # Try to match by number (1-indexed)
    if not target_milestone:
        try:
            milestone_index = int(milestone_identifier) - 1
            if 0 <= milestone_index < len(milestones):
                target_milestone = milestones[milestone_index]
        except ValueError:
            pass
    
    if not target_milestone:
        milestone_list = "\n".join([
            f"{i+1}. {m.title}"
            for i, m in enumerate(milestones)
        ])
        return (
            f"I couldn't find a milestone matching '{milestone_identifier}'. "
            "Here are your milestones:\n\n"
            f"{milestone_list}\n\n"
            "Please specify which one you'd like to delete."
        )
    
    # Request confirmation
    pending_data = {
        'type': 'milestone_deletion',
        'milestone_id': str(target_milestone.id),
        'milestone_title': target_milestone.title
    }
    conversation_manager.set_pending_confirmation(user_uuid, project.id, pending_data)
    
    return (
        f"Are you sure you want to delete **{target_milestone.title}**? "
        "This action cannot be undone. (yes/no)"
    )


async def _handle_mark_complete(
    intent: Any,
    project: Any,
    milestones: List[Any],
    user_uuid: UUID,
    project_plan_service: ProjectPlanService,
    formatter: DiscordProjectPlanFormatter,
    db: Session
) -> str:
    """
    Handle MARK_COMPLETE intent.
    
    Identifies which milestone was completed, marks it as complete with timestamp,
    sends celebration message, and shows next upcoming milestone.
    
    Args:
        intent: Classified intent with parameters
        project: Project object
        milestones: List of milestones
        user_uuid: User UUID
        project_plan_service: Project plan service instance
        formatter: Discord formatter instance
        db: Database session
        
    Returns:
        Celebration message with next milestone
        
    Validates: Requirements 5.1, 5.2, 5.3, 5.4
    """
    from datetime import datetime
    
    logger.info(f"Handling MARK_COMPLETE for project {project.id}")
    
    # Extract milestone identifier
    milestone_identifier = intent.parameters.get('milestone_identifier')
    
    if not milestone_identifier:
        # List incomplete milestones
        incomplete_milestones = [m for m in milestones if m.status != 'COMPLETED']
        
        if not incomplete_milestones:
            return "🎉 Congratulations! You've completed all your milestones!"
        
        milestone_list = "\n".join([
            f"{i+1}. {m.title}"
            for i, m in enumerate(incomplete_milestones)
        ])
        return (
            "Which milestone did you complete? Here are your pending milestones:\n\n"
            f"{milestone_list}\n\n"
            "Please specify which one you completed."
        )
    
    # Find the milestone
    target_milestone = None
    
    # Try to match by title (case-insensitive)
    for milestone in milestones:
        if milestone_identifier.lower() in milestone.title.lower():
            target_milestone = milestone
            break
    
    # Try to match by number (1-indexed)
    if not target_milestone:
        try:
            milestone_index = int(milestone_identifier) - 1
            if 0 <= milestone_index < len(milestones):
                target_milestone = milestones[milestone_index]
        except ValueError:
            pass
    
    if not target_milestone:
        incomplete_milestones = [m for m in milestones if m.status != 'COMPLETED']
        milestone_list = "\n".join([
            f"{i+1}. {m.title}"
            for i, m in enumerate(incomplete_milestones)
        ])
        return (
            f"I couldn't find a milestone matching '{milestone_identifier}'. "
            "Here are your pending milestones:\n\n"
            f"{milestone_list}\n\n"
            "Please specify which one you completed."
        )
    
    # Check if already completed
    if target_milestone.status == 'COMPLETED':
        return f"**{target_milestone.title}** is already marked as complete! 🎉"
    
    # Mark as complete
    await project_plan_service.mark_milestone_complete(target_milestone.id)
    
    logger.info(f"Marked milestone {target_milestone.id} as complete")
    
    # Build celebration message
    celebration_messages = [
        "🎉 Awesome work!",
        "🌟 Fantastic!",
        "🚀 Great job!",
        "💪 Well done!",
        "✨ Excellent!"
    ]
    
    import random
    celebration = random.choice(celebration_messages)
    
    response = f"{celebration} You've completed **{target_milestone.title}** in **{project.title}**!\n\n"
    
    # Find next upcoming milestone
    incomplete_milestones = [
        m for m in milestones 
        if m.status != 'COMPLETED' and m.id != target_milestone.id
    ]
    
    if incomplete_milestones:
        # Sort by target date
        incomplete_milestones.sort(key=lambda m: m.target_date)
        next_milestone = incomplete_milestones[0]
        
        # Calculate days until next milestone
        days_until = (next_milestone.target_date - datetime.now()).days
        
        time_text = ""
        if days_until < 0:
            time_text = f"(was due {abs(days_until)} days ago)"
        elif days_until == 0:
            time_text = "(due today!)"
        elif days_until == 1:
            time_text = "(due tomorrow)"
        else:
            time_text = f"(in {days_until} days)"
        
        response += (
            f"Next up: **{next_milestone.title}** "
            f"{time_text}\n\n"
            "Keep up the momentum! 💪"
        )
    else:
        # All milestones complete!
        response += (
            "🎊 **Congratulations!** You've completed all your milestones!\n\n"
            "You're crushing it! Time to celebrate your achievement! 🎉"
        )
    
    return response


async def _handle_ask_question(
    intent: Any,
    project: Any,
    milestones: List[Any],
    formatter: DiscordProjectPlanFormatter,
    user: Any
) -> str:
    """
    Handle ASK_QUESTION intent.
    
    Uses LLM with project context to answer question,
    formats response in user's preferred tone, and handles follow-up questions.
    
    Args:
        intent: Classified intent with parameters
        project: Project object
        milestones: List of milestones
        formatter: Discord formatter instance
        user: User object
        
    Returns:
        Answer to the user's question
        
    Validates: Requirements 2.1, 2.2, 2.5
    """
    from app.services.llm_service import llm_service
    
    logger.info(f"Handling ASK_QUESTION for project {project.id}")
    
    # Build context for LLM
    context = f"""Project: {project.title}
Goal: {project.goal}
Deadline: {project.target_completion_date.strftime('%Y-%m-%d') if project.target_completion_date else 'Not set'}

Milestones:
"""
    
    for i, milestone in enumerate(milestones, 1):
        status_emoji = formatter.STATUS_EMOJIS.get(milestone.status, "")
        status_text = "Completed" if milestone.status == "COMPLETED" else "Pending"
        context += f"{i}. {status_emoji} {milestone.title} - {milestone.target_date.strftime('%Y-%m-%d')} ({status_text})\n"
    
    # Get user's preferred tone
    tone = user.preferred_tone if user and user.preferred_tone else "friendly and supportive"
    
    # Extract the question
    question = intent.parameters.get('question', intent.parameters.get('message', 'No specific question'))
    
    prompt = f"""{context}

User's preferred communication style: {tone}

User question: {question}

Provide a helpful answer based on the project context above. Use the user's preferred communication style. Be concise and friendly."""
    
    try:
        response = llm_service.client.messages.create(
            model=llm_service.model,
            max_tokens=500,
            system="You are Morgan, a helpful accountability assistant. Answer questions about the user's project plan accurately and supportively.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    except Exception as e:
        logger.error(f"Failed to generate answer: {str(e)}", exc_info=True)
        return (
            "I'm having trouble generating an answer right now. "
            "Could you try rephrasing your question?"
        )


def _handle_unclear() -> str:
    """
    Handle UNCLEAR intent.
    
    Asks clarifying questions and provides examples of what user can do.
    
    Returns:
        Help message with available actions
        
    Validates: Requirements 2.3, 6.4
    """
    return (
        "I'm not sure what you'd like to do. Here are some things I can help with:\n\n"
        "• **View your project plan** - Just ask 'show me my plan'\n"
        "• **Answer questions** - Ask me anything about your project\n"
        "• **Edit your deadline** - Say 'change my deadline to [date]'\n"
        "• **Add a milestone** - Say 'add a milestone called [name] for [date]'\n"
        "• **Edit a milestone** - Say 'change [milestone] to [new date/name]'\n"
        "• **Delete a milestone** - Say 'remove [milestone]'\n"
        "• **Mark complete** - Say 'I completed [milestone]'\n\n"
        "What would you like to do?"
    )


@router.get("/project-plan/metrics")
async def get_project_plan_metrics(
    db: Session = Depends(get_db)
):
    """
    Get project plan management metrics.
    
    Returns metrics including:
    - Intent distribution (common request types)
    - Conversation patterns
    - Error rates by intent type
    
    Args:
        db: Database session
        
    Returns:
        Dict with all metrics
        
    Validates: Requirements 10.5
    """
    try:
        metrics = get_metrics_instance(db)
        all_metrics = metrics.get_all_metrics()
        
        logger.info(
            "Metrics retrieved",
            extra={
                'extra_fields': {
                    'event': 'metrics_retrieved',
                    'total_intents': sum(all_metrics['intent_distribution'].values()),
                    'total_conversations': all_metrics['conversation_patterns']['total_conversations']
                }
            }
        )
        
        return all_metrics
    
    except Exception as e:
        logger.error(
            "Error retrieving metrics",
            extra={
                'extra_fields': {
                    'event': 'metrics_retrieval_error',
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


async def _handle_intent(
    intent: Any,
    project: Any,
    milestones: List[Any],
    user_uuid: UUID,
    project_plan_service: ProjectPlanService,
    formatter: DiscordProjectPlanFormatter,
    conversation_manager: ProjectPlanConversationManager,
    milestone_generator: MilestoneGenerator,
    db: Session
) -> str:
    """
    Handle a classified intent and generate appropriate response.
    
    Args:
        intent: Classified intent
        project: Project object
        milestones: List of milestones
        user_uuid: User UUID
        project_plan_service: Project plan service instance
        formatter: Discord formatter instance
        conversation_manager: Conversation manager instance
        milestone_generator: Milestone generator instance
        db: Database session
        
    Returns:
        Response message string
        
    Validates: Requirements 1.1, 2.1, 3.1, 3.2, 3.3, 3.4, 4.1, 5.1
    """
    # Handle VIEW_PLAN intent
    if intent.type == IntentType.VIEW_PLAN:
        return await _handle_view_plan(
            project=project,
            milestones=milestones,
            formatter=formatter,
            milestone_generator=milestone_generator
        )
    
    # Handle EDIT_DEADLINE intent
    elif intent.type == IntentType.EDIT_DEADLINE:
        return await _handle_edit_deadline(
            intent=intent,
            project=project,
            milestones=milestones,
            user_uuid=user_uuid,
            project_plan_service=project_plan_service,
            formatter=formatter,
            conversation_manager=conversation_manager,
            db=db
        )
    
    # Handle ADD_MILESTONE intent
    elif intent.type == IntentType.ADD_MILESTONE:
        return await _handle_add_milestone(
            intent=intent,
            project=project,
            user_uuid=user_uuid,
            project_plan_service=project_plan_service,
            formatter=formatter,
            db=db
        )
    
    # Handle EDIT_MILESTONE intent
    elif intent.type == IntentType.EDIT_MILESTONE:
        return await _handle_edit_milestone(
            intent=intent,
            project=project,
            milestones=milestones,
            user_uuid=user_uuid,
            project_plan_service=project_plan_service,
            formatter=formatter,
            db=db
        )
    
    # Handle DELETE_MILESTONE intent
    elif intent.type == IntentType.DELETE_MILESTONE:
        return await _handle_delete_milestone(
            intent=intent,
            project=project,
            milestones=milestones,
            user_uuid=user_uuid,
            project_plan_service=project_plan_service,
            conversation_manager=conversation_manager,
            db=db
        )
    
    # Handle MARK_COMPLETE intent
    elif intent.type == IntentType.MARK_COMPLETE:
        return await _handle_mark_complete(
            intent=intent,
            project=project,
            milestones=milestones,
            user_uuid=user_uuid,
            project_plan_service=project_plan_service,
            formatter=formatter,
            db=db
        )
    
    # Handle ASK_QUESTION intent
    elif intent.type == IntentType.ASK_QUESTION:
        return await _handle_ask_question(
            intent=intent,
            project=project,
            milestones=milestones,
            formatter=formatter,
            user=db.query(User).filter(User.id == user_uuid).first()
        )
    
    # Handle UNCLEAR intent
    elif intent.type == IntentType.UNCLEAR:
        return _handle_unclear()
    
    # Fallback for unknown intents
    else:
        logger.warning(f"Unknown intent type: {intent.type}")
        return _handle_unclear()
