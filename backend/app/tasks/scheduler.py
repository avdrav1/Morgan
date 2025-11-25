from datetime import datetime, timedelta
from sqlalchemy import and_
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.metrics import track_check_in_sent, track_message_delivery
from app.core.logging_config import get_logger
from app.models import CheckIn, CheckInStatus, CheckInType, Task, TaskStatus, Project, ProjectStatus, User
from app.services.llm_service import llm_service
from app.services.scheduler_service import SchedulerService
from app.services.discord_adapter import DiscordAdapter
from app.services.web_adapter import WebAdapter
from app.services.messaging_adapter import MessagePlatform
from zoneinfo import ZoneInfo
import asyncio

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.scheduler.process_scheduled_check_ins")
def process_scheduled_check_ins():
    """Process check-ins that are due to be sent.
    
    Uses SchedulerService for quiet hours checking, enhanced LLM service
    for message generation, and MessagingAdapter for platform-agnostic delivery.
    
    Requirements: 3.1, 3.2, 3.3
    """
    db = SessionLocal()
    scheduler_service = SchedulerService()
    
    try:
        now = datetime.utcnow()
        
        # Find check-ins that are due
        check_ins = db.query(CheckIn).filter(
            and_(
                CheckIn.status == CheckInStatus.PENDING,
                CheckIn.scheduled_for <= now
            )
        ).all()
        
        logger.info(f"Processing {len(check_ins)} scheduled check-ins")
        
        for check_in in check_ins:
            try:
                # Get related entities
                project = db.query(Project).filter(Project.id == check_in.project_id).first()
                if not project:
                    logger.error(f"Project not found for check-in {check_in.id}")
                    continue
                
                task = db.query(Task).filter(Task.id == check_in.task_id).first() if check_in.task_id else None
                user = db.query(User).filter(User.id == project.user_id).first()
                
                if not user:
                    logger.error(f"User not found for check-in {check_in.id}")
                    continue
                
                # Check if user has paused messaging
                if user.messaging_paused:
                    logger.info(f"Skipping check-in {check_in.id} - user has paused messaging")
                    # Don't reschedule, just skip
                    continue
                
                # Convert current time to user's timezone for quiet hours check
                user_tz = ZoneInfo(user.timezone)
                now_user_tz = now.replace(tzinfo=ZoneInfo('UTC')).astimezone(user_tz)
                
                # Check quiet hours using SchedulerService
                if scheduler_service.is_within_quiet_hours(user, now_user_tz):
                    logger.info(f"Skipping check-in {check_in.id} - within quiet hours")
                    # Find next available slot after quiet hours
                    next_slot = scheduler_service.find_next_available_slot(
                        user=user,
                        preferred_time=now + timedelta(hours=1),
                        availability_windows=[]  # Just check quiet hours
                    )
                    if next_slot:
                        check_in.scheduled_for = next_slot
                        db.commit()
                    else:
                        # If no slot found, try again in 1 hour
                        check_in.scheduled_for = now + timedelta(hours=1)
                        db.commit()
                    continue
                
                # Generate message using enhanced LLM service
                message = asyncio.run(llm_service.generate_check_in_message(
                    user=user,
                    project=project,
                    task=task,
                    check_in_type=check_in.check_in_type.value
                ))
                
                # Determine platform and send message using appropriate adapter
                platform = check_in.platform or "discord"
                
                if platform == MessagePlatform.DISCORD.value and user.discord_user_id:
                    # Use Discord adapter
                    adapter = DiscordAdapter()
                    success = asyncio.run(adapter.send_message_with_retry(
                        user_identifier=user.discord_user_id,
                        message=message,
                        metadata={"check_in_id": str(check_in.id)}
                    ))
                elif platform == MessagePlatform.WEB.value:
                    # Use Web adapter
                    adapter = WebAdapter()
                    success = asyncio.run(adapter.send_message_with_retry(
                        user_identifier=str(user.id),
                        message=message,
                        metadata={"check_in_id": str(check_in.id)}
                    ))
                else:
                    logger.warning(f"Unknown platform {platform} for check-in {check_in.id}")
                    success = False
                
                if success:
                    # Update check-in status
                    check_in.status = CheckInStatus.SENT
                    check_in.sent_at = now
                    check_in.message_sent = message
                    
                    # Update user engagement tracking
                    user.total_check_ins_sent += 1
                    
                    db.commit()
                    
                    # Track metrics: check-in sent
                    track_check_in_sent(
                        user_id=str(user.id),
                        project_id=str(project.id)
                    )
                    
                    # Track metrics: message delivery success
                    track_message_delivery(
                        platform=platform,
                        success=True,
                        retry_count=0
                    )
                    
                    logger.info(f"Successfully sent check-in {check_in.id}")
                else:
                    # Message delivery failed after all retries
                    logger.error(f"Failed to deliver check-in {check_in.id} after retries")
                    
                    # Track metrics: message delivery failure
                    track_message_delivery(
                        platform=platform,
                        success=False,
                        retry_count=5  # Max retries
                    )
                    
                    # Don't mark as missed since it's a delivery failure, not user's fault
                    # Reschedule for later retry
                    check_in.scheduled_for = now + timedelta(hours=1)
                    db.commit()
                
            except Exception as e:
                logger.error(f"Error processing check-in {check_in.id}: {str(e)}")
                db.rollback()
        
    except Exception as e:
        logger.error(f"Error in process_scheduled_check_ins: {str(e)}")
    finally:
        db.close()


@celery_app.task(name="app.tasks.scheduler.detect_and_handle_ghosting")
def detect_and_handle_ghosting():
    """Detect users with missed check-ins and trigger appropriate responses.
    
    Checks for users who have missed 2, 4, or 7 consecutive check-ins and
    triggers appropriate ghosting responses based on the stage.
    
    Requirements: 9.1, 9.2, 9.3, 9.4
    """
    db = SessionLocal()
    scheduler_service = SchedulerService()
    
    try:
        # Find all active projects
        active_projects = db.query(Project).filter(
            Project.status == ProjectStatus.ACTIVE
        ).all()
        
        logger.info(f"Checking {len(active_projects)} active projects for ghosting")
        
        for project in active_projects:
            try:
                user = db.query(User).filter(User.id == project.user_id).first()
                if not user:
                    continue
                
                # Skip if user has paused messaging
                if user.messaging_paused:
                    continue
                
                # Count consecutive missed check-ins for this project
                recent_check_ins = db.query(CheckIn).filter(
                    and_(
                        CheckIn.project_id == project.id,
                        CheckIn.status.in_([CheckInStatus.SENT, CheckInStatus.RESPONDED, CheckInStatus.MISSED])
                    )
                ).order_by(CheckIn.sent_at.desc()).limit(10).all()
                
                # Count consecutive missed from most recent
                consecutive_missed = 0
                for check_in in recent_check_ins:
                    if check_in.status == CheckInStatus.MISSED:
                        consecutive_missed += 1
                    else:
                        # Stop counting when we hit a responded check-in
                        break
                
                # Update user's consecutive missed count
                user.consecutive_missed_check_ins = consecutive_missed
                
                # Check if we need to trigger a ghosting response
                if consecutive_missed >= 2:
                    # Calculate appropriate response
                    ghosting_response = scheduler_service.calculate_ghosting_response(
                        user=user,
                        project=project,
                        missed_count=consecutive_missed
                    )
                    
                    # Update project ghosting stage
                    project.ghosting_stage = ghosting_response["ghosting_stage"]
                    
                    # Check if we've already sent a ghosting message for this stage
                    # to avoid spamming the user
                    last_ghosting_check_in = db.query(CheckIn).filter(
                        and_(
                            CheckIn.project_id == project.id,
                            CheckIn.check_in_type == CheckInType.SCHEDULED,
                            CheckIn.status == CheckInStatus.SENT
                        )
                    ).order_by(CheckIn.sent_at.desc()).first()
                    
                    # Only send ghosting message if we haven't sent one recently
                    # (within last 24 hours)
                    should_send = True
                    if last_ghosting_check_in and last_ghosting_check_in.sent_at:
                        hours_since_last = (datetime.utcnow() - last_ghosting_check_in.sent_at).total_seconds() / 3600
                        if hours_since_last < 24:
                            should_send = False
                    
                    if should_send and ghosting_response["response_type"] != "none":
                        # Generate ghosting message using LLM
                        message = asyncio.run(llm_service.generate_ghosting_message(
                            user=user,
                            project=project,
                            ghosting_stage=ghosting_response["ghosting_stage"],
                            message_template=ghosting_response["message_template"]
                        ))
                        
                        # Determine platform
                        platform = "discord" if user.discord_user_id else "web"
                        
                        # Send message using appropriate adapter
                        if platform == MessagePlatform.DISCORD.value and user.discord_user_id:
                            adapter = DiscordAdapter()
                            success = asyncio.run(adapter.send_message_with_retry(
                                user_identifier=user.discord_user_id,
                                message=message,
                                metadata={"project_id": str(project.id), "ghosting_stage": ghosting_response["ghosting_stage"]}
                            ))
                        elif platform == MessagePlatform.WEB.value:
                            adapter = WebAdapter()
                            success = asyncio.run(adapter.send_message_with_retry(
                                user_identifier=str(user.id),
                                message=message,
                                metadata={"project_id": str(project.id), "ghosting_stage": ghosting_response["ghosting_stage"]}
                            ))
                        else:
                            success = False
                        
                        if success:
                            logger.info(
                                f"Sent ghosting stage {ghosting_response['ghosting_stage']} "
                                f"message for project {project.id}"
                            )
                        else:
                            logger.error(
                                f"Failed to send ghosting message for project {project.id}"
                            )
                
                db.commit()
                
            except Exception as e:
                logger.error(f"Error processing ghosting for project {project.id}: {str(e)}")
                db.rollback()
        
    except Exception as e:
        logger.error(f"Error in detect_and_handle_ghosting: {str(e)}")
    finally:
        db.close()


@celery_app.task(name="app.tasks.scheduler.schedule_upcoming_check_ins")
def schedule_upcoming_check_ins():
    """Schedule check-ins for upcoming task deadlines.
    
    Uses SchedulerService for availability-aware scheduling and implements
    adaptive frequency logic based on user responsiveness.
    
    Requirements: 2.6, 3.4, 3.5, 3.6
    """
    db = SessionLocal()
    scheduler_service = SchedulerService()
    
    try:
        now = datetime.utcnow()
        look_ahead = now + timedelta(days=7)  # Look 7 days ahead
        
        # Find active tasks with upcoming deadlines that don't have pending check-ins
        tasks = db.query(Task).join(Project).filter(
            and_(
                Task.status.in_([TaskStatus.NOT_STARTED, TaskStatus.IN_PROGRESS]),
                Task.due_date.isnot(None),
                Task.due_date >= now,
                Task.due_date <= look_ahead,
                Project.status == ProjectStatus.ACTIVE
            )
        ).all()
        
        logger.info(f"Scheduling check-ins for {len(tasks)} tasks")
        
        for task in tasks:
            try:
                # Check if there's already a pending check-in for this task
                existing = db.query(CheckIn).filter(
                    and_(
                        CheckIn.task_id == task.id,
                        CheckIn.status == CheckInStatus.PENDING
                    )
                ).first()
                
                if existing:
                    continue
                
                # Get project and user
                project = db.query(Project).filter(Project.id == task.project_id).first()
                if not project:
                    logger.error(f"Project not found for task {task.id}")
                    continue
                
                user = db.query(User).filter(User.id == project.user_id).first()
                if not user:
                    logger.error(f"User not found for task {task.id}")
                    continue
                
                # Skip if user has paused messaging
                if user.messaging_paused:
                    logger.info(f"Skipping task {task.id} - user has paused messaging")
                    continue
                
                # Get user's availability windows
                from app.models.availability_window import AvailabilityWindow
                availability_windows = db.query(AvailabilityWindow).filter(
                    AvailabilityWindow.user_id == user.id
                ).all()
                
                # Get recent check-ins for adaptive frequency
                recent_check_ins = db.query(CheckIn).filter(
                    and_(
                        CheckIn.project_id == project.id,
                        CheckIn.status.in_([CheckInStatus.SENT, CheckInStatus.RESPONDED, CheckInStatus.MISSED])
                    )
                ).order_by(CheckIn.sent_at.desc()).limit(10).all()
                
                # Determine if we should adapt frequency
                adaptation, reason = scheduler_service.should_adapt_frequency(
                    user=user,
                    project=project,
                    recent_check_ins=recent_check_ins
                )
                
                logger.info(f"Frequency adaptation for task {task.id}: {adaptation} - {reason}")
                
                # Calculate optimal check-in time using SchedulerService
                check_in_time = scheduler_service.calculate_check_in_time(
                    task=task,
                    user=user,
                    availability_windows=availability_windows
                )
                
                if not check_in_time:
                    logger.warning(
                        f"Could not find valid check-in time for task {task.id} "
                        f"with current availability constraints"
                    )
                    continue
                
                # Apply frequency adaptation
                if adaptation == "decrease":
                    # Reduce frequency by pushing check-in later (but still before due date)
                    time_until_due = (task.due_date - check_in_time).total_seconds() / 3600  # hours
                    if time_until_due > 48:  # If more than 2 days until due
                        # Push check-in 12 hours later
                        check_in_time = check_in_time + timedelta(hours=12)
                        # Make sure it's still before due date
                        if check_in_time >= task.due_date:
                            check_in_time = task.due_date - timedelta(hours=6)
                elif adaptation == "increase":
                    # Increase frequency by scheduling earlier
                    time_until_due = (task.due_date - check_in_time).total_seconds() / 3600  # hours
                    if time_until_due > 24:  # If more than 1 day until due
                        # Schedule 12 hours earlier
                        check_in_time = check_in_time - timedelta(hours=12)
                        # Make sure it's not in the past
                        if check_in_time < now:
                            check_in_time = now + timedelta(hours=1)
                
                # Determine platform (prefer Discord if available, otherwise web)
                platform = "discord" if user.discord_user_id else "web"
                
                # Create check-in
                check_in = CheckIn(
                    project_id=task.project_id,
                    task_id=task.id,
                    check_in_type=CheckInType.SCHEDULED,
                    status=CheckInStatus.PENDING,
                    scheduled_for=check_in_time,
                    platform=platform
                )
                
                db.add(check_in)
                db.commit()
                
                logger.info(
                    f"Scheduled check-in for task {task.id} at {check_in_time} "
                    f"(adaptation: {adaptation})"
                )
                
            except Exception as e:
                logger.error(f"Error scheduling check-in for task {task.id}: {str(e)}")
                db.rollback()
        
    except Exception as e:
        logger.error(f"Error in schedule_upcoming_check_ins: {str(e)}")
    finally:
        db.close()



@celery_app.task(name="app.tasks.scheduler.send_onboarding_reminders")
def send_onboarding_reminders():
    """Send reminder DMs to users with inactive onboarding sessions.
    
    Checks for onboarding sessions that have been inactive for 24+ hours
    and sends gentle reminder messages to encourage completion.
    
    Requirements: 6.3
    """
    db = SessionLocal()
    
    try:
        from app.services.onboarding_service import OnboardingService
        
        onboarding_service = OnboardingService(db)
        
        # Get sessions inactive for 24+ hours
        inactive_sessions = asyncio.run(onboarding_service.get_inactive_sessions(hours=24))
        
        logger.info(f"Found {len(inactive_sessions)} inactive onboarding sessions")
        
        for session in inactive_sessions:
            try:
                # Send reminder
                success = asyncio.run(onboarding_service.send_reminder(session.user_id))
                
                if success:
                    logger.info(
                        f"Sent onboarding reminder to user {session.user_id}",
                        extra={'extra_fields': {
                            'user_id': str(session.user_id),
                            'session_id': str(session.id),
                            'current_state': session.current_state.value
                        }}
                    )
                else:
                    logger.warning(
                        f"Failed to send onboarding reminder to user {session.user_id}",
                        extra={'extra_fields': {
                            'user_id': str(session.user_id),
                            'session_id': str(session.id)
                        }}
                    )
                    
            except Exception as e:
                logger.error(
                    f"Error sending reminder for session {session.id}: {str(e)}",
                    extra={'extra_fields': {
                        'session_id': str(session.id),
                        'error': str(e)
                    }},
                    exc_info=True
                )
        
    except Exception as e:
        logger.error(f"Error in send_onboarding_reminders: {str(e)}", exc_info=True)
    finally:
        db.close()


@celery_app.task(name="app.tasks.scheduler.cleanup_abandoned_onboarding_sessions")
def cleanup_abandoned_onboarding_sessions():
    """Mark abandoned onboarding sessions and archive old ones.
    
    This task performs two cleanup operations:
    1. Marks sessions as abandoned after 7 days of inactivity
    2. Archives old sessions (completed or failed) after 30 days
    
    Requirements: 6.3, 6.5
    """
    db = SessionLocal()
    
    try:
        from app.services.onboarding_service import OnboardingService
        
        onboarding_service = OnboardingService(db)
        
        # Mark sessions abandoned after 7 days of inactivity
        abandoned_count = asyncio.run(onboarding_service.mark_abandoned_sessions(days=7))
        
        logger.info(
            f"Marked {abandoned_count} onboarding sessions as abandoned",
            extra={'extra_fields': {
                'event': 'onboarding_cleanup_abandoned',
                'count': abandoned_count
            }}
        )
        
        # Archive old sessions after 30 days
        archived_count = asyncio.run(onboarding_service.archive_old_sessions(days=30))
        
        logger.info(
            f"Archived {archived_count} old onboarding sessions",
            extra={'extra_fields': {
                'event': 'onboarding_cleanup_archived',
                'count': archived_count
            }}
        )
        
    except Exception as e:
        logger.error(
            f"Error in cleanup_abandoned_onboarding_sessions: {str(e)}",
            extra={'extra_fields': {
                'error': str(e)
            }},
            exc_info=True
        )
    finally:
        db.close()


@celery_app.task(name="app.tasks.scheduler.schedule_blocker_followups")
def schedule_blocker_followups():
    """Schedule followup check-ins for blocked tasks.
    
    Identifies tasks that have been diagnosed with blockers and schedules
    followup check-ins to maintain context and provide continued support.
    
    Requirements: 4.2, 4.6
    """
    db = SessionLocal()
    scheduler_service = SchedulerService()
    
    try:
        now = datetime.utcnow()
        
        # Find tasks that are blocked and haven't had a recent followup
        from app.models.task import TaskStatus
        blocked_tasks = db.query(Task).join(Project).filter(
            and_(
                Task.status == TaskStatus.BLOCKED,
                Task.blocker_type.isnot(None),
                Project.status == ProjectStatus.ACTIVE
            )
        ).all()
        
        logger.info(f"Processing {len(blocked_tasks)} blocked tasks for followup")
        
        for task in blocked_tasks:
            try:
                # Get project and user
                project = db.query(Project).filter(Project.id == task.project_id).first()
                if not project:
                    continue
                
                user = db.query(User).filter(User.id == project.user_id).first()
                if not user:
                    continue
                
                # Skip if user has paused messaging
                if user.messaging_paused:
                    continue
                
                # Check if there's already a pending blocker followup for this task
                existing_followup = db.query(CheckIn).filter(
                    and_(
                        CheckIn.task_id == task.id,
                        CheckIn.check_in_type == CheckInType.BLOCKER_FOLLOWUP,
                        CheckIn.status == CheckInStatus.PENDING
                    )
                ).first()
                
                if existing_followup:
                    continue
                
                # Check when the blocker was diagnosed
                if not task.blocker_diagnosed_at:
                    # If no diagnosis time, use current time
                    task.blocker_diagnosed_at = now
                    db.commit()
                
                # Calculate time since blocker was diagnosed
                hours_since_diagnosis = (now - task.blocker_diagnosed_at).total_seconds() / 3600
                
                # Schedule followup based on blocker type and time since diagnosis
                # Different blocker types may need different followup cadences
                should_schedule_followup = False
                
                if task.blocker_type == "external":
                    # External blockers: check every 48 hours
                    should_schedule_followup = hours_since_diagnosis >= 48
                elif task.blocker_type == "clarity":
                    # Clarity blockers: check every 24 hours
                    should_schedule_followup = hours_since_diagnosis >= 24
                elif task.blocker_type == "emotional":
                    # Emotional blockers: check every 36 hours (give space but stay engaged)
                    should_schedule_followup = hours_since_diagnosis >= 36
                elif task.blocker_type == "time":
                    # Time blockers: check every 48 hours
                    should_schedule_followup = hours_since_diagnosis >= 48
                elif task.blocker_type == "scope":
                    # Scope blockers: check every 24 hours
                    should_schedule_followup = hours_since_diagnosis >= 24
                
                if not should_schedule_followup:
                    continue
                
                # Get user's availability windows
                from app.models.availability_window import AvailabilityWindow
                availability_windows = db.query(AvailabilityWindow).filter(
                    AvailabilityWindow.user_id == user.id
                ).all()
                
                # Calculate optimal followup time
                # For blocked tasks, we want to check in soon but respect availability
                preferred_time = now + timedelta(hours=2)
                
                followup_time = scheduler_service.find_next_available_slot(
                    user=user,
                    preferred_time=preferred_time,
                    availability_windows=availability_windows
                )
                
                if not followup_time:
                    logger.warning(
                        f"Could not find valid followup time for blocked task {task.id}"
                    )
                    continue
                
                # Determine platform
                platform = "discord" if user.discord_user_id else "web"
                
                # Create blocker followup check-in
                check_in = CheckIn(
                    project_id=task.project_id,
                    task_id=task.id,
                    check_in_type=CheckInType.BLOCKER_FOLLOWUP,
                    status=CheckInStatus.PENDING,
                    scheduled_for=followup_time,
                    platform=platform,
                    blocker_detected=True
                )
                
                db.add(check_in)
                db.commit()
                
                logger.info(
                    f"Scheduled blocker followup for task {task.id} "
                    f"(blocker type: {task.blocker_type}) at {followup_time}"
                )
                
            except Exception as e:
                logger.error(f"Error scheduling blocker followup for task {task.id}: {str(e)}")
                db.rollback()
        
    except Exception as e:
        logger.error(f"Error in schedule_blocker_followups: {str(e)}")
    finally:
        db.close()
