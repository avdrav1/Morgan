"""
Onboarding service for managing Discord DM onboarding flow.

This service orchestrates the onboarding state machine, validates user inputs,
and coordinates with the backend API to create projects.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

from app.models.onboarding_session import OnboardingSession, OnboardingState
from app.models.user import User
from app.models.project import Project
from app.services.onboarding_state_machine import OnboardingStateMachine
from app.services.llm_service import llm_service
from app.core.logging_config import get_logger, set_correlation_id, get_correlation_id
from app.core.metrics import metrics

logger = get_logger(__name__)


class OnboardingService:
    """
    Service for managing Discord DM onboarding sessions.
    
    Handles session creation, state transitions, data persistence,
    and project creation upon completion.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the onboarding service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.state_machine = OnboardingStateMachine()
    
    async def start_onboarding(
        self,
        user_id: UUID,
        discord_id: str,
        dm_enabled: bool = True
    ) -> Optional[OnboardingSession]:
        """
        Start a new onboarding session for a user.
        
        Creates a new onboarding session in the WELCOME state.
        If a session already exists for this user, returns the existing session.
        If DM delivery fails (dm_enabled=False), returns None to indicate
        web onboarding should be used instead.
        
        Args:
            user_id: UUID of the user
            discord_id: Discord user ID
            dm_enabled: Whether Discord DMs are enabled for this user
            
        Returns:
            Optional[OnboardingSession]: The created or existing onboarding session,
                                        or None if DM delivery failed
            
        Validates: Requirements 1.4, 7.1, 7.2
        """
        # Set correlation ID for this onboarding flow
        correlation_id = set_correlation_id()
        
        logger.info(
            "Starting onboarding",
            extra={
                'extra_fields': {
                    'event': 'onboarding_start',
                    'user_id': str(user_id),
                    'discord_id': discord_id,
                    'dm_enabled': dm_enabled,
                    'correlation_id': correlation_id
                }
            }
        )
        
        # Track onboarding start attempt
        metrics.increment('onboarding_started', {'dm_enabled': str(dm_enabled)})
        
        # If DMs are disabled, don't create a session
        if not dm_enabled:
            logger.warning(
                "DM delivery failed - redirecting to web onboarding",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_dm_failed',
                        'user_id': str(user_id),
                        'discord_id': discord_id,
                        'correlation_id': correlation_id
                    }
                }
            )
            metrics.increment('onboarding_dm_failed')
            return None
        
        # Check if user already has an active onboarding session
        existing_session = self.db.query(OnboardingSession).filter(
            OnboardingSession.user_id == user_id,
            OnboardingSession.current_state != OnboardingState.COMPLETED
        ).first()
        
        if existing_session:
            logger.info(
                "Found existing onboarding session",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_session_resumed',
                        'session_id': str(existing_session.id),
                        'user_id': str(user_id),
                        'current_state': existing_session.current_state.value,
                        'correlation_id': correlation_id
                    }
                }
            )
            metrics.increment('onboarding_session_resumed')
            return existing_session
        
        # Create new onboarding session
        session = OnboardingSession(
            user_id=user_id,
            discord_id=discord_id,
            current_state=OnboardingState.WELCOME,
            started_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
            conversation_history=[]
        )
        
        self.db.add(session)
        
        try:
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(
                "Onboarding session created",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_session_created',
                        'session_id': str(session.id),
                        'user_id': str(user_id),
                        'state': session.current_state.value,
                        'correlation_id': correlation_id
                    }
                }
            )
            metrics.increment('onboarding_session_created')
            
            return session
        except IntegrityError as e:
            self.db.rollback()
            logger.error(
                "Failed to create onboarding session",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_session_creation_failed',
                        'user_id': str(user_id),
                        'error': str(e),
                        'correlation_id': correlation_id
                    }
                },
                exc_info=True
            )
            metrics.increment('onboarding_errors', {'error_type': 'session_creation_failed'})
            raise
    
    async def process_message(
        self,
        user_id: UUID,
        message: str,
        next_state: Optional[OnboardingState] = None
    ) -> OnboardingSession:
        """
        Process a user message and update the onboarding session.
        
        Updates the session with the user's message, validates state transitions,
        and persists the data to the database.
        
        Args:
            user_id: UUID of the user
            message: The user's message
            next_state: Optional next state to transition to
            
        Returns:
            OnboardingSession: The updated onboarding session
            
        Raises:
            ValueError: If the session is not found or state transition is invalid
            
        Validates: Requirements 2.1, 6.2
        """
        correlation_id = get_correlation_id() or set_correlation_id()
        
        logger.info(
            "Processing onboarding message",
            extra={
                'extra_fields': {
                    'event': 'onboarding_message_received',
                    'user_id': str(user_id),
                    'message_length': len(message),
                    'correlation_id': correlation_id
                }
            }
        )
        
        # Get the session
        session = await self.get_session(user_id)
        if not session:
            logger.error(
                "Onboarding session not found",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_session_not_found',
                        'user_id': str(user_id),
                        'correlation_id': correlation_id
                    }
                }
            )
            metrics.increment('onboarding_errors', {'error_type': 'session_not_found'})
            raise ValueError(f"No onboarding session found for user {user_id}")
        
        previous_state = session.current_state
        
        # Add message to conversation history
        conversation_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "role": "user",
            "message": message
        }
        
        if session.conversation_history is None:
            session.conversation_history = []
        
        session.conversation_history.append(conversation_entry)
        
        # Mark conversation_history as modified so SQLAlchemy tracks the change
        flag_modified(session, "conversation_history")
        
        # Update last activity
        session.last_activity_at = datetime.utcnow()
        
        # Validate and perform state transition if requested
        if next_state is not None:
            try:
                self.state_machine.validate_transition(session.current_state, next_state)
                session.current_state = next_state
                
                logger.info(
                    "Onboarding state transition",
                    extra={
                        'extra_fields': {
                            'event': 'onboarding_state_transition',
                            'session_id': str(session.id),
                            'user_id': str(user_id),
                            'from_state': previous_state.value,
                            'to_state': next_state.value,
                            'correlation_id': correlation_id
                        }
                    }
                )
                metrics.increment('onboarding_state_transitions', {
                    'from_state': previous_state.value,
                    'to_state': next_state.value
                })
            except ValueError as e:
                logger.error(
                    "Invalid state transition",
                    extra={
                        'extra_fields': {
                            'event': 'onboarding_invalid_transition',
                            'session_id': str(session.id),
                            'user_id': str(user_id),
                            'from_state': previous_state.value,
                            'to_state': next_state.value,
                            'error': str(e),
                            'correlation_id': correlation_id
                        }
                    }
                )
                metrics.increment('onboarding_errors', {'error_type': 'invalid_state_transition'})
                raise
        
        # Persist changes
        try:
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(
                "Onboarding session updated",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_session_updated',
                        'session_id': str(session.id),
                        'user_id': str(user_id),
                        'current_state': session.current_state.value,
                        'correlation_id': correlation_id
                    }
                }
            )
            
            return session
        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to update onboarding session",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_session_update_failed',
                        'session_id': str(session.id),
                        'user_id': str(user_id),
                        'error': str(e),
                        'correlation_id': correlation_id
                    }
                },
                exc_info=True
            )
            metrics.increment('onboarding_errors', {'error_type': 'session_update_failed'})
            raise
    
    async def get_session(self, user_id: UUID) -> Optional[OnboardingSession]:
        """
        Retrieve an onboarding session for a user.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            Optional[OnboardingSession]: The onboarding session if found, None otherwise
        """
        session = self.db.query(OnboardingSession).filter(
            OnboardingSession.user_id == user_id,
            OnboardingSession.current_state != OnboardingState.COMPLETED
        ).first()
        
        return session
    
    async def cancel_onboarding(self, user_id: UUID) -> None:
        """
        Cancel an onboarding session.
        
        Sets the session state to PAUSED without creating a project.
        
        Args:
            user_id: UUID of the user
            
        Raises:
            ValueError: If the session is not found
            
        Validates: Requirements 9.1, 9.2
        """
        correlation_id = get_correlation_id() or set_correlation_id()
        
        logger.info(
            "Cancelling onboarding",
            extra={
                'extra_fields': {
                    'event': 'onboarding_cancel_requested',
                    'user_id': str(user_id),
                    'correlation_id': correlation_id
                }
            }
        )
        
        session = await self.get_session(user_id)
        if not session:
            logger.error(
                "Cannot cancel - session not found",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_cancel_failed',
                        'user_id': str(user_id),
                        'reason': 'session_not_found',
                        'correlation_id': correlation_id
                    }
                }
            )
            metrics.increment('onboarding_errors', {'error_type': 'cancel_session_not_found'})
            raise ValueError(f"No onboarding session found for user {user_id}")
        
        previous_state = session.current_state
        
        # Validate transition to PAUSED
        self.state_machine.validate_transition(session.current_state, OnboardingState.PAUSED)
        
        session.current_state = OnboardingState.PAUSED
        session.last_activity_at = datetime.utcnow()
        
        try:
            self.db.commit()
            
            logger.info(
                "Onboarding cancelled",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_cancelled',
                        'session_id': str(session.id),
                        'user_id': str(user_id),
                        'previous_state': previous_state.value,
                        'correlation_id': correlation_id
                    }
                }
            )
            metrics.increment('onboarding_cancelled', {'from_state': previous_state.value})
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to cancel onboarding",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_cancel_error',
                        'session_id': str(session.id),
                        'user_id': str(user_id),
                        'error': str(e),
                        'correlation_id': correlation_id
                    }
                },
                exc_info=True
            )
            metrics.increment('onboarding_errors', {'error_type': 'cancel_failed'})
            raise
    
    async def restart_onboarding(self, user_id: UUID) -> OnboardingSession:
        """
        Restart an onboarding session from the beginning.
        
        Clears collected data and resets to WELCOME state.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            OnboardingSession: The restarted onboarding session
            
        Raises:
            ValueError: If the session is not found
        """
        logger.info(f"Restarting onboarding for user {user_id}")
        
        session = await self.get_session(user_id)
        if not session:
            raise ValueError(f"No onboarding session found for user {user_id}")
        
        # If not already in PAUSED or FAILED state, transition to PAUSED first
        # (only PAUSED and FAILED states can transition to WELCOME)
        if session.current_state not in [OnboardingState.PAUSED, OnboardingState.FAILED]:
            self.state_machine.validate_transition(session.current_state, OnboardingState.PAUSED)
            session.current_state = OnboardingState.PAUSED
            self.db.commit()
        
        # Now validate transition to WELCOME
        self.state_machine.validate_transition(session.current_state, OnboardingState.WELCOME)
        
        # Clear collected data
        session.current_state = OnboardingState.WELCOME
        session.project_name = None
        session.project_goal = None
        session.deadline = None
        session.checkin_frequency = None
        session.preferred_tone = None
        session.conversation_history = []
        session.last_activity_at = datetime.utcnow()
        session.retry_count = 0
        session.error_message = None
        
        try:
            self.db.commit()
            self.db.refresh(session)
            logger.info(f"Restarted onboarding session {session.id}")
            return session
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to restart onboarding session {session.id}: {e}")
            raise
    
    async def complete_onboarding(self, user_id: UUID, max_retries: int = 3) -> Project:
        """
        Complete the onboarding process and create a project.
        
        Creates a project from the collected onboarding data and marks
        the user as no longer new. Implements idempotency - if called
        multiple times, returns the same project without creating duplicates.
        Includes retry logic for handling transient errors.
        
        Args:
            user_id: UUID of the user
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            Project: The created project
            
        Raises:
            ValueError: If the session is not found or required data is missing
            
        Validates: Requirements 5.1, 5.2, 5.3, 5.4
        """
        correlation_id = get_correlation_id() or set_correlation_id()
        start_time = datetime.utcnow()
        
        logger.info(
            "Completing onboarding",
            extra={
                'extra_fields': {
                    'event': 'onboarding_completion_started',
                    'user_id': str(user_id),
                    'correlation_id': correlation_id
                }
            }
        )
        
        # Query for session directly (including completed ones for idempotency)
        session = self.db.query(OnboardingSession).filter(
            OnboardingSession.user_id == user_id
        ).order_by(OnboardingSession.created_at.desc()).first()
        
        if not session:
            logger.error(
                "Cannot complete - session not found",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_completion_failed',
                        'user_id': str(user_id),
                        'reason': 'session_not_found',
                        'correlation_id': correlation_id
                    }
                }
            )
            metrics.increment('onboarding_errors', {'error_type': 'completion_session_not_found'})
            raise ValueError(f"No onboarding session found for user {user_id}")
        
        # Check if already completed (idempotency)
        if session.current_state == OnboardingState.COMPLETED:
            logger.info(
                "Onboarding already completed (idempotent call)",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_already_completed',
                        'session_id': str(session.id),
                        'user_id': str(user_id),
                        'correlation_id': correlation_id
                    }
                }
            )
            
            # Find the project created for this session
            project = self.db.query(Project).filter(
                Project.user_id == user_id,
                Project.title == session.project_name
            ).first()
            
            if project:
                return project
            else:
                # Session marked complete but no project found - this shouldn't happen
                logger.warning(
                    "Session marked complete but no project found",
                    extra={
                        'extra_fields': {
                            'event': 'onboarding_inconsistent_state',
                            'session_id': str(session.id),
                            'user_id': str(user_id),
                            'correlation_id': correlation_id
                        }
                    }
                )
                metrics.increment('onboarding_errors', {'error_type': 'inconsistent_state'})
        
        # Validate required data
        if not session.project_name:
            logger.error(
                "Cannot complete - missing project name",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_completion_failed',
                        'session_id': str(session.id),
                        'user_id': str(user_id),
                        'reason': 'missing_project_name',
                        'correlation_id': correlation_id
                    }
                }
            )
            metrics.increment('onboarding_errors', {'error_type': 'missing_required_data'})
            raise ValueError("Project name is required to complete onboarding")
            
        if not session.project_goal:
            logger.error(
                "Cannot complete - missing project goal",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_completion_failed',
                        'session_id': str(session.id),
                        'user_id': str(user_id),
                        'reason': 'missing_project_goal',
                        'correlation_id': correlation_id
                    }
                }
            )
            metrics.increment('onboarding_errors', {'error_type': 'missing_required_data'})
            raise ValueError("Project goal is required to complete onboarding")
        
        # Validate transition to CREATING_PROJECT
        self.state_machine.validate_transition(session.current_state, OnboardingState.CREATING_PROJECT)
        session.current_state = OnboardingState.CREATING_PROJECT
        self.db.commit()
        
        # Retry logic for project creation
        last_error = None
        for attempt in range(max_retries):
            try:
                # Create the project
                project = Project(
                    user_id=user_id,
                    title=session.project_name,
                    description=session.project_goal,  # Use goal as description
                    goal=session.project_goal,
                    target_completion_date=session.deadline,
                    project_tone=session.preferred_tone,
                    status="active"
                )
                
                self.db.add(project)
                
                # Mark user as no longer new
                user = self.db.query(User).filter(User.id == user_id).first()
                if user:
                    user.is_new = False
                    user.preferred_tone = session.preferred_tone or user.preferred_tone
                
                # Mark session as completed
                session.current_state = OnboardingState.COMPLETED
                session.completed_at = datetime.utcnow()
                session.last_activity_at = datetime.utcnow()
                
                self.db.commit()
                self.db.refresh(project)
                
                # Calculate completion time
                completion_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                duration_minutes = (session.completed_at - session.started_at).total_seconds() / 60
                
                logger.info(
                    "Onboarding completed successfully",
                    extra={
                        'extra_fields': {
                            'event': 'onboarding_completed',
                            'session_id': str(session.id),
                            'user_id': str(user_id),
                            'project_id': str(project.id),
                            'duration_minutes': round(duration_minutes, 2),
                            'project_name': session.project_name,
                            'has_deadline': session.deadline is not None,
                            'preferred_tone': session.preferred_tone,
                            'retry_attempt': attempt + 1,
                            'correlation_id': correlation_id
                        }
                    }
                )
                
                # Track metrics
                metrics.increment('onboarding_completed', {'has_deadline': str(session.deadline is not None)})
                metrics.record_duration('onboarding_completion_time', completion_time)
                metrics.record_duration('onboarding_total_duration', duration_minutes * 60 * 1000)
                
                if attempt > 0:
                    metrics.increment('onboarding_completion_retries', {'attempt': str(attempt + 1)})
                
                return project
                
            except Exception as e:
                self.db.rollback()
                last_error = e
                
                logger.warning(
                    f"Project creation attempt {attempt + 1} failed",
                    extra={
                        'extra_fields': {
                            'event': 'onboarding_completion_retry',
                            'session_id': str(session.id),
                            'user_id': str(user_id),
                            'attempt': attempt + 1,
                            'max_retries': max_retries,
                            'error': str(e),
                            'correlation_id': correlation_id
                        }
                    }
                )
                
                # If this was the last attempt, mark as failed and raise
                if attempt == max_retries - 1:
                    session.current_state = OnboardingState.FAILED
                    session.error_message = f"Failed after {max_retries} attempts: {str(e)}"
                    session.retry_count = max_retries
                    self.db.commit()
                    
                    logger.error(
                        "Failed to complete onboarding after all retries",
                        extra={
                            'extra_fields': {
                                'event': 'onboarding_completion_error',
                                'session_id': str(session.id),
                                'user_id': str(user_id),
                                'total_attempts': max_retries,
                                'error': str(e),
                                'correlation_id': correlation_id
                            }
                        },
                        exc_info=True
                    )
                    metrics.increment('onboarding_errors', {'error_type': 'completion_failed_all_retries'})
                    raise
                else:
                    # Wait before retrying (exponential backoff)
                    import asyncio
                    wait_time = 2 ** attempt  # 1s, 2s, 4s, etc.
                    logger.info(
                        f"Waiting {wait_time}s before retry",
                        extra={
                            'extra_fields': {
                                'session_id': str(session.id),
                                'wait_time': wait_time,
                                'correlation_id': correlation_id
                            }
                        }
                    )
                    await asyncio.sleep(wait_time)
        
        # This should never be reached, but just in case
        if last_error:
            raise last_error
        else:
            raise RuntimeError("Unexpected error in complete_onboarding")
    
    async def update_session_data(
        self,
        user_id: UUID,
        **data: Any
    ) -> OnboardingSession:
        """
        Update collected data in the onboarding session.
        
        Args:
            user_id: UUID of the user
            **data: Key-value pairs of data to update
            
        Returns:
            OnboardingSession: The updated session
            
        Raises:
            ValueError: If the session is not found
        """
        session = await self.get_session(user_id)
        if not session:
            raise ValueError(f"No onboarding session found for user {user_id}")
        
        # Update allowed fields
        allowed_fields = {
            'project_name', 'project_goal', 'deadline',
            'checkin_frequency', 'preferred_tone'
        }
        
        for key, value in data.items():
            if key in allowed_fields:
                setattr(session, key, value)
        
        session.last_activity_at = datetime.utcnow()
        
        try:
            self.db.commit()
            self.db.refresh(session)
            return session
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update session data for {session.id}: {e}")
            raise
    
    async def generate_completion_summary(self, user_id: UUID) -> str:
        """
        Generate a comprehensive completion summary with project plan.
        
        This method:
        1. Retrieves the onboarding session data
        2. Creates a temporary project object for decomposition
        3. Calls llm_service.decompose_project() to get project tasks/milestones
        4. Formats a summary with user preferences (tone, check-in frequency)
        5. Formats the project plan with tasks and estimated timeline
        6. Combines preferences and plan into a comprehensive summary
        
        Args:
            user_id: UUID of the user
            
        Returns:
            str: Formatted completion summary with preferences and project plan
            
        Raises:
            ValueError: If the session is not found or required data is missing
            
        Validates: Requirements 5.1, 5.2
        """
        correlation_id = get_correlation_id() or set_correlation_id()
        
        logger.info(
            "Generating completion summary",
            extra={
                'extra_fields': {
                    'event': 'onboarding_summary_generation_started',
                    'user_id': str(user_id),
                    'correlation_id': correlation_id
                }
            }
        )
        
        # Get the onboarding session
        session = await self.get_session(user_id)
        if not session:
            logger.error(
                "Cannot generate summary - session not found",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_summary_failed',
                        'user_id': str(user_id),
                        'reason': 'session_not_found',
                        'correlation_id': correlation_id
                    }
                }
            )
            raise ValueError(f"No onboarding session found for user {user_id}")
        
        # Validate required data
        if not session.project_name or not session.project_goal:
            logger.error(
                "Cannot generate summary - missing required data",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_summary_failed',
                        'user_id': str(user_id),
                        'reason': 'missing_required_data',
                        'correlation_id': correlation_id
                    }
                }
            )
            raise ValueError("Project name and goal are required to generate summary")
        
        # Get user data
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(
                "Cannot generate summary - user not found",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_summary_failed',
                        'user_id': str(user_id),
                        'reason': 'user_not_found',
                        'correlation_id': correlation_id
                    }
                }
            )
            raise ValueError(f"User {user_id} not found")
        
        # Create a temporary project object for decomposition
        # This project is not persisted to the database yet
        temp_project = Project(
            user_id=user_id,
            title=session.project_name,
            description=session.project_goal,
            goal=session.project_goal,
            target_completion_date=session.deadline,
            project_tone=session.preferred_tone,
            status="active"
        )
        
        try:
            # Call llm_service.decompose_project() to get tasks
            logger.info(
                "Calling LLM to decompose project",
                extra={
                    'extra_fields': {
                        'user_id': str(user_id),
                        'project_name': session.project_name,
                        'correlation_id': correlation_id
                    }
                }
            )
            
            tasks = await llm_service.decompose_project(user, temp_project)
            
            logger.info(
                "Project decomposed successfully",
                extra={
                    'extra_fields': {
                        'user_id': str(user_id),
                        'task_count': len(tasks),
                        'correlation_id': correlation_id
                    }
                }
            )
            
        except Exception as e:
            logger.error(
                "Failed to decompose project",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_summary_decomposition_failed',
                        'user_id': str(user_id),
                        'error': str(e),
                        'correlation_id': correlation_id
                    }
                },
                exc_info=True
            )
            # Fall back to a simple summary without task breakdown
            return self._generate_simple_summary(session)
        
        # Format the summary
        summary = self._format_completion_summary(session, tasks)
        
        logger.info(
            "Completion summary generated",
            extra={
                'extra_fields': {
                    'event': 'onboarding_summary_generated',
                    'user_id': str(user_id),
                    'summary_length': len(summary),
                    'correlation_id': correlation_id
                }
            }
        )
        
        metrics.increment('onboarding_summaries_generated')
        
        return summary
    
    def _format_completion_summary(
        self,
        session: OnboardingSession,
        tasks: list[Dict[str, Any]]
    ) -> str:
        """
        Format a comprehensive completion summary with preferences and project plan.
        
        Args:
            session: The onboarding session with collected data
            tasks: List of task dictionaries from decompose_project
            
        Returns:
            str: Formatted summary message
        """
        # Calculate total estimated hours
        total_hours = sum(task.get('estimated_duration_hours', 0) for task in tasks)
        
        # Format deadline if present
        deadline_text = ""
        if session.deadline:
            deadline_text = f"**Target Completion:** {session.deadline.strftime('%B %d, %Y')}\n"
        
        # Format tone preference
        tone_text = session.preferred_tone or "supportive"
        
        # Format check-in frequency
        checkin_text = session.checkin_frequency or "regularly"
        
        # Build the summary header
        summary = f"""🎉 **Great! Here's your project plan for '{session.project_name}'**

**Your Preferences:**
• Communication style: {tone_text}
• Check-in frequency: {checkin_text}
{deadline_text}
**Project Goal:** {session.project_goal}

**📋 Your Action Plan ({len(tasks)} tasks, ~{total_hours} hours total):**

"""
        
        # Add each task
        for i, task in enumerate(tasks, 1):
            title = task.get('title', f'Task {i}')
            description = task.get('description', '')
            hours = task.get('estimated_duration_hours', 0)
            
            summary += f"{i}. **{title}** (~{hours}h)\n"
            if description:
                summary += f"   {description}\n"
            summary += "\n"
        
        # Add closing message
        summary += f"""**What's Next?**
I'll check in with you {checkin_text} to see how you're progressing. You can always message me if you need help, want to update your project, or just need some accountability!

Ready to get started? Just confirm and I'll create your project! 💪"""
        
        return summary
    
    def _generate_simple_summary(self, session: OnboardingSession) -> str:
        """
        Generate a simple summary without task breakdown (fallback).
        
        Args:
            session: The onboarding session with collected data
            
        Returns:
            str: Simple formatted summary message
        """
        # Format deadline if present
        deadline_text = ""
        if session.deadline:
            deadline_text = f"**Target Completion:** {session.deadline.strftime('%B %d, %Y')}\n"
        
        # Format tone preference
        tone_text = session.preferred_tone or "supportive"
        
        # Format check-in frequency
        checkin_text = session.checkin_frequency or "regularly"
        
        summary = f"""🎉 **Great! Here's your project setup for '{session.project_name}'**

**Your Preferences:**
• Communication style: {tone_text}
• Check-in frequency: {checkin_text}
{deadline_text}
**Project Goal:** {session.project_goal}

**What's Next?**
I'll check in with you {checkin_text} to see how you're progressing. You can always message me if you need help, want to update your project, or just need some accountability!

Ready to get started? Just confirm and I'll create your project! 💪"""
        
        return summary
    
    async def process_message_with_state_logic(
        self,
        user_id: UUID,
        message: str
    ) -> Dict[str, Any]:
        """
        Process a user message with state-based logic.
        
        This method:
        1. Parses user input based on current onboarding state
        2. Extracts relevant data (project name, goal, deadline, tone, frequency)
        3. Validates extracted data using input validators
        4. Updates session with extracted data
        5. Determines next state based on current state and input
        6. Transitions to next state
        7. Generates LLM response for next question
        8. Handles validation errors with clarifying questions
        
        Args:
            user_id: UUID of the user
            message: The user's message
            
        Returns:
            Dict with 'reply', 'current_state', and 'validation_passed' keys
            
        Raises:
            ValueError: If the session is not found
            
        Validates: Requirements 2.1, 3.1, 3.2, 8.1, 8.2
        """
        from app.services.input_validators import (
            validate_project_name,
            validate_project_goal,
            DateParser,
            DeadlineValidator,
            ToneValidator,
            CheckinFrequencyParser,
            AmbiguityDetector
        )
        from app.models.onboarding_session import OnboardingState
        
        correlation_id = get_correlation_id() or set_correlation_id()
        
        # Get the session
        session = await self.get_session(user_id)
        if not session:
            raise ValueError(f"No onboarding session found for user {user_id}")
        
        current_state = session.current_state
        
        logger.info(
            "Processing message with state-based logic",
            extra={'extra_fields': {
                'user_id': str(user_id),
                'current_state': current_state.value,
                'correlation_id': correlation_id
            }}
        )
        
        # First, add the user message to conversation history
        await self.process_message(user_id, message)
        
        # Refresh session to get updated conversation history
        self.db.refresh(session)
        
        # State-based processing
        validation_passed = True
        next_state = None
        extracted_data = {}
        error_message = None
        
        # Process based on current state
        if current_state == OnboardingState.WELCOME:
            # User is responding to welcome - treat as project name
            result = validate_project_name(message)
            if result.is_valid:
                extracted_data['project_name'] = result.value
                # Transition to COLLECT_PROJECT_NAME, then immediately to COLLECT_GOAL
                # This is a two-step transition to comply with state machine
                next_state = OnboardingState.COLLECT_GOAL
                # We'll handle the intermediate state transition separately
                await self.process_message(user_id, "", next_state=OnboardingState.COLLECT_PROJECT_NAME)
            else:
                validation_passed = False
                error_message = result.error_message
                next_state = OnboardingState.COLLECT_PROJECT_NAME
        
        elif current_state == OnboardingState.COLLECT_PROJECT_NAME:
            result = validate_project_name(message)
            if result.is_valid:
                extracted_data['project_name'] = result.value
                next_state = OnboardingState.COLLECT_GOAL
            else:
                validation_passed = False
                error_message = result.error_message
                # Stay in same state
                next_state = OnboardingState.COLLECT_PROJECT_NAME
        
        elif current_state == OnboardingState.COLLECT_GOAL:
            result = validate_project_goal(message)
            if result.is_valid:
                extracted_data['project_goal'] = result.value
                next_state = OnboardingState.COLLECT_DEADLINE
            else:
                validation_passed = False
                error_message = result.error_message
                # Stay in same state
                next_state = OnboardingState.COLLECT_GOAL
        
        elif current_state == OnboardingState.COLLECT_DEADLINE:
            # Parse the date
            parse_result = DateParser.parse(message)
            if parse_result.is_valid:
                # Validate the deadline
                validation_result = DeadlineValidator.validate(parse_result.value)
                if validation_result.is_valid:
                    extracted_data['deadline'] = validation_result.value
                    
                    # Always go to CONFIRM_DEADLINE after collecting a deadline
                    # The state machine requires this transition
                    next_state = OnboardingState.CONFIRM_DEADLINE
                else:
                    validation_passed = False
                    error_message = validation_result.error_message
                    next_state = OnboardingState.COLLECT_DEADLINE
            else:
                validation_passed = False
                error_message = parse_result.error_message
                next_state = OnboardingState.COLLECT_DEADLINE
        
        elif current_state == OnboardingState.CONFIRM_DEADLINE:
            # User is confirming or rejecting the deadline
            message_lower = message.strip().lower()
            if message_lower in ['yes', 'y', 'correct', 'yep', 'yeah', 'sure', 'ok', 'okay']:
                # Deadline confirmed, move to next step
                next_state = OnboardingState.COLLECT_CHECKIN_FREQUENCY
            elif message_lower in ['no', 'n', 'nope', 'incorrect', 'wrong']:
                # User wants to re-enter deadline
                next_state = OnboardingState.COLLECT_DEADLINE
                error_message = "No problem! Please provide your deadline again."
            else:
                # Try to parse as a new deadline
                parse_result = DateParser.parse(message)
                if parse_result.is_valid:
                    validation_result = DeadlineValidator.validate(parse_result.value)
                    if validation_result.is_valid:
                        extracted_data['deadline'] = validation_result.value
                        next_state = OnboardingState.COLLECT_CHECKIN_FREQUENCY
                    else:
                        validation_passed = False
                        error_message = validation_result.error_message
                        next_state = OnboardingState.COLLECT_DEADLINE
                else:
                    validation_passed = False
                    error_message = "Please answer 'yes' to confirm or provide a different deadline."
                    next_state = OnboardingState.CONFIRM_DEADLINE
        
        elif current_state == OnboardingState.COLLECT_CHECKIN_FREQUENCY:
            result = CheckinFrequencyParser.parse(message)
            if result.is_valid:
                extracted_data['checkin_frequency'] = result.value
                next_state = OnboardingState.COLLECT_TONE
            else:
                validation_passed = False
                error_message = result.error_message
                next_state = OnboardingState.COLLECT_CHECKIN_FREQUENCY
        
        elif current_state == OnboardingState.COLLECT_TONE:
            result = ToneValidator.validate(message)
            if result.is_valid:
                extracted_data['preferred_tone'] = result.value
                next_state = OnboardingState.CONFIRM_DETAILS
            else:
                validation_passed = False
                error_message = result.error_message
                next_state = OnboardingState.COLLECT_TONE
        
        elif current_state == OnboardingState.CONFIRM_DETAILS:
            # User is confirming or requesting changes
            message_lower = message.strip().lower()
            if message_lower in ['yes', 'y', 'correct', 'looks good', 'confirm', 'yep', 'yeah', 'sure', 'ok', 'okay']:
                # User confirmed - create the project and show plan with milestones
                try:
                    project = await self.complete_onboarding(user_id)
                    
                    # Generate milestones for the project
                    from app.services.project_plan_service import ProjectPlanService
                    from app.services.discord_project_plan_formatter import DiscordProjectPlanFormatter
                    
                    plan_service = ProjectPlanService(self.db)
                    formatter = DiscordProjectPlanFormatter()
                    
                    # Get or generate milestones
                    project_plan = await plan_service.get_project_plan(user_id, str(project.id))
                    
                    # Format the project plan for Discord
                    formatted_messages = formatter.format_project_plan(
                        project_plan['project'],
                        project_plan['milestones'],
                        include_completed=False
                    )
                    
                    # Combine with completion message
                    completion_message = (
                        f"🎉 **Awesome! Your project '{project.title}' is all set up!**\n\n"
                        f"I'll check in with you {session.checkin_frequency or 'regularly'} to see how you're progressing. "
                        f"You can always message me if you need help or want to update your project.\n\n"
                        f"Let's make this happen! 💪\n\n"
                    )
                    
                    # Add the project plan
                    full_message = completion_message + "\n".join(formatted_messages)
                    
                    return {
                        'reply': full_message,
                        'current_state': OnboardingState.COMPLETED.value,
                        'validation_passed': True
                    }
                except Exception as e:
                    logger.error(f"Failed to complete onboarding: {e}", exc_info=True)
                    error_message = (
                        "I encountered an error creating your project. "
                        "Let me try again, or you can type 'help' for assistance."
                    )
                    validation_passed = False
                    next_state = OnboardingState.CONFIRM_DETAILS
            else:
                # User wants to make changes - for now, send them back to start
                # In a more sophisticated implementation, we could parse what they want to change
                error_message = (
                    "No problem! What would you like to change? "
                    "You can type 'restart' to start over, or tell me what you'd like to update."
                )
                validation_passed = False
                next_state = OnboardingState.CONFIRM_DETAILS
        
        else:
            # For other states, just generate a response
            logger.warning(f"Unhandled state in state-based processing: {current_state.value}")
            next_state = current_state
        
        # Update session with extracted data
        if extracted_data:
            await self.update_session_data(user_id, **extracted_data)
            
            logger.info(
                "Updated session data",
                extra={'extra_fields': {
                    'user_id': str(user_id),
                    'extracted_fields': list(extracted_data.keys()),
                    'correlation_id': correlation_id
                }}
            )
        
        # Transition to next state if different from current
        if next_state and next_state != current_state:
            await self.process_message(user_id, "", next_state=next_state)
            
            logger.info(
                "State transition completed",
                extra={'extra_fields': {
                    'user_id': str(user_id),
                    'from_state': current_state.value,
                    'to_state': next_state.value,
                    'correlation_id': correlation_id
                }}
            )
        
        # Generate response
        if not validation_passed and error_message:
            # Return error message with clarification
            response = error_message
        else:
            # Generate LLM response for next question
            response = await self.generate_response(user_id)
        
        # Get updated session state
        updated_session = await self.get_session(user_id)
        final_state = updated_session.current_state.value if updated_session else current_state.value
        
        return {
            'reply': response,
            'current_state': final_state,
            'validation_passed': validation_passed
        }
    
    async def generate_response(
        self,
        user_id: UUID,
        tone: Optional[str] = None,
        acknowledge_user_input: bool = True
    ) -> str:
        """
        Generate a conversational response for the current onboarding state.
        
        Enhanced to use state-specific prompts, include collected data in context,
        generate acknowledgments for user responses, generate clarifying questions
        for ambiguous inputs, and maintain conversational tone throughout.
        
        Uses the LLM service to generate natural, contextual responses based on
        the current state and conversation history.
        
        Args:
            user_id: UUID of the user
            tone: Optional tone override (defaults to session's preferred_tone or 'supportive')
            acknowledge_user_input: Whether to acknowledge the user's previous response
            
        Returns:
            str: The generated response message
            
        Raises:
            ValueError: If the session is not found
            
        Validates: Requirements 8.1, 8.2, 8.3, 8.4
        """
        session = await self.get_session(user_id)
        if not session:
            raise ValueError(f"No onboarding session found for user {user_id}")
        
        # Determine tone
        effective_tone = tone or session.preferred_tone or "supportive"
        
        # Collect data for context
        collected_data = {
            'project_name': session.project_name,
            'project_goal': session.project_goal,
            'deadline': session.deadline.strftime("%B %d, %Y") if session.deadline else None,
            'checkin_frequency': session.checkin_frequency,
            'preferred_tone': session.preferred_tone,
        }
        
        # Get the last user message for acknowledgment
        last_user_message = None
        if session.conversation_history:
            for msg in reversed(session.conversation_history):
                if msg.get('role') == 'user':
                    last_user_message = msg.get('message', '')
                    break
        
        # Build state-specific context and instructions
        state_context = self._build_state_specific_context(
            session.current_state,
            collected_data,
            last_user_message,
            acknowledge_user_input
        )
        
        # Generate response using enhanced LLM service call
        try:
            response = await llm_service.generate_onboarding_message(
                current_state=session.current_state.value,
                conversation_history=session.conversation_history or [],
                tone=effective_tone,
                collected_data=collected_data,
                state_context=state_context,
                acknowledge_input=acknowledge_user_input
            )
        except Exception as e:
            # If LLM fails, fall back to templates
            logger.error(
                f"Failed to generate onboarding response via LLM, using fallback: {e}",
                extra={
                    'extra_fields': {
                        'user_id': str(user_id),
                        'state': session.current_state.value,
                        'error': str(e)
                    }
                }
            )
            # Use template-based fallback
            from app.services.onboarding_templates import OnboardingTemplates
            template_vars = collected_data or {}
            response = OnboardingTemplates.get_message(
                state=session.current_state,
                tone=effective_tone,
                **template_vars
            )
        
        # Add bot response to conversation history
        bot_message = {
            "timestamp": datetime.utcnow().isoformat(),
            "role": "assistant",
            "message": response
        }
        
        if session.conversation_history is None:
            session.conversation_history = []
        
        session.conversation_history.append(bot_message)
        
        # Mark conversation_history as modified so SQLAlchemy tracks the change
        flag_modified(session, "conversation_history")
        
        session.last_activity_at = datetime.utcnow()
        
        try:
            self.db.commit()
            self.db.refresh(session)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save bot response to conversation history: {e}")
            # Don't raise - we still want to return the response
        
        return response
    
    def _build_state_specific_context(
        self,
        state: OnboardingState,
        collected_data: Dict[str, Any],
        last_user_message: Optional[str],
        acknowledge_input: bool
    ) -> Dict[str, Any]:
        """
        Build state-specific context for response generation.
        
        This method creates detailed context for each onboarding state, including:
        - What data has been collected so far
        - What the next question should be
        - How to acknowledge the user's previous response
        - What clarifications might be needed
        
        Args:
            state: Current onboarding state
            collected_data: Data collected so far
            last_user_message: The user's last message
            acknowledge_input: Whether to acknowledge the user's input
            
        Returns:
            Dict with state-specific context information
        """
        context = {
            'state': state.value,
            'collected_data': collected_data,
            'last_user_message': last_user_message,
            'acknowledge_input': acknowledge_input
        }
        
        # State-specific instructions
        if state == OnboardingState.WELCOME:
            context['instructions'] = (
                "This is the welcome message. Warmly greet the user and explain "
                "that you'll help them set up their first project. Ask what they'd "
                "like to work on."
            )
            context['acknowledge_needed'] = False
            
        elif state == OnboardingState.COLLECT_PROJECT_NAME:
            context['instructions'] = (
                "Ask the user what they'd like to call their project. "
                "Keep it simple and encouraging."
            )
            if acknowledge_input and last_user_message:
                context['acknowledgment_hint'] = (
                    "Acknowledge their interest in starting a project before asking for the name."
                )
            
        elif state == OnboardingState.COLLECT_GOAL:
            context['instructions'] = (
                f"The user named their project '{collected_data.get('project_name', 'their project')}'. "
                "Acknowledge this positively, then ask what main goal they want to achieve. "
                "Ask what success looks like for them."
            )
            context['acknowledge_needed'] = True
            context['acknowledgment_hint'] = (
                f"Compliment the project name '{collected_data.get('project_name', '')}' "
                "before asking about the goal."
            )
            
        elif state == OnboardingState.COLLECT_DEADLINE:
            context['instructions'] = (
                "The user has shared their project goal. Acknowledge it positively, "
                "then ask when they'd like to complete this project. "
                "Mention they can use natural language like 'in 2 weeks' or specific dates like 'December 31'."
            )
            context['acknowledge_needed'] = True
            context['acknowledgment_hint'] = (
                "Express enthusiasm about their goal before asking about the deadline."
            )
            
        elif state == OnboardingState.CONFIRM_DEADLINE:
            deadline_str = collected_data.get('deadline', 'the specified date')
            context['instructions'] = (
                f"Confirm with the user that they want to complete this by {deadline_str}. "
                "Ask them to confirm with yes/no."
            )
            context['acknowledge_needed'] = False
            
        elif state == OnboardingState.COLLECT_CHECKIN_FREQUENCY:
            context['instructions'] = (
                "Ask the user how often they'd like you to check in with them. "
                "Provide examples: daily, every 2 days, weekly, etc. "
                "Make it clear they can choose what works best for them."
            )
            if acknowledge_input:
                context['acknowledgment_hint'] = (
                    "Acknowledge that the deadline is set before asking about check-in frequency."
                )
            
        elif state == OnboardingState.COLLECT_TONE:
            context['instructions'] = (
                "Ask the user what communication style they prefer. "
                "Present the options clearly:\n"
                "• supportive - Encouraging and empathetic\n"
                "• direct - Straightforward and efficient\n"
                "• casual - Friendly and relaxed\n"
                "• drill_sergeant - No-nonsense and intense\n"
                "Ask which one feels right for them."
            )
            if acknowledge_input:
                context['acknowledgment_hint'] = (
                    "Acknowledge their check-in preference before asking about communication style."
                )
            
        elif state == OnboardingState.CONFIRM_DETAILS:
            # Build a summary of all collected data
            summary_parts = []
            if collected_data.get('project_name'):
                summary_parts.append(f"**Project:** {collected_data['project_name']}")
            if collected_data.get('project_goal'):
                summary_parts.append(f"**Goal:** {collected_data['project_goal']}")
            if collected_data.get('deadline'):
                summary_parts.append(f"**Deadline:** {collected_data['deadline']}")
            if collected_data.get('checkin_frequency'):
                summary_parts.append(f"**Check-ins:** {collected_data['checkin_frequency']}")
            if collected_data.get('preferred_tone'):
                summary_parts.append(f"**Tone:** {collected_data['preferred_tone']}")
            
            summary = "\n".join(summary_parts)
            
            context['instructions'] = (
                "Show the user a summary of all collected information and ask them "
                "to confirm it looks correct. Use this summary:\n\n"
                f"{summary}\n\n"
                "Ask them to confirm with yes/no."
            )
            if acknowledge_input:
                context['acknowledgment_hint'] = (
                    "Acknowledge their tone preference before showing the summary."
                )
            
        elif state == OnboardingState.SHOW_SUMMARY:
            context['instructions'] = (
                "The user is reviewing the project plan summary. "
                "This message should have already been generated by generate_completion_summary(). "
                "If you're generating a follow-up, ask them to confirm if they're ready to proceed."
            )
            context['acknowledge_needed'] = False
            
        elif state == OnboardingState.CREATING_PROJECT:
            context['instructions'] = (
                "The project is being created. Let the user know you're setting things up."
            )
            context['acknowledge_needed'] = False
            
        elif state == OnboardingState.COMPLETED:
            context['instructions'] = (
                "Onboarding is complete. This message should have already been generated. "
                "If generating a follow-up, welcome them and let them know you're ready to help."
            )
            context['acknowledge_needed'] = False
            
        elif state == OnboardingState.PAUSED:
            context['instructions'] = (
                "The onboarding is paused. Let the user know they can resume anytime "
                "by sending a message."
            )
            context['acknowledge_needed'] = False
            
        elif state == OnboardingState.FAILED:
            context['instructions'] = (
                "There was an error. Apologize and offer to help them restart or "
                "contact support."
            )
            context['acknowledge_needed'] = False
        
        return context
    
    async def get_inactive_sessions(self, hours: int = 24) -> list[OnboardingSession]:
        """
        Get onboarding sessions that have been inactive for a specified time.
        
        Returns sessions that are not completed, not paused, and haven't had
        activity for the specified number of hours.
        
        Args:
            hours: Number of hours of inactivity to check for (default: 24)
            
        Returns:
            list[OnboardingSession]: List of inactive sessions
            
        Validates: Requirements 6.3
        """
        from datetime import timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        inactive_sessions = self.db.query(OnboardingSession).filter(
            OnboardingSession.current_state.notin_([
                OnboardingState.COMPLETED,
                OnboardingState.PAUSED,
                OnboardingState.FAILED
            ]),
            OnboardingSession.last_activity_at < cutoff_time
        ).all()
        
        logger.info(
            f"Found {len(inactive_sessions)} inactive sessions "
            f"(inactive for {hours}+ hours)"
        )
        
        return inactive_sessions
    
    async def mark_abandoned_sessions(self, days: int = 7) -> int:
        """
        Mark onboarding sessions as abandoned after a specified number of days.
        
        Sessions that have been inactive for the specified number of days
        and are not already completed or failed will be marked as FAILED
        with an appropriate error message.
        
        Args:
            days: Number of days of inactivity before marking as abandoned (default: 7)
            
        Returns:
            int: Number of sessions marked as abandoned
            
        Validates: Requirements 6.5
        """
        from datetime import timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        abandoned_sessions = self.db.query(OnboardingSession).filter(
            OnboardingSession.current_state.notin_([
                OnboardingState.COMPLETED,
                OnboardingState.FAILED
            ]),
            OnboardingSession.last_activity_at < cutoff_time
        ).all()
        
        count = 0
        for session in abandoned_sessions:
            try:
                session.current_state = OnboardingState.FAILED
                session.error_message = f"Session abandoned after {days} days of inactivity"
                session.updated_at = datetime.utcnow()
                
                logger.info(
                    "Marked onboarding session as abandoned",
                    extra={
                        'extra_fields': {
                            'event': 'onboarding_session_abandoned',
                            'session_id': str(session.id),
                            'user_id': str(session.user_id),
                            'days_inactive': days,
                            'last_activity': session.last_activity_at.isoformat()
                        }
                    }
                )
                
                count += 1
                
            except Exception as e:
                logger.error(
                    f"Error marking session {session.id} as abandoned: {e}",
                    extra={
                        'extra_fields': {
                            'session_id': str(session.id),
                            'error': str(e)
                        }
                    },
                    exc_info=True
                )
        
        if count > 0:
            try:
                self.db.commit()
                logger.info(f"Marked {count} sessions as abandoned")
                metrics.increment('onboarding_sessions_abandoned', {'count': str(count)})
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to commit abandoned sessions: {e}", exc_info=True)
                raise
        
        return count
    
    async def archive_old_sessions(self, days: int = 30) -> int:
        """
        Archive old onboarding sessions after a specified number of days.
        
        For now, this marks sessions as archived by updating their state.
        In a production system, this might move data to cold storage or
        a separate archive table.
        
        Args:
            days: Number of days before archiving (default: 30)
            
        Returns:
            int: Number of sessions archived
            
        Validates: Requirements 6.5
        """
        from datetime import timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        # Find sessions that are completed or failed and old enough to archive
        old_sessions = self.db.query(OnboardingSession).filter(
            OnboardingSession.current_state.in_([
                OnboardingState.COMPLETED,
                OnboardingState.FAILED
            ]),
            OnboardingSession.updated_at < cutoff_time
        ).all()
        
        count = 0
        for session in old_sessions:
            try:
                # For now, we'll just log the archival
                # In production, you might move this to a separate archive table
                # or cold storage
                logger.info(
                    "Archiving old onboarding session",
                    extra={
                        'extra_fields': {
                            'event': 'onboarding_session_archived',
                            'session_id': str(session.id),
                            'user_id': str(session.user_id),
                            'final_state': session.current_state.value,
                            'age_days': (datetime.utcnow() - session.updated_at).days
                        }
                    }
                )
                
                # Mark as archived by adding a note to error_message
                if session.error_message:
                    session.error_message += f" | Archived on {datetime.utcnow().isoformat()}"
                else:
                    session.error_message = f"Archived on {datetime.utcnow().isoformat()}"
                
                session.updated_at = datetime.utcnow()
                
                count += 1
                
            except Exception as e:
                logger.error(
                    f"Error archiving session {session.id}: {e}",
                    extra={
                        'extra_fields': {
                            'session_id': str(session.id),
                            'error': str(e)
                        }
                    },
                    exc_info=True
                )
        
        if count > 0:
            try:
                self.db.commit()
                logger.info(f"Archived {count} old sessions")
                metrics.increment('onboarding_sessions_archived', {'count': str(count)})
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to commit archived sessions: {e}", exc_info=True)
                raise
        
        return count
    
    async def send_reminder(self, user_id: UUID) -> bool:
        """
        Send a reminder DM to a user with an inactive onboarding session.
        
        Generates a gentle reminder message based on the current state and
        sends it via the Discord bot.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            bool: True if reminder was sent successfully, False otherwise
            
        Validates: Requirements 6.3
        """
        session = await self.get_session(user_id)
        if not session:
            logger.warning(f"No active session found for user {user_id} when sending reminder")
            return False
        
        # Get user to find Discord ID
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.discord_user_id:
            logger.warning(f"User {user_id} not found or has no Discord ID")
            return False
        
        # Generate reminder message based on current state
        reminder_message = self._generate_reminder_message(session)
        
        # Send reminder via Discord bot
        try:
            import httpx
            from app.core.config import settings
            
            discord_bot_url = settings.DISCORD_BOT_API_URL if hasattr(settings, 'DISCORD_BOT_API_URL') else "http://discord-bot:8001"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{discord_bot_url}/send-dm",
                    json={
                        "discord_user_id": user.discord_user_id,
                        "message": reminder_message
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    success = data.get("success", False)
                    
                    if success:
                        logger.info(
                            f"Reminder sent successfully to user {user_id}",
                            extra={'extra_fields': {
                                'user_id': str(user_id),
                                'discord_user_id': user.discord_user_id
                            }}
                        )
                        
                        # Update last_activity_at to track that we sent a reminder
                        session.last_activity_at = datetime.utcnow()
                        self.db.commit()
                        
                        return True
                    else:
                        logger.warning(
                            f"Failed to send reminder to user {user_id}: {data.get('reason', 'unknown')}",
                            extra={'extra_fields': {
                                'user_id': str(user_id),
                                'reason': data.get('reason', 'unknown')
                            }}
                        )
                        return False
                else:
                    logger.error(
                        f"Discord bot API error when sending reminder: {response.status_code}",
                        extra={'extra_fields': {
                            'user_id': str(user_id),
                            'status_code': response.status_code
                        }}
                    )
                    return False
                    
        except Exception as e:
            logger.error(
                f"Error sending reminder to user {user_id}: {e}",
                extra={'extra_fields': {
                    'user_id': str(user_id),
                    'error': str(e)
                }},
                exc_info=True
            )
            return False
    
    def _generate_reminder_message(self, session: OnboardingSession) -> str:
        """
        Generate a reminder message based on the current onboarding state.
        
        Args:
            session: The onboarding session
            
        Returns:
            str: The reminder message
        """
        state_messages = {
            OnboardingState.WELCOME: (
                "👋 Hey there! I noticed we started setting up your accountability assistant, "
                "but we didn't finish. No worries - we can pick up right where we left off!\n\n"
                "**What project would you like to work on?**"
            ),
            OnboardingState.COLLECT_PROJECT_NAME: (
                "Hi! Just checking in - we were setting up your first project. "
                "Whenever you're ready, just tell me the name of your project and we'll continue!"
            ),
            OnboardingState.COLLECT_GOAL: (
                f"Hey! We started setting up **{session.project_name}** but didn't finish. "
                "When you have a moment, tell me what you're hoping to achieve with this project!"
            ),
            OnboardingState.COLLECT_DEADLINE: (
                f"Hi! We're almost done setting up **{session.project_name}**. "
                "Just need to know - when would you like to complete this project by?"
            ),
            OnboardingState.COLLECT_CHECKIN_FREQUENCY: (
                "Hey! We're making great progress. Just need to know how often you'd like me to check in with you. "
                "Would you prefer daily, every 2-3 days, or weekly check-ins?"
            ),
            OnboardingState.COLLECT_TONE: (
                "Almost there! Last question - what communication style works best for you? "
                "I can be supportive like a coach, direct like a manager, casual like a buddy, or firm like a drill sergeant."
            ),
        }
        
        # Get message for current state, or use a generic one
        message = state_messages.get(
            session.current_state,
            "Hi! Just checking in - we were setting up your accountability assistant. "
            "Whenever you're ready, just send me a message and we'll continue where we left off!"
        )
        
        return message
    
    def is_command(self, message: str) -> bool:
        """
        Check if a message is a command.
        
        Args:
            message: The user's message
            
        Returns:
            bool: True if the message is a command, False otherwise
        """
        message_lower = message.strip().lower()
        commands = ['help', 'cancel', 'stop', 'restart']
        return message_lower in commands
    
    async def handle_command(self, user_id: UUID, command: str) -> str:
        """
        Handle a command during onboarding.
        
        Processes commands like help, cancel, stop, and restart.
        
        Args:
            user_id: UUID of the user
            command: The command to handle
            
        Returns:
            str: Response message for the command
            
        Raises:
            ValueError: If the session is not found or command is invalid
            
        Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5
        """
        correlation_id = get_correlation_id() or set_correlation_id()
        command_lower = command.strip().lower()
        
        logger.info(
            "Processing onboarding command",
            extra={
                'extra_fields': {
                    'event': 'onboarding_command_received',
                    'user_id': str(user_id),
                    'command': command_lower,
                    'correlation_id': correlation_id
                }
            }
        )
        
        metrics.increment('onboarding_commands', {'command': command_lower})
        
        session = await self.get_session(user_id)
        if not session:
            logger.error(
                "Cannot process command - session not found",
                extra={
                    'extra_fields': {
                        'event': 'onboarding_command_failed',
                        'user_id': str(user_id),
                        'command': command_lower,
                        'reason': 'session_not_found',
                        'correlation_id': correlation_id
                    }
                }
            )
            raise ValueError(f"No onboarding session found for user {user_id}")
        
        if command_lower == 'help':
            return await self._handle_help_command(session)
        elif command_lower in ['cancel', 'stop']:
            return await self._handle_cancel_command(user_id, session)
        elif command_lower == 'restart':
            return await self._handle_restart_command(user_id, session)
        else:
            logger.warning(
                f"Unknown command: {command_lower}",
                extra={
                    'extra_fields': {
                        'user_id': str(user_id),
                        'command': command_lower,
                        'correlation_id': correlation_id
                    }
                }
            )
            return (
                f"I don't recognize the command '{command}'. "
                "Available commands: **help**, **cancel**, **stop**, **restart**"
            )
    
    async def _handle_help_command(self, session: OnboardingSession) -> str:
        """
        Handle the 'help' command with contextual help based on current state.
        
        Args:
            session: The onboarding session
            
        Returns:
            str: Contextual help message
            
        Validates: Requirements 9.5
        """
        logger.info(
            f"Providing help for user {session.user_id} in state {session.current_state.value}"
        )
        
        # Base help message
        base_help = (
            "**Available Commands:**\n"
            "• **help** - Show this help message\n"
            "• **cancel** or **stop** - Pause the onboarding process\n"
            "• **restart** - Start over from the beginning\n\n"
        )
        
        # Contextual help based on current state
        state_help = {
            OnboardingState.WELCOME: (
                "**Current Step:** Getting Started\n"
                "I'm here to help you set up your first project! "
                "Just tell me the name of the project you'd like to work on.\n\n"
                "**Example:** \"Website redesign\" or \"Learn Python\""
            ),
            OnboardingState.COLLECT_PROJECT_NAME: (
                "**Current Step:** Project Name\n"
                "Please tell me the name of your project. Keep it short and descriptive.\n\n"
                "**Example:** \"Website redesign\" or \"Learn Python\""
            ),
            OnboardingState.COLLECT_GOAL: (
                "**Current Step:** Project Goal\n"
                "What are you hoping to achieve with this project? "
                "Describe your goal in a sentence or two.\n\n"
                "**Example:** \"Build a responsive website for my business\" or "
                "\"Complete a Python course and build 3 projects\""
            ),
            OnboardingState.COLLECT_DEADLINE: (
                "**Current Step:** Deadline\n"
                "When would you like to complete this project? "
                "You can use natural language or specific dates.\n\n"
                "**Examples:**\n"
                "• \"in 2 weeks\"\n"
                "• \"by December 31\"\n"
                "• \"March 15, 2024\"\n"
                "• \"next Friday\""
            ),
            OnboardingState.CONFIRM_DEADLINE: (
                "**Current Step:** Confirm Deadline\n"
                "Please confirm if the deadline I understood is correct. "
                "Reply with **yes** to confirm or provide a different date."
            ),
            OnboardingState.COLLECT_CHECKIN_FREQUENCY: (
                "**Current Step:** Check-in Frequency\n"
                "How often would you like me to check in with you about your progress?\n\n"
                "**Options:**\n"
                "• **daily** - Every day\n"
                "• **every 2-3 days** - A few times per week\n"
                "• **weekly** - Once a week"
            ),
            OnboardingState.COLLECT_TONE: (
                "**Current Step:** Communication Tone\n"
                "What communication style works best for you?\n\n"
                "**Options:**\n"
                "• **supportive** - Encouraging and understanding (like a coach)\n"
                "• **direct** - Straightforward and to the point (like a manager)\n"
                "• **casual** - Friendly and relaxed (like a buddy)\n"
                "• **firm** - Strict and disciplined (like a drill sergeant)"
            ),
            OnboardingState.CONFIRM_DETAILS: (
                "**Current Step:** Confirm Details\n"
                "Please review the information you've provided and confirm it's correct. "
                "Reply with **yes** to create your project, or tell me what you'd like to change."
            ),
            OnboardingState.PAUSED: (
                "**Current Step:** Paused\n"
                "Your onboarding is currently paused. "
                "You can **restart** to begin again, or just send me a message to resume where you left off."
            ),
        }
        
        contextual_help = state_help.get(
            session.current_state,
            "**Current Step:** Setting up your project\n"
            "Just respond to my questions and I'll guide you through the setup process."
        )
        
        return base_help + contextual_help
    
    async def _handle_cancel_command(self, user_id: UUID, session: OnboardingSession) -> str:
        """
        Handle the 'cancel' or 'stop' command.
        
        Args:
            user_id: UUID of the user
            session: The onboarding session
            
        Returns:
            str: Cancellation confirmation message
            
        Validates: Requirements 9.1, 9.2
        """
        logger.info(
            f"Cancelling onboarding for user {user_id}",
            extra={
                'extra_fields': {
                    'user_id': str(user_id),
                    'session_id': str(session.id),
                    'current_state': session.current_state.value
                }
            }
        )
        
        # Cancel the onboarding
        await self.cancel_onboarding(user_id)
        
        return (
            "⏸️ **Onboarding Paused**\n\n"
            "No problem! I've paused your onboarding. Your progress has been saved.\n\n"
            "**What would you like to do?**\n"
            "• Send me a message anytime to **resume** where you left off\n"
            "• Type **restart** to start over from the beginning\n"
            "• Type **help** if you need assistance\n\n"
            "Take your time - I'll be here when you're ready!"
        )
    
    async def _handle_restart_command(self, user_id: UUID, session: OnboardingSession) -> str:
        """
        Handle the 'restart' command.
        
        Args:
            user_id: UUID of the user
            session: The onboarding session
            
        Returns:
            str: Restart confirmation message
            
        Validates: Requirements 9.3
        """
        logger.info(
            f"Restarting onboarding for user {user_id}",
            extra={
                'extra_fields': {
                    'user_id': str(user_id),
                    'session_id': str(session.id),
                    'previous_state': session.current_state.value
                }
            }
        )
        
        # Restart the onboarding
        await self.restart_onboarding(user_id)
        
        return (
            "🔄 **Starting Fresh!**\n\n"
            "Alright, let's start over from the beginning. "
            "I've cleared your previous responses.\n\n"
            "**What project would you like to work on?**\n"
            "Just tell me the name of your project, and we'll take it from there!"
        )
