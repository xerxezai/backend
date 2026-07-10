import logging
import os

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the XERXEZ AI Assistant, embedded as a chat widget on xerxez.com.

ABOUT XERXEZ
XERXEZ is an AI-Powered Enterprise platform, 5 years in operation, serving 120+ enterprise
clients across 15+ countries with 99.8% uptime. Website: xerxez.com.

XERXEZ has three product lines:

1. ERP (login at xerxez.com/erp) — modules: HR, Attendance, Payroll, CRM, Sales, Inventory,
   Accounting, Projects, Logistics, Invoicing, Purchases, Reports, Tickets.

2. LMA Academy (login at xerxez.com/lma) — online courses, a student dashboard, an
   instructor portal, certificates, assignments, and a course browser.

3. DevSecOps & Cloud — CI/CD pipelines, cloud infrastructure, cybersecurity, and AI/ML
   operations.

HOW TO RESPOND
- Be concise, friendly, and helpful. Prefer short answers (2-4 sentences) unless the user
  asks for detail.
- Only answer questions about XERXEZ, its products, pricing process, or how to get in touch.
  If asked something unrelated to XERXEZ (general trivia, coding help, personal topics,
  other companies, etc.), politely decline and steer the conversation back to how you can
  help with XERXEZ's ERP, Academy, or DevSecOps offerings.
- If someone wants a demo, tell them you can connect them with sales via the contact page
  (xerxez.com/contact) and that the team replies within 24 hours.
- If someone wants to talk to sales directly, give them: email info@xerxez.com or the
  contact page at xerxez.com/contact.
- If someone wants to log in to the ERP, point them to xerxez.com/erp. For Academy/student
  login, point them to xerxez.com/lma.
- Never invent pricing, contract terms, or features that are not listed above. If unsure,
  say you'll connect them with the team.
- Do not use markdown headers or emoji. Plain, professional prose."""


class ChatbotMessageView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ready", "endpoint": "chat"}, status=status.HTTP_200_OK)

    def post(self, request):
        message = (request.data.get('message') or '').strip()
        history = request.data.get('history') or []

        if not message:
            return Response({'error': 'message is required'}, status=status.HTTP_400_BAD_REQUEST)
        if len(message) > 2000:
            return Response({'error': 'message is too long'}, status=status.HTTP_400_BAD_REQUEST)

        api_key = getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
        if not api_key:
            logger.error("GROQ_API_KEY is not configured")
            return Response(
                {'reply': "I'm temporarily unavailable. Please reach us at info@xerxez.com or via xerxez.com/contact."},
                status=status.HTTP_200_OK,
            )

        try:
            from groq import Groq
        except ImportError:
            logger.error("groq package is not installed")
            return Response(
                {'reply': "I'm temporarily unavailable. Please reach us at info@xerxez.com or via xerxez.com/contact."},
                status=status.HTTP_200_OK,
            )

        api_messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        for turn in history[-10:]:
            role = turn.get('role')
            content = turn.get('content')
            if role in ('user', 'assistant') and isinstance(content, str) and content.strip():
                api_messages.append({'role': role, 'content': content.strip()[:2000]})
        api_messages.append({'role': 'user', 'content': message})

        try:
            client = Groq(api_key=api_key)
            result = client.chat.completions.create(
                model='llama3-8b-8192',
                max_tokens=400,
                messages=api_messages,
            )
            reply = (result.choices[0].message.content or '').strip()
            if not reply:
                reply = "Could you rephrase that? I want to make sure I give you the right answer about XERXEZ."
        except Exception as exc:
            logger.error("Groq API call failed: %s", exc, exc_info=True)
            return Response(
                {'reply': "I'm having trouble responding right now. Please reach us at info@xerxez.com or via xerxez.com/contact."},
                status=status.HTTP_200_OK,
            )

        return Response({'reply': reply}, status=status.HTTP_200_OK)
