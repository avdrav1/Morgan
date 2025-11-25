"""
Onboarding state machine with transition validation logic.

This module defines the valid state transitions for the Discord DM onboarding flow
and provides validation to ensure state transitions follow the defined rules.
"""

from typing import Dict, Set, Optional
from app.models.onboarding_session import OnboardingState


class OnboardingStateMachine:
    """
    State machine for managing onboarding flow transitions.
    
    Defines valid state transitions and provides validation logic to ensure
    the onboarding flow follows the correct sequence.
    """
    
    # Define valid state transitions
    # Key: current state, Value: set of valid next states
    VALID_TRANSITIONS: Dict[OnboardingState, Set[OnboardingState]] = {
        OnboardingState.WELCOME: {
            OnboardingState.COLLECT_PROJECT_NAME,
            OnboardingState.PAUSED,
            OnboardingState.FAILED,
        },
        OnboardingState.COLLECT_PROJECT_NAME: {
            OnboardingState.COLLECT_GOAL,
            OnboardingState.COLLECT_PROJECT_NAME,  # Stay in same state for invalid input
            OnboardingState.PAUSED,
            OnboardingState.FAILED,
        },
        OnboardingState.COLLECT_GOAL: {
            OnboardingState.COLLECT_DEADLINE,
            OnboardingState.COLLECT_PROJECT_NAME,  # Allow going back
            OnboardingState.COLLECT_GOAL,  # Stay in same state for invalid input
            OnboardingState.PAUSED,
            OnboardingState.FAILED,
        },
        OnboardingState.COLLECT_DEADLINE: {
            OnboardingState.CONFIRM_DEADLINE,
            OnboardingState.COLLECT_DEADLINE,  # Stay in same state for invalid input
            OnboardingState.COLLECT_GOAL,  # Allow going back
            OnboardingState.PAUSED,
            OnboardingState.FAILED,
        },
        OnboardingState.CONFIRM_DEADLINE: {
            OnboardingState.COLLECT_CHECKIN_FREQUENCY,
            OnboardingState.COLLECT_DEADLINE,  # Go back to re-enter deadline
            OnboardingState.PAUSED,
            OnboardingState.FAILED,
        },
        OnboardingState.COLLECT_CHECKIN_FREQUENCY: {
            OnboardingState.COLLECT_TONE,
            OnboardingState.COLLECT_CHECKIN_FREQUENCY,  # Stay in same state for invalid input
            OnboardingState.CONFIRM_DEADLINE,  # Allow going back
            OnboardingState.PAUSED,
            OnboardingState.FAILED,
        },
        OnboardingState.COLLECT_TONE: {
            OnboardingState.CONFIRM_DETAILS,
            OnboardingState.COLLECT_TONE,  # Stay in same state for invalid input
            OnboardingState.COLLECT_CHECKIN_FREQUENCY,  # Allow going back
            OnboardingState.PAUSED,
            OnboardingState.FAILED,
        },
        OnboardingState.CONFIRM_DETAILS: {
            OnboardingState.SHOW_SUMMARY,
            OnboardingState.CREATING_PROJECT,
            OnboardingState.COLLECT_PROJECT_NAME,  # Allow editing from start
            OnboardingState.PAUSED,
            OnboardingState.FAILED,
        },
        OnboardingState.SHOW_SUMMARY: {
            OnboardingState.CREATING_PROJECT,
            OnboardingState.CONFIRM_DETAILS,  # Allow going back to edit
            OnboardingState.PAUSED,
            OnboardingState.FAILED,
        },
        OnboardingState.CREATING_PROJECT: {
            OnboardingState.COMPLETED,
            OnboardingState.FAILED,
            OnboardingState.CREATING_PROJECT,  # Allow retry
        },
        OnboardingState.COMPLETED: {
            OnboardingState.COMPLETED,  # Terminal state - can only stay here
        },
        OnboardingState.PAUSED: {
            OnboardingState.WELCOME,  # Restart from beginning
            OnboardingState.COLLECT_PROJECT_NAME,  # Resume from where paused
            OnboardingState.COLLECT_GOAL,
            OnboardingState.COLLECT_DEADLINE,
            OnboardingState.CONFIRM_DEADLINE,
            OnboardingState.COLLECT_CHECKIN_FREQUENCY,
            OnboardingState.COLLECT_TONE,
            OnboardingState.CONFIRM_DETAILS,
            OnboardingState.SHOW_SUMMARY,
            OnboardingState.PAUSED,  # Can stay paused
        },
        OnboardingState.FAILED: {
            OnboardingState.WELCOME,  # Restart from beginning
            OnboardingState.COLLECT_PROJECT_NAME,  # Retry from where failed
            OnboardingState.COLLECT_GOAL,
            OnboardingState.COLLECT_DEADLINE,
            OnboardingState.CONFIRM_DEADLINE,
            OnboardingState.COLLECT_CHECKIN_FREQUENCY,
            OnboardingState.COLLECT_TONE,
            OnboardingState.CONFIRM_DETAILS,
            OnboardingState.SHOW_SUMMARY,
            OnboardingState.CREATING_PROJECT,
            OnboardingState.FAILED,  # Can stay failed
        },
    }
    
    @classmethod
    def is_valid_transition(
        cls,
        current_state: OnboardingState,
        next_state: OnboardingState
    ) -> bool:
        """
        Check if a state transition is valid.
        
        Args:
            current_state: The current state of the onboarding session
            next_state: The proposed next state
            
        Returns:
            True if the transition is valid, False otherwise
        """
        if current_state not in cls.VALID_TRANSITIONS:
            return False
        
        return next_state in cls.VALID_TRANSITIONS[current_state]
    
    @classmethod
    def get_valid_next_states(
        cls,
        current_state: OnboardingState
    ) -> Set[OnboardingState]:
        """
        Get all valid next states from the current state.
        
        Args:
            current_state: The current state of the onboarding session
            
        Returns:
            Set of valid next states
        """
        return cls.VALID_TRANSITIONS.get(current_state, set())
    
    @classmethod
    def validate_transition(
        cls,
        current_state: OnboardingState,
        next_state: OnboardingState
    ) -> None:
        """
        Validate a state transition and raise an exception if invalid.
        
        Args:
            current_state: The current state of the onboarding session
            next_state: The proposed next state
            
        Raises:
            ValueError: If the transition is not valid
        """
        if not cls.is_valid_transition(current_state, next_state):
            valid_states = cls.get_valid_next_states(current_state)
            raise ValueError(
                f"Invalid state transition from {current_state.value} to {next_state.value}. "
                f"Valid next states: {[s.value for s in valid_states]}"
            )
    
    @classmethod
    def get_initial_state(cls) -> OnboardingState:
        """
        Get the initial state for a new onboarding session.
        
        Returns:
            The initial onboarding state (WELCOME)
        """
        return OnboardingState.WELCOME
    
    @classmethod
    def is_terminal_state(cls, state: OnboardingState) -> bool:
        """
        Check if a state is terminal (no further progression possible).
        
        Args:
            state: The state to check
            
        Returns:
            True if the state is terminal, False otherwise
        """
        return state == OnboardingState.COMPLETED
    
    @classmethod
    def is_error_state(cls, state: OnboardingState) -> bool:
        """
        Check if a state represents an error condition.
        
        Args:
            state: The state to check
            
        Returns:
            True if the state is an error state, False otherwise
        """
        return state == OnboardingState.FAILED
    
    @classmethod
    def is_paused_state(cls, state: OnboardingState) -> bool:
        """
        Check if a state represents a paused session.
        
        Args:
            state: The state to check
            
        Returns:
            True if the state is paused, False otherwise
        """
        return state == OnboardingState.PAUSED
    
    @classmethod
    def can_resume(cls, state: OnboardingState) -> bool:
        """
        Check if onboarding can be resumed from this state.
        
        Args:
            state: The state to check
            
        Returns:
            True if onboarding can be resumed, False otherwise
        """
        # Can resume from paused or failed states, but not from completed
        return state in {OnboardingState.PAUSED, OnboardingState.FAILED}
