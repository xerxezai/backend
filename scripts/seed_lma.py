"""
Seed script for LMA (Learning Management Application)
Creates courses, modules, lessons and sets up instructor profiles.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xerxez_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.lma.models import LMAProfile, Course, Module, Lesson

User = get_user_model()

INSTRUCTOR_USERNAMES = ['Danish', 'Tanzeem']

# ── Set up instructor profiles ──────────────────────────────────────────────
for username in INSTRUCTOR_USERNAMES:
    try:
        user = User.objects.get(username=username)
        profile, _ = LMAProfile.objects.get_or_create(user=user)
        profile.lma_role = 'both'
        profile.can_access_student = True
        profile.can_access_instructor = True
        profile.save()
        print(f'✅ LMA profile set for {username}')
    except User.DoesNotExist:
        print(f'⚠️  User {username} not found — skipping profile')

# ── Get instructor (Tanzeem) ─────────────────────────────────────────────────
try:
    instructor = User.objects.get(username='Tanzeem')
except User.DoesNotExist:
    try:
        instructor = User.objects.get(username='Danish')
    except User.DoesNotExist:
        print('❌ No instructor user found. Run create_railway_users.py first.')
        exit(1)

# ── Course 1: Full Stack AI Development ─────────────────────────────────────
course1, created1 = Course.objects.get_or_create(
    title='Full Stack AI Development',
    defaults={
        'description': 'Build production-ready AI systems from scratch — LLMs, RAG pipelines, API development, and enterprise deployment patterns. Hands-on from day one with real models and real data.',
        'instructor': instructor,
        'category': 'AI & ML',
        'level': 'intermediate',
        'price': 4999,
        'badge': 'BESTSELLER',
        'header_color': 'cream',
        'rating': 4.8,
        'total_ratings': 247,
        'total_students': 1200,
        'hours': 60,
        'lessons': 48,
        'tech_stack': ['Python', 'LangChain', 'OpenAI', 'FastAPI'],
        'status': 'published',
    }
)
if not created1:
    # Update existing
    Course.objects.filter(id=course1.id).update(
        instructor=instructor, badge='BESTSELLER', header_color='cream',
        rating=4.8, total_ratings=247, total_students=1200,
        hours=60, lessons=48, status='published',
        tech_stack=['Python', 'LangChain', 'OpenAI', 'FastAPI'],
    )
    course1.refresh_from_db()

print(f'{"✅ Created" if created1 else "🔄 Updated"}: {course1.title}')

# Modules for course 1
MODULES_C1 = [
    ('Introduction to AI & LLMs',      4,  180, [
        ('What is Generative AI?',          45, True),
        ('LLM Architecture Deep Dive',      40, False),
        ('Prompt Engineering Fundamentals', 55, False),
        ('Setting Up Your AI Dev Environment', 40, False),
    ]),
    ('Python for AI Development',       8,  320, [
        ('Python Refresher for AI',         40, True),
        ('NumPy & Pandas for Data',         45, False),
        ('Working with APIs in Python',     35, False),
        ('Async Python for AI Services',    40, False),
        ('Type Hints & Pydantic Models',    35, False),
        ('Error Handling & Logging',        30, False),
        ('Testing AI Applications',         55, False),
        ('Code Review & Best Practices',    40, False),
    ]),
    ('LangChain & RAG Pipelines',       10, 420, [
        ('LangChain Fundamentals',          45, True),
        ('Chains & Agents',                 40, False),
        ('Vector Stores Introduction',      35, False),
        ('Embeddings & Semantic Search',    45, False),
        ('Building RAG Systems',            55, False),
        ('Retrieval Strategies',            40, False),
        ('Document Processing Pipelines',   45, False),
        ('Multi-Step RAG Chains',           40, False),
        ('Evaluation & Testing RAG',        50, False),
        ('Production RAG Architecture',     45, False),
    ]),
    ('OpenAI API Integration',          8,  300, [
        ('OpenAI API Quickstart',           35, True),
        ('Chat Completions Deep Dive',      40, False),
        ('Function Calling & Tools',        45, False),
        ('Vision & Multimodal APIs',        35, False),
        ('Embeddings API',                  40, False),
        ('Fine-Tuning Models',              50, False),
        ('Rate Limiting & Cost Management', 30, False),
        ('OpenAI in Production',            25, False),
    ]),
    ('FastAPI Backend Development',     10, 400, [
        ('FastAPI Quickstart',              40, True),
        ('Routing & Request Handling',      35, False),
        ('Pydantic Data Validation',        40, False),
        ('Database Integration',            45, False),
        ('Authentication & JWT',            45, False),
        ('Background Tasks',                35, False),
        ('WebSockets for Real-time AI',     50, False),
        ('Middleware & Dependencies',       35, False),
        ('API Documentation with OpenAPI',  35, False),
        ('Testing FastAPI Apps',            40, False),
    ]),
    ('Deployment & Production',         8,  280, [
        ('Docker Containerization',         35, True),
        ('Docker Compose for AI Stack',     40, False),
        ('CI/CD with GitHub Actions',       40, False),
        ('Deploying to AWS EC2',            35, False),
        ('AWS Lambda for Serverless AI',    40, False),
        ('Monitoring with Prometheus',      35, False),
        ('Logging & Observability',         30, False),
        ('Production Checklist',            25, False),
    ]),
]

for m_title, m_lessons, m_dur, lessons_data in MODULES_C1:
    module, _ = Module.objects.get_or_create(
        course=course1,
        title=m_title,
        defaults={'order': MODULES_C1.index((m_title, m_lessons, m_dur, lessons_data)) + 1, 'duration': m_dur}
    )
    for l_idx, (l_title, l_dur, l_free) in enumerate(lessons_data):
        Lesson.objects.get_or_create(
            module=module,
            title=l_title,
            defaults={'duration': l_dur, 'order': l_idx + 1, 'is_free_preview': l_free}
        )

print(f'✅ Modules & lessons seeded for: {course1.title}')

# ── Course 2: MLOps ──────────────────────────────────────────────────────────
course2, created2 = Course.objects.get_or_create(
    title='MLOps – Machine Learning Operations',
    defaults={
        'description': 'Automate the full ML lifecycle — from training pipelines to production monitoring with Kubernetes, MLflow, and cloud platforms. Build real MLOps infrastructure during the course.',
        'instructor': instructor,
        'category': 'DevSecOps & AI',
        'level': 'advanced',
        'price': 3999,
        'badge': 'NEW',
        'header_color': 'blue',
        'rating': 4.9,
        'total_ratings': 89,
        'total_students': 450,
        'hours': 50,
        'lessons': 40,
        'tech_stack': ['Kubernetes', 'MLflow', 'Docker', 'AWS'],
        'status': 'published',
    }
)
if not created2:
    Course.objects.filter(id=course2.id).update(
        instructor=instructor, badge='NEW', header_color='blue',
        rating=4.9, total_ratings=89, total_students=450,
        hours=50, lessons=40, status='published',
        tech_stack=['Kubernetes', 'MLflow', 'Docker', 'AWS'],
    )
    course2.refresh_from_db()

print(f'{"✅ Created" if created2 else "🔄 Updated"}: {course2.title}')

MODULES_C2 = [
    ('MLOps Fundamentals',            5, 200, [
        ('What is MLOps?',                  40, True),
        ('ML System Design',                45, False),
        ('MLOps Maturity Model',            35, False),
        ('Setting Up Your MLOps Stack',     45, False),
        ('MLOps Tools Overview',            35, False),
    ]),
    ('Kubernetes for ML',             8, 320, [
        ('Kubernetes Core Concepts',        40, True),
        ('Pods, Services & Deployments',    45, False),
        ('Kubernetes for AI Workloads',     40, False),
        ('Helm Charts',                     35, False),
        ('GPU Scheduling',                  45, False),
        ('Kubeflow Introduction',           40, False),
        ('Auto-scaling ML Services',        40, False),
        ('K8s Monitoring',                  35, False),
    ]),
    ('MLflow Experiment Tracking',    7, 280, [
        ('MLflow Quickstart',               40, True),
        ('Experiment Tracking',             45, False),
        ('Model Registry',                  40, False),
        ('Projects & Reproducibility',      35, False),
        ('MLflow on AWS',                   45, False),
        ('Team Collaboration in MLflow',    40, False),
        ('MLflow vs Alternatives',          35, False),
    ]),
    ('Docker & Containerization',     8, 320, [
        ('Docker Fundamentals',             40, True),
        ('Dockerfile Best Practices',       35, False),
        ('Docker for ML Models',            45, False),
        ('Docker Compose',                  40, False),
        ('Container Security',              35, False),
        ('GPU Containers',                  45, False),
        ('Container Registries',            40, False),
        ('Docker in CI/CD',                 40, False),
    ]),
    ('AWS SageMaker',                 7, 280, [
        ('SageMaker Overview',              40, True),
        ('Training Jobs',                   45, False),
        ('SageMaker Pipelines',             40, False),
        ('Model Deployment & Endpoints',    45, False),
        ('SageMaker Studio',                35, False),
        ('Cost Optimization',               40, False),
        ('SageMaker vs Self-Managed',       35, False),
    ]),
    ('Monitoring & Production',       5, 200, [
        ('ML Model Drift Detection',        40, True),
        ('Prometheus & Grafana',            45, False),
        ('Alerting for ML Systems',         35, False),
        ('A/B Testing Models',              45, False),
        ('Incident Response for ML',        35, False),
    ]),
]

for m_title, m_lessons, m_dur, lessons_data in MODULES_C2:
    module, _ = Module.objects.get_or_create(
        course=course2,
        title=m_title,
        defaults={'order': MODULES_C2.index((m_title, m_lessons, m_dur, lessons_data)) + 1, 'duration': m_dur}
    )
    for l_idx, (l_title, l_dur, l_free) in enumerate(lessons_data):
        Lesson.objects.get_or_create(
            module=module,
            title=l_title,
            defaults={'duration': l_dur, 'order': l_idx + 1, 'is_free_preview': l_free}
        )

print(f'✅ Modules & lessons seeded for: {course2.title}')
print('\n🎉 LMA seed complete!')
