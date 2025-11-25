from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import re

from app.models.check_in import CheckIn
from app.models.task import Task


class ConversationManager:
    """Manages conversation context and state for check-ins."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_conversation_context(
        self,
        check_in: CheckIn,
        max_history: int = 10
    ) -> List[Dict[str, str]]:
        """
        Retrieve conversation history for a check-in.
        
        Returns a list of conversation turns in the format expected by the LLM:
        [
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "..."},
            ...
        ]
        
        Args:
            check_in: The CheckIn object to get context for
            max_history: Maximum number of conversation turns to retrieve
            
        Returns:
            List of conversation turns with role and content
        """
        # First, check if this check-in has stored conversation context
        if check_in.conversation_context:
            # Return the stored context, limited to max_history
            context = check_in.conversation_context
            if isinstance(context, list):
                return context[-max_history:]
        
        # If no stored context, build from check-in fields
        conversation = []
        
        # Add the initial message if it was sent
        if check_in.message_sent:
            conversation.append({
                "role": "assistant",
                "content": check_in.message_sent
            })
        
        # Add user response if available
        if check_in.user_response:
            conversation.append({
                "role": "user",
                "content": check_in.user_response
            })
        
        # Add assistant reply if available
        if check_in.assistant_reply:
            conversation.append({
                "role": "assistant",
                "content": check_in.assistant_reply
            })
        
        return conversation[-max_history:]
    
    def store_conversation_turn(
        self,
        check_in: CheckIn,
        role: str,
        content: str
    ) -> None:
        """
        Store a conversation turn in the check-in's conversation context.
        
        Args:
            check_in: The CheckIn object to update
            role: The role of the speaker ("user" or "assistant")
            content: The message content
        """
        # Get existing context or initialize empty list
        if check_in.conversation_context and isinstance(check_in.conversation_context, list):
            context = check_in.conversation_context
        else:
            context = []
        
        # Add the new turn
        context.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Update the check-in
        check_in.conversation_context = context
        check_in.updated_at = datetime.utcnow()
        
        # Also update the specific fields for backwards compatibility
        if role == "assistant":
            if not check_in.message_sent:
                check_in.message_sent = content
            else:
                check_in.assistant_reply = content
        elif role == "user":
            check_in.user_response = content
        
        self.db.commit()
    
    def detect_blocker_pattern(
        self,
        task: Task,
        conversation_history: List[Dict[str, str]]
    ) -> Optional[str]:
        """
        Detect blocker patterns from conversation history.
        
        Analyzes the conversation to identify one of five blocker types:
        - time: Not enough time, too busy, scheduling conflicts
        - clarity: Unclear requirements, don't know how to start, confusion
        - emotional: Anxiety, fear, overwhelm, procrastination
        - external: Waiting on others, dependencies, external blockers
        - scope: Task too big, scope creep, unrealistic expectations
        
        Args:
            task: The Task object being discussed
            conversation_history: List of conversation turns
            
        Returns:
            Blocker type string if detected, None otherwise
        """
        # Combine all user messages into one text for pattern matching
        user_messages = [
            turn["content"].lower()
            for turn in conversation_history
            if turn.get("role") == "user"
        ]
        
        if not user_messages:
            return None
        
        combined_text = " ".join(user_messages)
        
        # Define patterns for each blocker type
        time_patterns = [
            r'(no time|not enough time|too busy|don\'?t have.*time|running out of time)',
            r'(schedule|scheduling conflict|other priorities|urgent)',
            r'(deadline|rushed|behind schedule)'
        ]
        
        clarity_patterns = [
            r'\b(unclear|not sure|don\'t know|confused|confusing)\b',
            r'\b(how to|where to start|what to do|don\'t understand)\b',
            r'\b(vague|ambiguous|need more info|need clarification)\b'
        ]
        
        emotional_patterns = [
            r'(anxious|anxiety|worried|scared|fear|afraid)',
            r'(overwhelm|overwhelming|stressed|stress|burnout)',
            r'(procrastinat|avoid|avoiding|dread|dreading)',
            r'(unmotivated|can\'?t focus|distracted)'
        ]
        
        external_patterns = [
            r'\b(waiting|waiting for|blocked by|depends on|dependency)\b',
            r'\b(someone else|other people|team|colleague)\b',
            r'\b(external|outside|third party|vendor)\b',
            r'\b(approval|permission|access)\b'
        ]
        
        scope_patterns = [
            r'\b(too big|too large|too much|overwhelming scope)\b',
            r'\b(scope creep|expanded|growing|bigger than)\b',
            r'\b(unrealistic|too ambitious|overestimated)\b',
            r'\b(break down|break it down|smaller|simplify)\b'
        ]
        
        # Count matches for each blocker type
        blocker_scores = {
            "time": sum(1 for pattern in time_patterns if re.search(pattern, combined_text)),
            "clarity": sum(1 for pattern in clarity_patterns if re.search(pattern, combined_text)),
            "emotional": sum(1 for pattern in emotional_patterns if re.search(pattern, combined_text)),
            "external": sum(1 for pattern in external_patterns if re.search(pattern, combined_text)),
            "scope": sum(1 for pattern in scope_patterns if re.search(pattern, combined_text))
        }
        
        # Return the blocker type with the highest score, if any
        max_score = max(blocker_scores.values())
        if max_score > 0:
            for blocker_type, score in blocker_scores.items():
                if score == max_score:
                    return blocker_type
        
        return None
    
    def extract_reschedule_intent(
        self,
        user_response: str
    ) -> bool:
        """
        Detect if the user is requesting to reschedule a task.
        
        Analyzes user response for patterns indicating they want to:
        - Push back the deadline
        - Change the due date
        - Request more time
        - Delay the task
        
        Args:
            user_response: The user's message text
            
        Returns:
            True if reschedule intent is detected, False otherwise
        """
        if not user_response:
            return False
        
        # Convert to lowercase for pattern matching
        text = user_response.lower()
        
        # Define reschedule intent patterns
        reschedule_patterns = [
            # Direct reschedule requests
            r'(reschedule|re-schedule|push.*back|move.*back)',
            r'(postpone|delay|extend|extension)',
            r'(change.*deadline|new deadline|different deadline)',
            r'(change.*due date|new due date)',
            
            # Time-related requests
            r'\b(need more time|more time|extra time|additional time)\b',
            r'\b(can\'t make it|won\'t make it|can\'t finish|won\'t finish)\b',
            r'\b(not going to make|not gonna make)\b',
            
            # Indirect reschedule signals
            r'\b(later|next week|next month|another day)\b.*\b(do|finish|complete|work on)\b',
            r'\b(do|finish|complete|work on)\b.*\b(later|next week|next month|another day)\b',
            
            # Questions about rescheduling
            r'\b(can i|could i|can we|could we)\b.*\b(reschedule|push|move|change|postpone|delay)\b',
            r'\b(is it okay|is it ok|would it be okay|would it be ok)\b.*\b(reschedule|push|move|change|postpone|delay)\b',
            
            # Statements about not meeting deadline
            r'\b(won\'t be able to|can\'t|cannot)\b.*\b(by|before|on time)\b',
            r'\b(behind schedule|running behind|falling behind)\b'
        ]
        
        # Check if any pattern matches
        for pattern in reschedule_patterns:
            if re.search(pattern, text):
                return True
        
        return False
