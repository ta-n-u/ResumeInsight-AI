# core/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser


# -------------------------------------------------------------------
# 1. CUSTOM USER MODEL
# Extends Django's built-in User to add HR roles.
# -------------------------------------------------------------------
class User(AbstractUser):
    """
    Custom user model for ResumeInsight AI.
    Two roles: HR Manager and Super Admin.
    """

    ROLE_CHOICES = [
        ('hr_manager', 'HR Manager'),
        ('super_admin', 'Super Admin'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='hr_manager'
    )

    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def is_super_admin(self):
        return self.role == 'super_admin'

    def is_hr_manager(self):
        return self.role == 'hr_manager'


# -------------------------------------------------------------------
# 2. JOB DESCRIPTION MODEL
# HR Managers create job postings with required skills.
# -------------------------------------------------------------------
class JobDescription(models.Model):
    """
    Stores job postings created by HR Managers.
    """

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('draft', 'Draft'),
    ]

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='job_descriptions'
    )

    title           = models.CharField(max_length=255)
    department      = models.CharField(max_length=100, blank=True)
    description     = models.TextField()
    required_skills = models.TextField(
        help_text="Comma-separated list of required skills. e.g. Python, Django, SQL"
    )
    experience_required = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. 2-3 years"
    )
    education_required = models.CharField(
        max_length=255,
        blank=True,
        help_text="e.g. Bachelor's in Computer Science"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active'
    )

    # ── Matching Score Weights (HR configurable) ──
    skill_weight = models.FloatField(
        default=0.50,
        help_text="Weight for skill overlap (default 50%)"
    )
    semantic_weight = models.FloatField(
        default=0.20,
        help_text="Weight for semantic similarity (default 20%)"
    )
    education_weight = models.FloatField(
        default=0.20,
        help_text="Weight for education match (default 20%)"
    )
    experience_weight = models.FloatField(
        default=0.10,
        help_text="Weight for experience match (default 10%)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} — {self.department}"

    def get_skills_list(self):
        """Returns required skills as a clean Python list."""
        return [skill.strip() for skill in self.required_skills.split(',')]


# -------------------------------------------------------------------
# 3. CANDIDATE MODEL
# Stores candidate personal info. Supports Blind Screening.
# -------------------------------------------------------------------
class Candidate(models.Model):
    """
    Stores candidate profile data.
    In Blind Mode, name/email/phone are hidden from the HR view.
    """

    # Real personal data (used in normal mode)
    full_name   = models.CharField(max_length=255)
    email       = models.EmailField(blank=True)
    phone       = models.CharField(max_length=20, blank=True)

    # Blind screening alias — auto-generated (e.g. Candidate_001)
    blind_id    = models.CharField(max_length=50, unique=True, blank=True)

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='candidates'
    )

    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        """Auto-generate a blind_id before saving if not already set."""
        if not self.blind_id:
            # Save first to get a primary key, then generate the ID
            super().save(*args, **kwargs)
            self.blind_id = f"Candidate_{self.pk:03d}"
            # Update only the blind_id field
            Candidate.objects.filter(pk=self.pk).update(blind_id=self.blind_id)
        else:
            super().save(*args, **kwargs)


# -------------------------------------------------------------------
# 4. RESUME MODEL
# Stores the uploaded PDF and its extracted raw text.
# -------------------------------------------------------------------
class Resume(models.Model):
    """
    Stores the uploaded resume PDF and all NLP-extracted data.
    One candidate can have one resume per job application.
    """

    candidate   = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name='resumes'
    )

    job         = models.ForeignKey(
        JobDescription,
        on_delete=models.CASCADE,
        related_name='resumes'
    )

    # The actual uploaded PDF file
    pdf_file    = models.FileField(upload_to='resumes/')

    # Raw text extracted from the PDF by pdfplumber
    raw_text    = models.TextField(blank=True)

    # NLP extracted fields (populated after processing)
    extracted_skills     = models.TextField(blank=True,
                           help_text="Comma-separated skills found in resume")
    extracted_education  = models.TextField(blank=True)
    extracted_experience = models.TextField(blank=True)

    # Processing status
    is_processed = models.BooleanField(default=False)

    uploaded_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Resume of {self.candidate.full_name} for {self.job.title}"

    def get_extracted_skills_list(self):
        """Returns extracted skills as a clean Python list."""
        return [skill.strip() for skill in self.extracted_skills.split(',') if skill.strip()]


# -------------------------------------------------------------------
# 5. MATCH RESULT MODEL
# Stores the cosine similarity score for each resume vs job.
# -------------------------------------------------------------------
class MatchResult(models.Model):
    """
    Stores the NLP matching score between a resume and a job description.
    This is the core output of the matching engine.
    """

    resume      = models.OneToOneField(
        Resume,
        on_delete=models.CASCADE,
        related_name='match_result'
    )

    job         = models.ForeignKey(
        JobDescription,
        on_delete=models.CASCADE,
        related_name='match_results'
    )

    candidate   = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name='match_results'
    )

    # The final similarity score (0.00 to 1.00)
    similarity_score = models.FloatField(default=0.0)

    # Percentage version for easy display (0 to 100)
    match_percentage = models.FloatField(default=0.0)

    # Skills found in resume that match the JD
    matched_skills  = models.TextField(blank=True)

    # Skills in JD that are missing from the resume
    missing_skills  = models.TextField(blank=True)

    # Ranking position among all candidates for this job
    rank            = models.PositiveIntegerField(default=0)

    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-similarity_score']   # highest score first

    def __str__(self):
        return f"{self.candidate.full_name} → {self.job.title} | Score: {self.match_percentage:.1f}%"

    def get_matched_skills_list(self):
        return [s.strip() for s in self.matched_skills.split(',') if s.strip()]

    def get_missing_skills_list(self):
        return [s.strip() for s in self.missing_skills.split(',') if s.strip()]


# -------------------------------------------------------------------
# 6. SKILL MODEL
# Master list of skills — used for the Custom Skill Library feature.
# -------------------------------------------------------------------
class Skill(models.Model):
    """
    A master library of skills known to the system.
    HR Managers can add custom skills to expand NLP recognition.
    """

    CATEGORY_CHOICES = [
        ('technical', 'Technical'),
        ('soft', 'Soft Skill'),
        ('tool', 'Tool / Software'),
        ('language', 'Programming Language'),
        ('other', 'Other'),
    ]

    name        = models.CharField(max_length=100, unique=True)
    category    = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='technical'
    )
    added_by    = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='skills_added'
    )

    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


# -------------------------------------------------------------------
# 7. NOTIFICATION MODEL
# Simple in-app notifications for HR users.
# -------------------------------------------------------------------
class Notification(models.Model):
    """
    Stores notifications for HR users.
    e.g. 'Resume processed', 'New candidate ranked'.
    """

    user        = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    message     = models.TextField()
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']   # newest first

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:50]}"