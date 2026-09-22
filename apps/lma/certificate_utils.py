"""
Certificate rendering — draws the instructor-uploaded template as a full-page
background on a reportlab PDF canvas, then overlays the student's name,
course title, completion date, and the certificate's unique verification ID.

Only image templates (PNG/JPG) can be used as a pixel background — reportlab
can draw raster images directly via ImageReader, but not PDF pages, and this
app doesn't bundle a PDF-rasterizing dependency (poppler/PyMuPDF). A PDF
template is still accepted for upload/preview/download, but auto-generation
requires an image template; see `TemplateNotRenderable`.
"""
import io

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas


class TemplateNotRenderable(Exception):
    """Raised when the course's certificate_template can't be used as a
    pixel background (e.g. it's a PDF, not an image)."""


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


def _is_image_template(template_field) -> bool:
    name = (template_field.name or '').lower()
    return any(name.endswith(ext) for ext in IMAGE_EXTENSIONS)


def generate_certificate_file(certificate):
    """Renders `certificate` (a Certificate instance with .student/.course
    already set) using its course's certificate_template, and saves the
    result onto `certificate.certificate_file`. Raises TemplateNotRenderable
    if the course has no template, or the template isn't a raster image."""
    course = certificate.course
    template_field = course.certificate_template
    if not template_field:
        raise TemplateNotRenderable('This course has no certificate template uploaded yet.')
    if not _is_image_template(template_field):
        raise TemplateNotRenderable('Certificate templates must be PNG or JPG to auto-generate a certificate.')

    template_field.open('rb')
    try:
        image_bytes = template_field.read()
    finally:
        template_field.close()

    pil_image = Image.open(io.BytesIO(image_bytes))
    pil_image = pil_image.convert('RGB')
    width_px, height_px = pil_image.size

    buffer = io.BytesIO()
    page_size = (width_px, height_px)
    c = pdf_canvas.Canvas(buffer, pagesize=page_size)
    c.drawImage(ImageReader(pil_image), 0, 0, width=width_px, height=height_px)

    student_name = certificate.student.get_full_name() or certificate.student.username
    course_title = course.title
    completion_date = timezone.now().strftime('%B %d, %Y')
    verification_id = str(certificate.unique_id)

    center_x = width_px / 2

    c.setFillColorRGB(0.03, 0.1, 0.2)
    c.setFont('Helvetica-Bold', max(24, round(height_px * 0.06)))
    c.drawCentredString(center_x, height_px * 0.52, student_name)

    c.setFont('Helvetica', max(14, round(height_px * 0.03)))
    c.drawCentredString(center_x, height_px * 0.42, course_title)

    c.setFont('Helvetica', max(10, round(height_px * 0.018)))
    c.drawCentredString(center_x, height_px * 0.32, f"Completed on {completion_date}")

    c.setFont('Helvetica', max(7, round(height_px * 0.012)))
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(center_x, height_px * 0.04, f"Certificate ID: {verification_id}")

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"certificate-{certificate.unique_id}.pdf"
    certificate.certificate_file.save(filename, ContentFile(buffer.read()), save=False)
    certificate.save(update_fields=['certificate_file'])
