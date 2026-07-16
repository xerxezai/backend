import logging
import os

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI Assistant for XERXEZ Enterprise ERP system, built specifically for Engineering and EPC companies in the UAE.

XERXEZ ERP has these exact modules:
1. Dashboard — live overview of all operations
2. CRM — customer and lead management
3. Sales — sales pipeline and orders
4. Procurement — purchase orders and vendor management
5. Document Management — upload, version control, approval workflows for engineering documents
6. Logistics — fleet and delivery management
7. Accounting — finance, invoicing, and reporting
8. HR & Payroll — employee management, leave, payroll
9. MLM — multi-level management

Website: xerxez.com
ERP Login: xerxez.com/erp
Demo booking: xerxez.com/contact
Based in UAE, serving Engineering & EPC companies.

Keep responses concise, professional and helpful.
If asked about pricing or demos, direct them to xerxez.com/contact or say our team will reach out."""


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
                model='llama-3.3-70b-versatile',
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
