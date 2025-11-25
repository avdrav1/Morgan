from anthropic import Anthropic
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.logging_config import get_logger, PIIRedactor
from app.core.alerts import record_llm_failure
from app.models import User, Project, Task

logger = get_logger(__name__)


class LLMService:
    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.ANTHROPIC_MODEL
        
        # Fallback templates for when LLM API fails
        # Requirements: 3.1
        self.fallback_templates = {
            "check_in_scheduled": "Hi! Just checking in on your task: {task_title}. How's it going? Any progress to share?",
            "check_in_pre_deadline": "Your task '{task_title}' is due soon ({due_date}). How are you progressing? Need any support?",
            "check_in_overdue": "I noticed '{task_title}' is past its deadline. What's happening with this task? Let's figure out next steps together.",
            "coaching_minimal": "Got it! Thanks for the update.",
            "coaching_progress": "Thanks for the update on '{task_title}'. Keep up the good work!",
            "coaching_blocked": "I hear you're facing some challenges with '{task_title}'. What's the main thing blocking you right now?",
            "ghosting_stage_1": "Hey, I haven't heard from you in a while. Everything okay? Just checking if you still want to work on '{project_title}'.",
            "ghosting_stage_2": "I've noticed you've been away for a bit. No judgment at all - life happens! Would you like to pause '{project_title}' or adjust our approach?",
            "ghosting_stage_3": "It's been a while since we connected. I'm here when you're ready. Would you like me to archive '{project_title}' for now? We can always pick it back up later.",
        }
    
    def _get_tone_system_prompt(self, tone: str, custom_prompt: Optional[str] = None) -> str:
        """Get the system prompt based on tone setting."""
        
        base_prompts = {
            "coach": """You are a supportive accountability coach. Your role is to:
- Emphasize growth and learning from setbacks
- Frame challenges as opportunities
- Ask reflective questions to deepen understanding
- Celebrate incremental progress explicitly
- Be encouraging while maintaining high standards
- Help users develop self-awareness about their patterns""",
            
            "manager": """You are a professional project manager. Your role is to:
- Focus on outcomes and deliverables
- Keep communication efficient and action-oriented
- Provide clear status updates in structured format
- Escalate timeline risks proactively
- Be direct about what needs to happen next
- Maintain professional boundaries""",
            
            "buddy": """You are an accountability buddy and peer supporter. Your role is to:
- Use friendly, peer-like language ("we're in this together")
- Share enthusiasm for wins and progress
- Be understanding about challenges while staying persistent
- Keep conversations casual but purposeful
- Build rapport and trust naturally
- Motivate through camaraderie rather than authority""",
            
            "drill_sergeant": """You are a direct, no-nonsense accountability partner. Your role is to:
- Be direct about missed commitments and patterns
- Use strategic pressure and create urgency
- Challenge excuses when appropriate (without being cruel)
- Point out gaps between stated goals and actual actions
- Include measured guilt-tripping when it serves accountability
- Still provide support and options, but with higher expectations
- Create productive discomfort that motivates action, not destructive shame"""
        }
        
        base = base_prompts.get(tone, base_prompts["coach"])
        
        if custom_prompt:
            return f"{base}\n\nAdditional context and instructions:\n{custom_prompt}"
        
        return base
    
    def _build_context(
        self,
        user: User,
        project: Optional[Project] = None,
        task: Optional[Task] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """Build context string for the LLM.
        
        Ensures project_context is included when present.
        """
        context_parts = []
        
        # User context
        context_parts.append(f"User timezone: {user.timezone}")
        if user.quiet_hours_start and user.quiet_hours_end:
            context_parts.append(f"Quiet hours: {user.quiet_hours_start} - {user.quiet_hours_end}")
        
        # Project context
        if project:
            context_parts.append(f"\nProject: {project.title}")
            context_parts.append(f"Goal: {project.goal}")
            # Always include project_context when present (Requirement 6.9)
            if project.project_context:
                context_parts.append(f"Project-specific context: {project.project_context}")
        
        # Task context
        if task:
            context_parts.append(f"\nCurrent task: {task.title}")
            context_parts.append(f"Status: {task.status}")
            if task.due_date:
                context_parts.append(f"Due date: {task.due_date}")
            if task.blocker_type:
                context_parts.append(f"Blocker type: {task.blocker_type}")
                if task.blocker_description:
                    context_parts.append(f"Blocker details: {task.blocker_description}")
        
        # Additional context
        if additional_context:
            context_parts.append(f"\n{additional_context}")
        
        return "\n".join(context_parts)
    
    async def generate_check_in_message(
        self,
        user: User,
        project: Project,
        task: Task,
        check_in_type: str = "scheduled"
    ) -> str:
        """Generate a proactive check-in message.
        
        Uses fallback templates if LLM API fails (Requirements: 3.1).
        """
        
        tone = project.project_tone or user.preferred_tone
        system_prompt = self._get_tone_system_prompt(tone, user.custom_system_prompt)
        
        context = self._build_context(user, project, task)
        
        user_message = f"""Generate a proactive check-in message for the user about their task.

Context:
{context}

Check-in type: {check_in_type}

Your message should:
1. Reference the specific task and its deadline
2. Be concise (2-3 sentences)
3. Ask about their progress
4. Match the tone specified in your system prompt
5. Not include greetings or signatures - just the core message

Generate only the check-in message, nothing else."""

        try:
            logger.info(
                "LLM request: generate_check_in_message",
                extra={
                    'extra_fields': {
                        'operation': 'generate_check_in_message',
                        'check_in_type': check_in_type,
                        'tone': tone,
                        'model': self.model,
                        'task_id': str(task.id),
                        'project_id': str(project.id),
                    }
                }
            )
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            
            result = response.content[0].text
            
            logger.info(
                "LLM response: generate_check_in_message",
                extra={
                    'extra_fields': {
                        'operation': 'generate_check_in_message',
                        'response_length': len(result),
                        'tokens_used': response.usage.input_tokens + response.usage.output_tokens if hasattr(response, 'usage') else None,
                    }
                }
            )
            
            return result
        except Exception as e:
            logger.error(
                f"LLM API failed for check-in message",
                extra={
                    'extra_fields': {
                        'operation': 'generate_check_in_message',
                        'error': str(e),
                        'fallback_used': True,
                    }
                },
                exc_info=True
            )
            
            # Record failure for alerting
            record_llm_failure('generate_check_in_message', str(e))
            
            # Use fallback template based on check-in type
            template_key = f"check_in_{check_in_type}"
            template = self.fallback_templates.get(template_key, self.fallback_templates["check_in_scheduled"])
            
            return template.format(
                task_title=task.title,
                due_date=task.due_date.strftime("%Y-%m-%d") if task.due_date else "soon"
            )
    
    async def generate_coaching_response(
        self,
        user: User,
        project: Project,
        task: Task,
        user_response: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        is_minimal_response: bool = False
    ) -> str:
        """Generate a coaching response based on user's reply.
        
        Uses fallback templates if LLM API fails (Requirements: 3.1).
        
        Args:
            user: The user responding
            project: The project context
            task: The task being discussed
            user_response: The user's response text
            conversation_history: Previous conversation turns
            is_minimal_response: Whether this is a minimal response (10 or fewer characters)
                                Requirements: 12.1, 12.2
        """
        
        tone = project.project_tone or user.preferred_tone
        system_prompt = self._get_tone_system_prompt(tone, user.custom_system_prompt)
        
        context = self._build_context(user, project, task)
        
        messages = []
        
        # Add conversation history if available
        if conversation_history:
            messages.extend(conversation_history)
        
        # Build response instructions based on whether it's a minimal response
        if is_minimal_response:
            # For minimal responses: accept and acknowledge without over-questioning
            # Requirements: 12.1, 12.2
            response_instructions = f"""Context:
{context}

User's response to check-in: {user_response}

This is a minimal response (10 or fewer characters). Respond to the user with:
1. Simple acknowledgment of their update (e.g., "done", "ok", "finished")
2. Brief positive reinforcement if appropriate
3. DO NOT ask follow-up questions or probe for more details
4. DO NOT over-question them
5. Keep it very brief (1-2 sentences maximum)
6. Match your assigned tone

Generate your response:"""
        else:
            # For regular responses: normal coaching flow
            response_instructions = f"""Context:
{context}

User's response to check-in: {user_response}

Respond to the user based on their update. Your response should:
1. Acknowledge their progress or blocker
2. If there's a blocker, ask targeted questions to understand it
3. Suggest specific next steps or strategies if appropriate
4. Be conversational and match your assigned tone
5. Keep it concise (3-4 sentences unless detailed coaching is needed)

Generate your response:"""
        
        # Add current context and user response
        messages.append({
            "role": "user",
            "content": response_instructions
        })
        
        try:
            logger.info(
                "LLM request: generate_coaching_response",
                extra={
                    'extra_fields': {
                        'operation': 'generate_coaching_response',
                        'is_minimal_response': is_minimal_response,
                        'tone': tone,
                        'model': self.model,
                        'task_id': str(task.id),
                        'project_id': str(project.id),
                        'user_response_redacted': PIIRedactor.redact(user_response),
                    }
                }
            )
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=messages
            )
            
            result = response.content[0].text
            
            logger.info(
                "LLM response: generate_coaching_response",
                extra={
                    'extra_fields': {
                        'operation': 'generate_coaching_response',
                        'response_length': len(result),
                        'tokens_used': response.usage.input_tokens + response.usage.output_tokens if hasattr(response, 'usage') else None,
                    }
                }
            )
            
            return result
        except Exception as e:
            logger.error(
                f"LLM API failed for coaching response",
                extra={
                    'extra_fields': {
                        'operation': 'generate_coaching_response',
                        'error': str(e),
                        'fallback_used': True,
                    }
                },
                exc_info=True
            )
            
            # Record failure for alerting
            record_llm_failure('generate_coaching_response', str(e))
            
            # Use fallback template based on response type
            if is_minimal_response:
                return self.fallback_templates["coaching_minimal"]
            elif "block" in user_response.lower() or "stuck" in user_response.lower():
                return self.fallback_templates["coaching_blocked"].format(task_title=task.title)
            else:
                return self.fallback_templates["coaching_progress"].format(task_title=task.title)
    
    async def diagnose_blocker(
        self,
        user: User,
        task: Task,
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, str]:
        """Diagnose the type of blocker and suggest strategies.
        
        Returns:
            Dict with 'blocker_type' and 'suggested_strategies'
        """
        
        # Get project for context
        project = task.project
        tone = project.project_tone or user.preferred_tone
        system_prompt = self._get_tone_system_prompt(tone, user.custom_system_prompt)
        
        context = self._build_context(user, project, task)
        
        # Build conversation history string
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in conversation_history
        ])
        
        user_message = f"""Analyze the conversation to diagnose what's blocking the user from completing their task.

Context:
{context}

Conversation history:
{conversation_text}

Based on the conversation, identify the blocker type from these categories:
- time: Not enough time, competing priorities, underestimated effort
- clarity: Unclear requirements, don't know how to start, missing information
- emotional: Anxiety, perfectionism, fear of failure, overwhelm
- external: Waiting on others, missing resources, external dependencies
- scope: Task is too big, scope creep, unrealistic expectations

Return a JSON object with this structure:
{{
  "blocker_type": "one of: time, clarity, emotional, external, scope",
  "suggested_strategies": "2-3 specific, actionable strategies to overcome this blocker"
}}

Return ONLY the JSON object, no other text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        
        # Parse the JSON response
        import json
        result_json = response.content[0].text.strip()
        # Remove markdown code blocks if present
        if result_json.startswith("```"):
            result_json = result_json.split("\n", 1)[1]
            result_json = result_json.rsplit("\n", 1)[0]
        
        return json.loads(result_json)
    
    async def propose_reschedule(
        self,
        user: User,
        task: Task,
        blocker_info: Dict[str, Any],
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Propose a new deadline based on blocker analysis.
        
        Returns:
            Dict with 'proposed_date' (ISO format string) and 'reasoning'
        """
        
        project = task.project
        tone = project.project_tone or user.preferred_tone
        system_prompt = self._get_tone_system_prompt(tone, user.custom_system_prompt)
        
        context = self._build_context(user, project, task)
        
        # Build conversation history string
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in conversation_history
        ])
        
        from datetime import datetime, timedelta
        current_date = datetime.utcnow().isoformat()
        
        user_message = f"""Based on the blocker analysis and conversation, propose a realistic new deadline for this task.

Context:
{context}

Current date: {current_date}
Original due date: {task.due_date.isoformat() if task.due_date else 'Not set'}

Blocker type: {blocker_info.get('blocker_type', 'unknown')}
Blocker details: {task.blocker_description or 'See conversation'}

Conversation history:
{conversation_text}

Consider:
1. The type of blocker and typical resolution time
2. The user's current constraints mentioned in conversation
3. A realistic buffer to avoid repeated rescheduling
4. The original task estimate: {task.estimated_duration_hours or 'unknown'} hours

Return a JSON object with this structure:
{{
  "proposed_date": "YYYY-MM-DDTHH:MM:SS",
  "reasoning": "Brief explanation (2-3 sentences) of why this new deadline is realistic"
}}

Return ONLY the JSON object, no other text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        
        # Parse the JSON response
        import json
        result_json = response.content[0].text.strip()
        # Remove markdown code blocks if present
        if result_json.startswith("```"):
            result_json = result_json.split("\n", 1)[1]
            result_json = result_json.rsplit("\n", 1)[0]
        
        return json.loads(result_json)
    
    async def generate_clarification_questions(
        self,
        user: User,
        initial_description: str,
        existing_info: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """Generate clarification questions for a project description.
        
        Returns a list of questions to help understand the project better.
        """
        
        tone = user.preferred_tone
        system_prompt = self._get_tone_system_prompt(tone, user.custom_system_prompt)
        
        existing_context = ""
        if existing_info:
            existing_context = "\n".join([
                f"{key}: {value}" 
                for key, value in existing_info.items() 
                if value
            ])
        
        user_message = f"""A user wants to start a new project. They provided this description:

"{initial_description}"

{f"We already know:{existing_context}" if existing_context else ""}

Generate 2-4 targeted clarification questions to understand:
1. The specific goal or outcome they want to achieve
2. The scope and boundaries of the project
3. Any deadlines or time constraints
4. Success criteria - how they'll know they're done

Return a JSON array with this structure:
[
  {{
    "question": "The clarification question to ask",
    "field": "goal|scope|deadline|success_criteria"
  }},
  ...
]

Keep questions conversational and match your assigned tone.
Return ONLY the JSON array, no other text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        
        # Parse the JSON response
        import json
        questions_json = response.content[0].text.strip()
        # Remove markdown code blocks if present
        if questions_json.startswith("```"):
            questions_json = questions_json.split("\n", 1)[1]
            questions_json = questions_json.rsplit("\n", 1)[0]
        
        return json.loads(questions_json)
    
    async def process_clarification_answers(
        self,
        user: User,
        initial_description: str,
        answers: Dict[str, str]
    ) -> Dict[str, str]:
        """Process clarification answers and extract structured project info.
        
        Returns a dict with title, goal, success_criteria, etc.
        """
        
        tone = user.preferred_tone
        system_prompt = self._get_tone_system_prompt(tone, user.custom_system_prompt)
        
        answers_text = "\n".join([
            f"Q ({field}): {answer}"
            for field, answer in answers.items()
        ])
        
        user_message = f"""Based on the user's initial description and their answers to clarification questions, extract structured project information.

Initial description: "{initial_description}"

Clarification answers:
{answers_text}

Extract and return a JSON object with:
{{
  "title": "A concise project title (3-8 words)",
  "goal": "The main goal or outcome",
  "description": "A comprehensive description combining initial input and clarifications",
  "success_criteria": "How they'll know the project is complete",
  "estimated_duration_weeks": "Estimated duration (e.g., '2-3 weeks', '1 month')"
}}

Return ONLY the JSON object, no other text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        
        # Parse the JSON response
        import json
        result_json = response.content[0].text.strip()
        # Remove markdown code blocks if present
        if result_json.startswith("```"):
            result_json = result_json.split("\n", 1)[1]
            result_json = result_json.rsplit("\n", 1)[0]
        
        return json.loads(result_json)
    
    async def decompose_project(
        self,
        user: User,
        project: Project
    ) -> List[Dict[str, Any]]:
        """Break down a project into actionable tasks.
        
        Returns 5-20 tasks based on project complexity.
        """
        
        tone = project.project_tone or user.preferred_tone
        system_prompt = self._get_tone_system_prompt(tone, user.custom_system_prompt)
        
        # Build project context section
        project_context_section = ""
        if project.project_context:
            project_context_section = f"\nProject-specific context: {project.project_context}\n"
        
        user_message = f"""Break down this project into 5-20 concrete, actionable tasks.

Project: {project.title}
Description: {project.description}
Goal: {project.goal}
{f"Success criteria: {project.success_criteria}" if project.success_criteria else ""}{project_context_section}

IMPORTANT: Generate between 5 and 20 tasks. Adjust the granularity based on project complexity:
- Simple projects: 5-8 tasks
- Medium projects: 9-15 tasks
- Complex projects: 16-20 tasks

For each task, provide:
1. A clear, action-oriented title (start with a verb)
2. A brief description of what needs to be done
3. Estimated duration in hours
4. Logical sequence order

Return the tasks as a JSON array with this structure:
[
  {{
    "title": "Task title",
    "description": "What needs to be done",
    "estimated_duration_hours": 4,
    "order": 1
  }},
  ...
]

Return ONLY the JSON array, no other text."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        
        # Parse the JSON response
        import json
        tasks_json = response.content[0].text.strip()
        # Remove markdown code blocks if present
        if tasks_json.startswith("```"):
            tasks_json = tasks_json.split("\n", 1)[1]
            tasks_json = tasks_json.rsplit("\n", 1)[0]
        
        tasks = json.loads(tasks_json)
        
        # Validate task count is between 5 and 20
        if not (5 <= len(tasks) <= 20):
            raise ValueError(f"Task count must be between 5 and 20, got {len(tasks)}")
        
        return tasks


    async def generate_ghosting_message(
        self,
        user: User,
        project: Project,
        ghosting_stage: int,
        message_template: str
    ) -> str:
        """Generate an empathetic ghosting response message.
        
        Uses fallback templates if LLM API fails (Requirements: 3.1).
        
        Args:
            user: The user who has missed check-ins
            project: The project with missed check-ins
            ghosting_stage: The ghosting stage (1=2 missed, 2=4 missed, 3=7 missed)
            message_template: Template identifier for the type of message
            
        Returns:
            str: The generated ghosting message
        """
        
        tone = project.project_tone or user.preferred_tone
        system_prompt = self._get_tone_system_prompt(tone, user.custom_system_prompt)
        
        context = self._build_context(user, project)
        
        # Define message guidance based on stage
        stage_guidance = {
            1: """The user has missed 2 consecutive check-ins. Your message should:
- Acknowledge that they might be going through a difficult time
- Express understanding without judgment
- Gently ask if they want to continue with the project
- Keep it brief and supportive (2-3 sentences)
- Don't pressure them, just check in""",
            
            2: """The user has missed 4 consecutive check-ins. Your message should:
- Show empathy for whatever they're dealing with
- Ask if they want to pause the project or adjust the approach
- Offer specific options (pause, adjust timeline, change approach)
- Make it clear there's no judgment
- Keep it warm but direct (3-4 sentences)""",
            
            3: """The user has missed 7 consecutive check-ins. Your message should:
- Be very understanding and non-judgmental
- Offer to archive the project and check in later
- Acknowledge that sometimes life gets in the way
- Leave the door open for returning when ready
- Express that you're here when they need support
- Keep it compassionate and brief (3-4 sentences)"""
        }
        
        guidance = stage_guidance.get(ghosting_stage, stage_guidance[1])
        
        user_message = f"""Generate an empathetic message for a user who has missed multiple check-ins.

Context:
{context}

Ghosting stage: {ghosting_stage} (consecutive missed check-ins: {ghosting_stage * 2})

{guidance}

Generate only the message, nothing else."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=400,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            
            return response.content[0].text
        except Exception as e:
            logger.error(f"LLM API failed for ghosting message: {e}")
            # Use fallback template based on ghosting stage
            template_key = f"ghosting_stage_{ghosting_stage}"
            template = self.fallback_templates.get(template_key, self.fallback_templates["ghosting_stage_1"])
            
            return template.format(project_title=project.title)
    
    async def generate_onboarding_message(
        self,
        current_state: str,
        conversation_history: List[Dict[str, str]],
        tone: str = "supportive",
        collected_data: Optional[Dict[str, Any]] = None,
        state_context: Optional[Dict[str, Any]] = None,
        acknowledge_input: bool = True
    ) -> str:
        """Generate a conversational onboarding message based on current state.
        
        Enhanced to use state-specific prompts, include collected data in context,
        generate acknowledgments for user responses, generate clarifying questions
        for ambiguous inputs, and maintain conversational tone throughout.
        
        Uses fallback templates if LLM API fails (Requirements: 8.1, 8.2, 8.4, 8.5).
        
        Args:
            current_state: The current onboarding state
            conversation_history: List of previous conversation turns
            tone: The user's preferred communication tone
            collected_data: Data collected so far in onboarding
            state_context: Enhanced state-specific context with instructions
            acknowledge_input: Whether to acknowledge the user's previous response
            
        Returns:
            str: The generated onboarding message
        """
        from app.services.onboarding_templates import OnboardingTemplates
        from app.models.onboarding_session import OnboardingState
        
        # Map tone to system prompt style
        tone_mapping = {
            "supportive": "coach",
            "direct": "manager",
            "casual": "buddy",
            "drill_sergeant": "drill_sergeant"
        }
        
        system_tone = tone_mapping.get(tone, "coach")
        system_prompt = self._get_tone_system_prompt(system_tone)
        
        # Add onboarding-specific instructions
        system_prompt += """

For onboarding conversations:
- Be warm and welcoming
- Ask one question at a time
- Keep messages concise (2-3 sentences)
- Acknowledge user responses before asking the next question when appropriate
- Be encouraging and supportive throughout
- Don't use greetings or signatures - just the core message
- If the user's input seems ambiguous, ask a clarifying question
- Maintain a natural, conversational flow"""
        
        # Build context from collected data
        context_parts = []
        if collected_data:
            for key, value in collected_data.items():
                if value:
                    context_parts.append(f"{key}: {value}")
        
        context = "\n".join(context_parts) if context_parts else "No data collected yet"
        
        # Use enhanced state context if provided
        if state_context:
            state_instructions = state_context.get('instructions', '')
            acknowledgment_hint = state_context.get('acknowledgment_hint', '')
            last_user_message = state_context.get('last_user_message', '')
            
            # Build enhanced prompt with state-specific instructions
            prompt_parts = [f"Current onboarding state: {current_state}"]
            
            if context:
                prompt_parts.append(f"\nCollected data so far:\n{context}")
            
            if last_user_message and acknowledge_input:
                prompt_parts.append(f"\nUser's last message: \"{last_user_message}\"")
                if acknowledgment_hint:
                    prompt_parts.append(f"\nAcknowledgment guidance: {acknowledgment_hint}")
            
            prompt_parts.append(f"\nYour task: {state_instructions}")
            
            if acknowledge_input and last_user_message:
                prompt_parts.append(
                    "\nIMPORTANT: Start by briefly acknowledging the user's response, "
                    "then ask your next question. Keep the acknowledgment natural and brief."
                )
            
            prompt_parts.append("\nGenerate your response:")
            
            state_prompt = "\n".join(prompt_parts)
        else:
            # Fallback to basic state prompts
            state_prompts = {
                "welcome": "Generate a warm welcome message for a new user starting onboarding. Introduce yourself briefly and ask what project they'd like to work on.",
                "collect_project_name": "The user has expressed interest in starting a project. Acknowledge their interest, then ask them what they'd like to call this project.",
                "collect_goal": f"The user named their project '{collected_data.get('project_name', 'their project')}'. Acknowledge the name positively, then ask them what main goal they want to achieve with this project.",
                "collect_deadline": "The user has shared their project goal. Acknowledge it enthusiastically, then ask them when they'd like to complete this project. Mention they can use natural language like 'in 2 weeks' or specific dates.",
                "confirm_deadline": f"The user provided a deadline. Confirm with them that they want to complete this by {collected_data.get('deadline', 'the specified date')}.",
                "collect_checkin_frequency": "Acknowledge that the deadline is set, then ask the user how often they'd like you to check in with them (e.g., daily, every 2 days, weekly).",
                "collect_tone": "Acknowledge their check-in preference, then ask the user what communication style they prefer. Offer options: supportive (encouraging), direct (straightforward), casual (friendly), or drill_sergeant (no-nonsense).",
                "confirm_details": f"Acknowledge their tone preference, then show the user a summary of all collected information and ask them to confirm it looks correct:\n{context}",
            }
            
            state_prompt = state_prompts.get(current_state, "Continue the onboarding conversation naturally, acknowledging the user's previous response.")
        
        # Build messages with conversation history
        messages = []
        
        # Add conversation history (last 5 turns for context)
        if conversation_history:
            for msg in conversation_history[-5:]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["message"]
                })
        
        # Add current prompt
        messages.append({
            "role": "user",
            "content": state_prompt
        })
        
        try:
            logger.info(
                "LLM request: generate_onboarding_message",
                extra={
                    'extra_fields': {
                        'operation': 'generate_onboarding_message',
                        'current_state': current_state,
                        'tone': tone,
                        'model': self.model,
                        'acknowledge_input': acknowledge_input,
                    }
                }
            )
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                system=system_prompt,
                messages=messages,
                timeout=5.0  # 5 second timeout as per requirements
            )
            
            result = response.content[0].text
            
            logger.info(
                "LLM response: generate_onboarding_message",
                extra={
                    'extra_fields': {
                        'operation': 'generate_onboarding_message',
                        'response_length': len(result),
                    }
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"LLM API failed for onboarding message",
                extra={
                    'extra_fields': {
                        'operation': 'generate_onboarding_message',
                        'error': str(e),
                        'fallback_used': True,
                    }
                },
                exc_info=True
            )
            
            # Record failure for alerting
            record_llm_failure('generate_onboarding_message', str(e))
            
            # Use fallback template from OnboardingTemplates
            try:
                # Convert state string to OnboardingState enum
                state_enum = OnboardingState(current_state)
                
                # Prepare template variables
                template_vars = collected_data or {}
                
                # Get message from templates
                return OnboardingTemplates.get_message(
                    state=state_enum,
                    tone=tone,
                    **template_vars
                )
            except (ValueError, KeyError) as template_error:
                # If template lookup fails, return a generic message
                logger.error(
                    f"Failed to get fallback template",
                    extra={
                        'extra_fields': {
                            'operation': 'generate_onboarding_message_fallback',
                            'error': str(template_error),
                        }
                    }
                )
                return "Let's continue with your onboarding. What would you like to tell me?"


# Singleton instance
llm_service = LLMService()
