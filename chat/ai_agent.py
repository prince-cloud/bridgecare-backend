from typing import List, Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from .models import AIChatSession, AIChatMessage
from .ai_agent_tools import AgentTools

# LangChain imports
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from loguru import logger

# from langchain_redis import RedisVectorStore, RedisConfig
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.schema import Document as LangchainDocument
# from langchain_community.vectorstores import Chroma


# Get Redis URL from Django settings
OPENAI_API_KEY = getattr(settings, "OPENAI_API_KEY", "")
OPENAI_MODEL = getattr(settings, "OPENAI_MODEL", "gpt-4o")
EMBEDDING_MODEL = getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small")


class ChatService:
    """Service for handling chat functionality"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=OPENAI_MODEL,
            openai_api_key=OPENAI_API_KEY,
            temperature=0.7,
        )
        self.embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=OPENAI_API_KEY,
        )
        self.agent_tools = AgentTools()

    def ask_question(
        self,
        question: str,
        user_id: int,
        session_id=None,
        max_results: int = 5,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Ask a question and get response with priority system"""
        try:
            # Get or create chat session
            session = self._get_or_create_session(user_id, session_id)

            # Priority 0: Check if this is a greeting (highest priority, no file lookups)
            greeting_response = self._handle_greeting_request(
                question,
                session,
                user_id,
            )
            if greeting_response:
                return greeting_response

            conversation_history = self._get_conversation_history(session)
            health_response = self._handle_health_question(
                question, session, user_id, conversation_history=conversation_history
            )
            if health_response:
                return health_response

            # Priority 2: Handle general questions (about service, capabilities, etc.)
            general_response = self._handle_general_question(question, session, user_id)
            if general_response:
                return general_response

            # If no handler matched, return a helpful default response
            return self._create_default_response(question, session)

        except Exception as e:
            logger.error(f"Error asking question: {str(e)}")
            return self._create_error_response(str(e))

    def _is_greeting(self, question: str) -> Dict[str, Any]:
        """
        Use AI to naturally detect if a message is a greeting or conversational opener.
        Returns a dict with 'is_greeting' boolean, 'greeting_type', and 'confidence' score.
        """
        try:
            # Use LLM to determine if this is a greeting naturally
            intent_prompt = f"""You are analyzing user messages to determine if they are greetings or conversational openers.

User message: "{question}"

Analyze the user's intent naturally. Consider:
- Greetings (hello, hi, good morning, etc.)
- Conversational starters (how are you, what's up, etc.)
- Questions about the assistant (who are you, what are you)
- Polite expressions (thank you, thanks)
- Closing expressions (goodbye, bye, see you later)

Respond in JSON format with:
{{
    "is_greeting": true/false,
    "greeting_type": "opening" | "closing" | "polite" | "question_about_assistant" | "conversational_starter" | null,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Only respond with valid JSON, no additional text."""

            response = self.llm.invoke(intent_prompt)
            response_text = response.content.strip()

            # Parse JSON response
            import json

            try:
                # Extract JSON from response (in case there's extra text)
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(response_text[json_start:json_end])
                    return {
                        "is_greeting": result.get("is_greeting", False),
                        "greeting_type": result.get("greeting_type"),
                        "confidence": result.get("confidence", 0.5),
                        "reasoning": result.get("reasoning", ""),
                    }
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    f"Failed to parse greeting detection response: {e}, response: {response_text}"
                )

            # Fallback: very short messages are likely greetings
            question_lower = question.lower().strip()
            is_short = len(question_lower) <= 20

            return {
                "is_greeting": is_short,
                "greeting_type": "opening" if is_short else None,
                "confidence": 0.4 if is_short else 0.2,
                "reasoning": "Fallback detection used",
            }

        except Exception as e:
            logger.error(f"Error in AI-based greeting detection: {e}")
            # Fallback to simple check
            return {
                "is_greeting": False,
                "greeting_type": None,
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}",
            }

    def _handle_greeting_request(
        self, question: str, session: Any, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Handle greeting messages using natural language understanding.
        Returns a response if this is a greeting, None otherwise.
        """
        try:
            # Use AI to detect if this is a greeting naturally
            greeting_result = self._is_greeting(question)

            # Only proceed if confident it's a greeting
            if (
                not greeting_result.get("is_greeting", False)
                or greeting_result.get("confidence", 0) < 0.5
            ):
                return None

            # Save the user message first
            _ = self._save_user_message(session, question)

            # Generate appropriate greeting response based on type
            greeting_type = greeting_result.get("greeting_type", "opening")
            response_content = self._generate_greeting_response(
                question, greeting_type, session
            )

            # Save the assistant response
            assistant_message = self._save_assistant_message(
                session,
                response_content,
                confidence_score=greeting_result.get("confidence", 0.9),
                source_type="greeting",
            )

            # Update session
            session.last_message_at = timezone.now()
            if not session.title or session.title == "New Chat":
                session.title = "Greeting"
            session.save()

            return {
                "success": True,
                "answer": response_content,
                "session_id": session.id,
                "session_title": session.title,
                "message_id": assistant_message.id,
                "confidence_score": greeting_result.get("confidence", 0.9),
            }

        except Exception as e:
            logger.error(f"Error handling greeting: {e}")
            return None

    def _is_health_related_question(
        self, question: str, conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Use AI to naturally detect if a question is health-related.
        Returns a dict with 'is_health_related' boolean and 'confidence' score.
        """
        try:
            # Build context from conversation history if available
            context = ""
            if conversation_history:
                recent_messages = conversation_history[
                    -3:
                ]  # Last 3 messages for context
                context = "\n".join(
                    [
                        f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                        for msg in recent_messages
                    ]
                )

            # Use LLM to determine if this is a health-related question
            intent_prompt = f"""You are an AI health assistant. Analyze the following user message to determine if it's related to health, medical concerns, symptoms, prescriptions, or how the user is feeling.

User message: "{question}"
{f"Recent conversation context:\n{context}" if context else ""}

Analyze the user's intent naturally. Consider:
- Questions about how they're feeling
- Symptoms or health concerns
- Medication or prescription questions
- General health inquiries
- Wellness and preventive health

Respond in JSON format with:
{{
    "is_health_related": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Only respond with valid JSON, no additional text."""

            response = self.llm.invoke(intent_prompt)
            response_text = response.content.strip()

            # Parse JSON response
            import json

            try:
                # Extract JSON from response (in case there's extra text)
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(response_text[json_start:json_end])
                    return {
                        "is_health_related": result.get("is_health_related", False),
                        "confidence": result.get("confidence", 0.5),
                        "reasoning": result.get("reasoning", ""),
                    }
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    f"Failed to parse intent detection response: {e}, response: {response_text}"
                )

            # Fallback: if we can't parse, use a simple heuristic
            question_lower = question.lower()
            health_indicators = [
                "feel",
                "feeling",
                "symptom",
                "pain",
                "sick",
                "medicine",
                "prescription",
                "doctor",
                "health",
            ]
            has_health_indicator = any(
                indicator in question_lower for indicator in health_indicators
            )

            return {
                "is_health_related": has_health_indicator,
                "confidence": 0.6 if has_health_indicator else 0.3,
                "reasoning": "Fallback detection used",
            }

        except Exception as e:
            logger.error(f"Error in AI-based health question detection: {e}")
            # Fallback to simple check
            return {
                "is_health_related": False,
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}",
            }

    def _handle_health_question(
        self,
        question: str,
        session,
        user_id: int,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle health-related questions using AgentTools with natural language understanding.
        Supports follow-up questions and conversation context.
        Returns a response if this is a health question, None otherwise.
        """
        try:
            # Use AI to detect if this is health-related (natural language understanding)
            intent_result = self._is_health_related_question(
                question, conversation_history
            )

            # Only proceed if confident it's health-related
            if (
                not intent_result.get("is_health_related", False)
                or intent_result.get("confidence", 0) < 0.5
            ):
                return None

            # Save the user message first
            _ = self._save_user_message(session, question)

            # Get conversation context for better understanding
            context_messages = conversation_history or []

            # Get health-related response using AgentTools with context
            response_content = self.agent_tools.get_health_related_info(
                question, conversation_history=context_messages
            )

            # Determine if the response is asking a follow-up question
            _ = self._is_followup_question(response_content)

            # Save the assistant response
            assistant_message = self._save_assistant_message(
                session,
                response_content,
                confidence_score=intent_result.get("confidence", 0.8),
                source_type="health",
            )

            # Update session
            session.last_message_at = timezone.now()
            if not session.title or session.title == "New Chat":
                # Extract a short title from the question
                title = question[:50] + "..." if len(question) > 50 else question
                session.title = title
            session.save()

            return {
                "success": True,
                "session_id": session.id,
                "message_id": assistant_message.id,
                "confidence_score": intent_result.get("confidence", 0.8),
                "answer": response_content,
                "session_title": session.title,
            }

        except Exception as e:
            logger.error(f"Error handling health question: {e}")
            return None

    def _is_general_question(self, question: str) -> Dict[str, Any]:
        """
        Use AI to detect if a question is about the service, capabilities, or general inquiry.
        Returns a dict with 'is_general_question' boolean and 'confidence' score.
        """
        try:
            # Use LLM to determine if this is a general/service question
            intent_prompt = f"""You are analyzing user messages to determine if they are asking about the AI assistant itself, its capabilities, services, or general information.

User message: "{question}"

Analyze if the user is asking about:
- What the assistant can do or its capabilities
- What services are offered
- How the assistant works
- Who created it or information about it
- Its limitations or accuracy
- Whether it can help with something specific
- General questions about the platform/service

Respond in JSON format with:
{{
    "is_general_question": true/false,
    "question_category": "capabilities" | "limitations" | "about_service" | "how_it_works" | "general_inquiry" | null,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}

Only respond with valid JSON, no additional text."""

            response = self.llm.invoke(intent_prompt)
            response_text = response.content.strip()

            # Parse JSON response
            import json

            try:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(response_text[json_start:json_end])
                    return {
                        "is_general_question": result.get("is_general_question", False),
                        "question_category": result.get("question_category"),
                        "confidence": result.get("confidence", 0.5),
                        "reasoning": result.get("reasoning", ""),
                    }
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    f"Failed to parse general question detection: {e}, response: {response_text}"
                )

            return {
                "is_general_question": False,
                "question_category": None,
                "confidence": 0.3,
                "reasoning": "Fallback - could not determine",
            }

        except Exception as e:
            logger.error(f"Error in general question detection: {e}")
            return {
                "is_general_question": False,
                "question_category": None,
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}",
            }

    def _handle_general_question(
        self, question: str, session, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Handle general questions about the service, capabilities, and other inquiries.
        Returns a response if this is a general question, None otherwise.
        """
        try:
            # Detect if this is a general question
            general_result = self._is_general_question(question)

            # Only proceed if confident it's a general question
            if (
                not general_result.get("is_general_question", False)
                or general_result.get("confidence", 0) < 0.5
            ):
                return None

            # Save the user message
            user_message = self._save_user_message(session, question)

            # Generate response about the service
            question_category = general_result.get(
                "question_category", "general_inquiry"
            )
            response_content = self._generate_service_response(
                question, question_category
            )

            # Save the assistant response
            assistant_message = self._save_assistant_message(
                session,
                response_content,
                confidence_score=general_result.get("confidence", 0.8),
                source_type="general",
            )

            # Update session
            session.last_message_at = timezone.now()
            if not session.title or session.title == "New Chat":
                session.title = "Service Information"
            session.save()

            return {
                "success": True,
                "session_id": session.id,
                "message_id": assistant_message.id,
                "confidence_score": general_result.get("confidence", 0.8),
                "answer": response_content,
                "session_title": session.title,
            }

        except Exception as e:
            logger.error(f"Error handling general question: {e}")
            return None

    def _generate_service_response(self, question: str, category: str) -> str:
        """
        Generate responses about the service, capabilities, and limitations.
        """
        try:
            # System context about the service
            service_info = """You are an AI health assistant with the following characteristics:

**What I Can Do:**
- Answer health-related questions naturally
- Provide information about symptoms, conditions, and general health topics
- Discuss medications and treatments in general terms
- Ask clarifying questions to better understand your health concerns
- Offer general wellness and preventive health information
- Provide empathetic, conversational support

**What I Cannot Do:**
- Diagnose medical conditions (I'm not a doctor)
- Prescribe medications or provide specific medical treatment plans
- Replace professional medical advice
- Provide emergency medical care (call emergency services if urgent)
- Access your medical records or personal health data

**How I Work:**
- I use natural language understanding to comprehend your questions
- I don't rely on keywords - I understand context and intent
- I can have follow-up conversations to get more details
- I maintain conversation context to provide better responses
- I'm designed to be empathetic and helpful

**When to See a Real Doctor:**
- For diagnosis of any condition
- For prescription medications
- For serious or persistent symptoms
- For emergency situations
- For personalized treatment plans
- For any concern that worries you

**My Purpose:**
I'm here to provide general health information and support. Think of me as a helpful resource for health questions, but always consult healthcare professionals for medical advice."""

            # Use LLM to generate contextual response
            prompt = f"""You are a helpful AI health assistant. A user is asking about your service, capabilities, or general information.

User question: "{question}"
Question category: {category}

Service Information:
{service_info}

Generate a natural, helpful response that:
1. Directly answers their question
2. Is friendly and conversational
3. Provides relevant information from the service details above
4. Is honest about limitations
5. Encourages appropriate use of the service
6. Keeps it concise (2-4 sentences unless more detail is needed)
7. Uses emojis sparingly if appropriate

Generate only the response message, no additional text."""

            response = self.llm.invoke(prompt)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error generating service response: {e}")
            # Fallback response
            if category == "capabilities":
                return "I'm an AI health assistant here to help answer your health-related questions! 🏥 I can provide information about symptoms, conditions, medications, and general health topics. However, I cannot diagnose conditions or prescribe medications - for that, please consult a healthcare professional. How can I help you today?"
            elif category == "limitations":
                return "While I can provide helpful health information, I have important limitations: I cannot diagnose medical conditions, prescribe medications, or replace professional medical advice. Always consult healthcare professionals for medical decisions. Is there a health question I can help you with?"
            else:
                return "I'm an AI health assistant designed to help answer health questions and provide general health information. I understand your concerns naturally and can have conversations to better help you. What would you like to know?"

    def _create_default_response(self, question: str, session) -> Dict[str, Any]:
        """
        Create a helpful default response when no specific handler matches.
        """
        # Save user message
        _ = self._save_user_message(session, question)

        # Generate a helpful redirect
        response_content = """I'm not quite sure how to help with that specific question, but I'm here to assist with health-related concerns! 😊

I can help you with:
- Questions about symptoms or how you're feeling
- General health information
- Medication questions
- Wellness and preventive health

You can also ask me about what I can do or my capabilities. What would you like to know?"""

        # Save assistant message
        assistant_message = self._save_assistant_message(
            session, response_content, confidence_score=0.5, source_type="default"
        )

        # Update session
        session.last_message_at = timezone.now()
        if not session.title or session.title == "New Chat":
            session.title = question[:50] + "..." if len(question) > 50 else question
        session.save()

        return {
            "success": True,
            "session_id": session.id,
            "message_id": assistant_message.id,
            "confidence_score": 0.5,
            "answer": response_content,
            "session_title": session.title,
        }

    def _is_followup_question(self, response: str) -> bool:
        """
        Detect if the assistant's response is asking a follow-up question.
        """
        response_lower = response.lower()
        question_indicators = [
            "?",
            "can you tell me",
            "could you",
            "what",
            "how",
            "when",
            "where",
            "which",
            "do you",
            "are you",
            "have you",
        ]
        return (
            any(indicator in response_lower for indicator in question_indicators)
            and "?" in response
        )

    def _get_or_create_session(self, user_id: int, session_id: Optional[int] = None):
        """
        Get or create a chat session for the user.
        """
        if session_id:
            return AIChatSession.objects.get(id=session_id, user_id=user_id)
        return AIChatSession.objects.create(user_id=user_id)

    def _save_user_message(self, session, content: str):
        """
        Save a user message to the session.
        """
        return AIChatMessage.objects.create(
            session=session, message_type="user", content=content
        )

    def _save_assistant_message(
        self,
        session,
        content: str,
        confidence_score: float = 0.8,
        source_type: str = "general",
    ):
        """
        Save an assistant message to the session.
        """
        return AIChatMessage.objects.create(
            session=session, message_type="assistant", content=content
        )

    def _generate_greeting_response(
        self, question: str, greeting_type: str, session: Any
    ) -> str:
        """
        Generate an appropriate greeting response using AI for natural, contextual responses.
        """
        try:
            # Use AI to generate a natural, contextual greeting response
            prompt = f"""You are a friendly and helpful AI health assistant. A user has sent you a greeting or conversational message.

User message: "{question}"
Greeting type: {greeting_type}

Generate a natural, warm, and appropriate response. Guidelines:
1. Be friendly and welcoming
2. Briefly introduce yourself as a health assistant
3. Let them know you're ready to help with health questions
4. Keep it concise (2-3 sentences max)
5. Use emojis sparingly (1-2 max) and appropriately
6. Match the tone of their message (formal/informal)
7. If it's a closing greeting, wish them well
8. If they're asking about you, briefly explain your role

Generate only the response message, no additional text or explanations."""

            response = self.llm.invoke(prompt)
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error generating AI greeting response: {e}")
            # Fallback to simple response
            if greeting_type == "closing":
                return "Goodbye! 👋 Take care of yourself. Feel free to come back if you have any health questions!"
            elif greeting_type == "polite":
                return "You're welcome! 😊 I'm glad I could help. Is there anything else you'd like to know about health?"
            elif greeting_type == "question_about_assistant":
                return "I'm a health assistant designed to help answer health-related questions. I can provide information about symptoms, treatments, medications, and general health topics. How can I help you today? 🏥"
            else:
                return "Hello! 👋 I'm here to help you with health-related questions. What would you like to know?"

    def _get_conversation_history(
        self, session, limit: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get recent conversation history from the session.
        Returns a list of messages with 'role' and 'content' keys.
        """
        messages = AIChatMessage.objects.filter(session=session).order_by(
            "-created_at"
        )[:limit]

        history = []
        for msg in reversed(messages):
            history.append(
                {
                    "role": msg.message_type,
                    "content": msg.content,
                }
            )
        return history

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """
        Create a standardized error response.
        """
        return {
            "success": False,
            "error": error_message,
            "answer": f"I apologize, but I encountered an error: {error_message}. Please try again or rephrase your question.",
        }
