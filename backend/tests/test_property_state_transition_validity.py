"""
Property-based tests for onboarding state machine transition validity.

Feature: discord-dm-onboarding, Property 2: State transition validity
Validates: Requirements 2.1
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from app.models.onboarding_session import OnboardingState
from app.services.onboarding_state_machine import OnboardingStateMachine


# Strategy to generate any OnboardingState
@st.composite
def onboarding_states(draw):
    """Generate a random OnboardingState."""
    return draw(st.sampled_from(list(OnboardingState)))


# Strategy to generate valid state transitions
@st.composite
def valid_state_transition(draw):
    """Generate a valid state transition pair."""
    current_state = draw(onboarding_states())
    valid_next_states = OnboardingStateMachine.get_valid_next_states(current_state)
    
    # If there are no valid next states, skip this example
    assume(len(valid_next_states) > 0)
    
    next_state = draw(st.sampled_from(list(valid_next_states)))
    return (current_state, next_state)


# Strategy to generate invalid state transitions
@st.composite
def invalid_state_transition(draw):
    """Generate an invalid state transition pair."""
    current_state = draw(onboarding_states())
    next_state = draw(onboarding_states())
    
    # Only keep this example if the transition is invalid
    assume(not OnboardingStateMachine.is_valid_transition(current_state, next_state))
    
    return (current_state, next_state)


@settings(max_examples=100)
@given(transition=valid_state_transition())
def test_valid_transitions_are_accepted(transition):
    """
    Property 2: State transition validity
    
    For any valid state transition according to the state machine rules,
    the is_valid_transition method should return True.
    
    This ensures that all transitions defined in VALID_TRANSITIONS are
    correctly recognized as valid.
    
    Validates: Requirements 2.1
    """
    current_state, next_state = transition
    
    # Valid transitions should be accepted
    assert OnboardingStateMachine.is_valid_transition(current_state, next_state), \
        f"Transition from {current_state.value} to {next_state.value} should be valid"
    
    # validate_transition should not raise an exception
    try:
        OnboardingStateMachine.validate_transition(current_state, next_state)
    except ValueError as e:
        pytest.fail(f"validate_transition raised ValueError for valid transition: {e}")


@settings(max_examples=100)
@given(transition=invalid_state_transition())
def test_invalid_transitions_are_rejected(transition):
    """
    Property 2: State transition validity
    
    For any invalid state transition (not in the state machine rules),
    the is_valid_transition method should return False and validate_transition
    should raise a ValueError.
    
    This ensures that transitions not defined in VALID_TRANSITIONS are
    correctly rejected.
    
    Validates: Requirements 2.1
    """
    current_state, next_state = transition
    
    # Invalid transitions should be rejected
    assert not OnboardingStateMachine.is_valid_transition(current_state, next_state), \
        f"Transition from {current_state.value} to {next_state.value} should be invalid"
    
    # validate_transition should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        OnboardingStateMachine.validate_transition(current_state, next_state)
    
    # Check that the error message is informative
    error_message = str(exc_info.value)
    assert "Invalid state transition" in error_message, \
        "Error message should indicate invalid transition"
    assert current_state.value in error_message, \
        "Error message should include current state"
    assert next_state.value in error_message, \
        "Error message should include next state"


@settings(max_examples=100)
@given(current_state=onboarding_states())
def test_get_valid_next_states_returns_valid_set(current_state):
    """
    Property 2: State transition validity
    
    For any current state, get_valid_next_states should return a set of states
    where each state in the set is a valid transition from the current state.
    
    Validates: Requirements 2.1
    """
    valid_next_states = OnboardingStateMachine.get_valid_next_states(current_state)
    
    # Should return a set
    assert isinstance(valid_next_states, set), \
        "get_valid_next_states should return a set"
    
    # Every state in the returned set should be a valid transition
    for next_state in valid_next_states:
        assert OnboardingStateMachine.is_valid_transition(current_state, next_state), \
            f"State {next_state.value} in valid_next_states should be a valid transition from {current_state.value}"


@settings(max_examples=100)
@given(
    current_state=onboarding_states(),
    next_state=onboarding_states()
)
def test_transition_validity_is_consistent(current_state, next_state):
    """
    Property 2: State transition validity
    
    For any pair of states, is_valid_transition and validate_transition should
    be consistent: if is_valid_transition returns True, validate_transition
    should not raise an exception, and vice versa.
    
    Validates: Requirements 2.1
    """
    is_valid = OnboardingStateMachine.is_valid_transition(current_state, next_state)
    
    if is_valid:
        # If is_valid_transition says it's valid, validate_transition should not raise
        try:
            OnboardingStateMachine.validate_transition(current_state, next_state)
        except ValueError as e:
            pytest.fail(
                f"Inconsistency: is_valid_transition returned True but validate_transition raised: {e}"
            )
    else:
        # If is_valid_transition says it's invalid, validate_transition should raise
        with pytest.raises(ValueError):
            OnboardingStateMachine.validate_transition(current_state, next_state)


@settings(max_examples=100)
@given(current_state=onboarding_states())
def test_valid_next_states_matches_is_valid_transition(current_state):
    """
    Property 2: State transition validity
    
    For any current state, the set returned by get_valid_next_states should
    exactly match the states for which is_valid_transition returns True.
    
    Validates: Requirements 2.1
    """
    valid_next_states = OnboardingStateMachine.get_valid_next_states(current_state)
    
    # Check all possible states
    for state in OnboardingState:
        is_valid = OnboardingStateMachine.is_valid_transition(current_state, state)
        in_valid_set = state in valid_next_states
        
        assert is_valid == in_valid_set, \
            f"Inconsistency for transition {current_state.value} -> {state.value}: " \
            f"is_valid_transition={is_valid}, in get_valid_next_states={in_valid_set}"


def test_initial_state_is_welcome():
    """
    Property 2: State transition validity
    
    The initial state for a new onboarding session should always be WELCOME.
    
    Validates: Requirements 2.1
    """
    initial_state = OnboardingStateMachine.get_initial_state()
    assert initial_state == OnboardingState.WELCOME, \
        f"Initial state should be WELCOME, got {initial_state.value}"


def test_completed_is_terminal_state():
    """
    Property 2: State transition validity
    
    The COMPLETED state should be terminal (only valid transition is to itself).
    
    Validates: Requirements 2.1
    """
    assert OnboardingStateMachine.is_terminal_state(OnboardingState.COMPLETED), \
        "COMPLETED should be a terminal state"
    
    # COMPLETED should only transition to itself
    valid_next = OnboardingStateMachine.get_valid_next_states(OnboardingState.COMPLETED)
    assert valid_next == {OnboardingState.COMPLETED}, \
        "COMPLETED should only transition to itself"


def test_failed_is_error_state():
    """
    Property 2: State transition validity
    
    The FAILED state should be recognized as an error state.
    
    Validates: Requirements 2.1
    """
    assert OnboardingStateMachine.is_error_state(OnboardingState.FAILED), \
        "FAILED should be an error state"


def test_paused_is_paused_state():
    """
    Property 2: State transition validity
    
    The PAUSED state should be recognized as a paused state.
    
    Validates: Requirements 2.1
    """
    assert OnboardingStateMachine.is_paused_state(OnboardingState.PAUSED), \
        "PAUSED should be a paused state"


def test_can_resume_from_paused_and_failed():
    """
    Property 2: State transition validity
    
    Onboarding should be resumable from PAUSED and FAILED states,
    but not from COMPLETED.
    
    Validates: Requirements 2.1
    """
    assert OnboardingStateMachine.can_resume(OnboardingState.PAUSED), \
        "Should be able to resume from PAUSED"
    assert OnboardingStateMachine.can_resume(OnboardingState.FAILED), \
        "Should be able to resume from FAILED"
    assert not OnboardingStateMachine.can_resume(OnboardingState.COMPLETED), \
        "Should not be able to resume from COMPLETED"


@settings(max_examples=100)
@given(current_state=onboarding_states())
def test_all_states_have_defined_transitions(current_state):
    """
    Property 2: State transition validity
    
    Every state in OnboardingState should have defined transitions in the
    state machine (even if it's just to itself).
    
    Validates: Requirements 2.1
    """
    valid_next_states = OnboardingStateMachine.get_valid_next_states(current_state)
    
    # Every state should have at least one valid transition
    assert len(valid_next_states) > 0, \
        f"State {current_state.value} has no valid transitions defined"
