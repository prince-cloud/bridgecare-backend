from typing import Dict, List, Optional
from loguru import logger
from django.conf import settings
from langchain_openai import ChatOpenAI


class AgentTools:
    """Tools for answering questions on health and providing neccesary presbcriptions and symptoms and helath related issues"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o"),
            openai_api_key=getattr(settings, "OPENAI_API_KEY", ""),
            temperature=0.3,
        )

    def get_health_related_info(
        self, query: str, conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Get intelligent health related information based on question intent.
        Supports conversation context and can ask follow-up questions to better understand the user.
        """
        try:
            # Use AI to understand the question and provide relevant information
            prompt = self.create_health_related_prompt(query, conversation_history)
            response = self.llm.invoke(prompt)

            return response.content.strip()

        except Exception as e:
            logger.error(f"Error getting health related info: {str(e)}")
            # Fallback to general info if AI fails
            return "I'm sorry, I don't have enough information to answer that question. Could you provide more details about what you're experiencing?"

    def create_health_related_prompt(
        self, query: str, conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Create an intelligent prompt for understanding health related questions.
        Includes conversation context for natural follow-up questions.
        """
        # Build conversation context
        context_section = ""
        if conversation_history and len(conversation_history) > 1:
            context_lines = []
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    context_lines.append(f"User: {content}")
                elif role == "assistant":
                    context_lines.append(f"Assistant: {content}")
            if context_lines:
                context_section = f"\n\nPrevious conversation:\n" + "\n".join(
                    context_lines
                )

        return f"""You are a compassionate and knowledgeable AI health assistant. Your role is to help users understand their health concerns, symptoms, and questions about prescriptions and medications.

Current User Question: "{query}"
{context_section}

Your approach:
1. **Natural Understanding**: Understand the user's intent naturally, even if they don't use medical terminology. For example:
   - "I don't feel well" → Ask about specific symptoms
   - "My head hurts" → Ask about duration, severity, location
   - "What should I take?" → Ask what symptoms they're experiencing

2. **Ask Clarifying Questions**: If the user's question is vague or you need more information to provide helpful guidance, naturally ask follow-up questions such as:
   - "Can you tell me more about [specific symptom]?"
   - "How long have you been experiencing this?"
   - "Are there any other symptoms you're noticing?"
   - "What medications are you currently taking?"

3. **Provide Helpful Information**: When you have enough context:
   - Explain symptoms in understandable terms
   - Provide general health information
   - Suggest when to consult a healthcare professional
   - Discuss medication considerations (but never prescribe)

4. **Important Guidelines**:
   - Never provide a diagnosis or prescribe medications
   - Always recommend consulting a healthcare professional for serious concerns
   - Use clear, empathetic language
   - Use emojis sparingly and appropriately (🏥 💊 🤒 😊)
   - If the question isn't health-related, politely redirect

5. **Response Style**:
   - Be conversational and natural
   - Show empathy and understanding
   - Ask one or two follow-up questions at a time (not overwhelming)
   - Provide actionable information when possible

Please provide a helpful, natural response to the user's health question. If you need more information, ask clarifying questions in a conversational way."""
