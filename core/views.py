# core/views.py
import os
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import HRSignupForm, HRLoginForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import HRSignupForm, HRLoginForm, JobDescriptionForm
from .models import JobDescription
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import HRSignupForm, HRLoginForm, JobDescriptionForm, ResumeUploadForm
from .models import JobDescription, Resume, Candidate
from .services import process_resume
from .services import process_resume, run_nlp_pipeline
from .services import process_resume, run_nlp_pipeline, run_matching_engine
from .models import JobDescription, Resume, Candidate, MatchResult
from django.contrib.auth import get_user_model
User = get_user_model()
from .services import (
    extract_text_from_pdf, run_matching_engine, create_notification,
    extract_candidate_name, extract_email, extract_phone,
    clean_text, extract_text_from_image, process_resume
)


# -------------------------------------------------------------------
# Signup View
# -------------------------------------------------------------------
def signup_view(request):
    """
    Handles new HR Manager registration.
    """
    # If user is already logged in, send to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = HRSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)    # log them in immediately after signup
            create_notification(user, f'Welcome to ResumeInsight AI! Your HR Manager account has been created.')
            messages.success(request, f'Welcome, {user.first_name}! Your account has been created.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = HRSignupForm()

    return render(request, 'auth/signup.html', {'form': form})


# -------------------------------------------------------------------
# Login View
# -------------------------------------------------------------------
def login_view(request):
    """
    Handles HR user login.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = HRLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            create_notification(user, f'👋 Welcome back, {user.get_full_name() or user.username}! You signed in successfully.')
            # Send welcome email
            from django.core.mail import send_mail
            try:
                send_mail(
                    subject='Welcome back to ResumeInsight AI',
                    message=f'''Hi {user.get_full_name() or user.username},
            You have successfully signed in to ResumeInsight AI.

            Account Details:
            - Username: {user.username}
            - Role: {user.get_role_display()}
            - Login Time: {user.last_login}

            If this was not you, please contact your system administrator immediately.

            Best regards,
            ResumeInsight AI Team''',
                from_email='noreply@resumeinsight.ai',
                recipient_list=[user.email] if user.email else [],
                fail_silently=True
                )
            except Exception:
                pass  # Never break login if email fails
                


            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = HRLoginForm()

    return render(request, 'auth/login.html', {'form': form})


# -------------------------------------------------------------------
# Logout View
# -------------------------------------------------------------------
def logout_view(request):
    """
    Logs out the user and redirects to the landing page.
    """
    from django.contrib.auth import logout
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('landing')


# -------------------------------------------------------------------
# Dashboard View (placeholder for now)
# -------------------------------------------------------------------
@login_required
def dashboard_view(request):
    """
    HR Dashboard with summary stats and chart data.
    """
    from .models import JobDescription, Resume, Candidate, MatchResult
    from django.db.models import Count, Avg
    import json

    user = request.user

    # ── Basic Stats ──
    total_jobs       = JobDescription.objects.filter(created_by=user).count()
    active_jobs      = JobDescription.objects.filter(created_by=user, status='active').count()
    total_resumes    = Resume.objects.filter(job__created_by=user).count()
    processed        = Resume.objects.filter(job__created_by=user, is_processed=True).count()
    total_candidates = Candidate.objects.filter(uploaded_by=user).count()
    total_matches    = MatchResult.objects.filter(job__created_by=user).count()

    # ── Top Ranked Candidates (for existing table) ──
    top_matches = MatchResult.objects.filter(
        job__created_by=user
    ).select_related('candidate', 'job').order_by('-match_percentage')[:5]

    # ── Recent Resumes ──
    recent_resumes = Resume.objects.filter(
        job__created_by=user
    ).select_related('candidate', 'job').order_by('-uploaded_at')[:5]

    # ────────────────────────────────
    # CHART DATA
    # ────────────────────────────────

   # Chart 1 — Match Score Distribution (Bar)
    matches = MatchResult.objects.filter(job__created_by=user)
    score_0_25  = matches.filter(match_percentage__lt=25).count()
    score_25_50 = matches.filter(match_percentage__gte=25, match_percentage__lt=50).count()
    score_50_75 = matches.filter(match_percentage__gte=50, match_percentage__lt=75).count()
    score_75_100= matches.filter(match_percentage__gte=75).count()

    # Chart 2 — Resume Processing Status (Doughnut)
    pending_resumes = total_resumes - processed

    # Chart 3 — Candidates per Job (Bar)
    jobs_with_counts = JobDescription.objects.filter(
        created_by=user
    ).annotate(
        candidate_count=Count('resumes')
    ).order_by('-candidate_count')[:6]

    candidates_per_job = {
        'labels': [j.title[:20] for j in jobs_with_counts],
        'data'  : [j.candidate_count for j in jobs_with_counts],
    }

    # Chart 4 — Top Required Skills (Horizontal Bar)
    all_jobs    = JobDescription.objects.filter(created_by=user)
    skill_count = {}
    for job in all_jobs:
        for skill in job.get_skills_list():
            skill = skill.strip()
            if skill:
                skill_count[skill] = skill_count.get(skill, 0) + 1

    # Convert to list of dicts for template
    top_skills = [
        {'name': name, 'count': count}
        for name, count in sorted(skill_count.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    return render(request, 'dashboard.html', {
        # Stats
        'total_jobs'       : total_jobs,
        'active_jobs'      : active_jobs,
        'total_resumes'    : total_resumes,
        'processed_resumes': processed,
        'pending_resumes'  : pending_resumes,
        'total_candidates' : total_candidates,
        'total_matches'    : total_matches,

        # Table data
        'top_candidates'   : top_matches,
        'recent_resumes'   : recent_resumes,
        'jobs'             : JobDescription.objects.filter(
                                created_by=user
                             ).order_by('-created_at')[:5],

        # Chart data
        'score_0_25'        : score_0_25,
        'score_25_50'       : score_25_50,
        'score_50_75'       : score_50_75,
        'score_75_100'      : score_75_100,
        'top_skills'        : top_skills,
        'candidates_per_job': json.dumps(candidates_per_job),
    })


@login_required
def analytics_view(request):
    """
    Full analytics page with detailed charts and insights.
    """
    from .models import JobDescription, Resume, Candidate, MatchResult
    from django.db.models import Count, Avg
    import json

    user    = request.user
    matches = MatchResult.objects.filter(job__created_by=user)

    # ── Summary Numbers ──
    total_candidates = Candidate.objects.filter(uploaded_by=user).count()
    avg_score        = matches.aggregate(Avg('match_percentage'))['match_percentage__avg'] or 0
    top_score        = matches.order_by('-match_percentage').first()
    total_jobs       = JobDescription.objects.filter(created_by=user).count()

    # ── Chart 1: Score Distribution ──
    score_dist = {
        'labels': ['0–25%', '26–50%', '51–75%', '76–100%'],
        'data'  : [
            matches.filter(match_percentage__lt=25).count(),
            matches.filter(match_percentage__gte=25, match_percentage__lt=50).count(),
            matches.filter(match_percentage__gte=50, match_percentage__lt=75).count(),
            matches.filter(match_percentage__gte=75).count(),
        ],
        'colors': ['#EF4444', '#F59E0B', '#3B82F6', '#10B981'],
    }

    # ── Chart 2: Processing Status ──
    total_resumes = Resume.objects.filter(job__created_by=user).count()
    processed     = Resume.objects.filter(job__created_by=user, is_processed=True).count()
    processing_data = {
        'labels': ['Processed', 'Unprocessed'],
        'data'  : [processed, total_resumes - processed],
    }

    # ── Chart 3: Candidates per Job ──
    jobs_data = JobDescription.objects.filter(
        created_by=user
    ).annotate(
        candidate_count=Count('match_results', distinct=True),
        avg_score=Avg('match_results__match_percentage')
    ).order_by('-candidate_count')

    candidates_per_job = {
        'labels': [j.title[:25] for j in jobs_data],
        'data'  : [j.candidate_count for j in jobs_data],
    }

    # ── Chart 4: Top Skills in Demand ──
    all_jobs   = JobDescription.objects.filter(created_by=user)
    skill_freq = {}
    for job in all_jobs:
        for skill in job.get_skills_list():
            skill = skill.strip()
            if skill:
                skill_freq[skill] = skill_freq.get(skill, 0) + 1

    top_skills = sorted(skill_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    skills_chart = {
        'labels': [s[0] for s in top_skills],
        'data'  : [s[1] for s in top_skills],
    }

    # ── Chart 5: Average Score per Job ──
    avg_per_job = {
        'labels': [j.title[:25] for j in jobs_data if j.avg_score],
        'data'  : [round(j.avg_score, 1) for j in jobs_data if j.avg_score],
    }

    # ── Top 5 Candidates Table ──
    top_candidates = matches.select_related(
        'candidate', 'job'
    ).order_by('-match_percentage')[:5]

    return render(request, 'analytics.html', {
        'total_candidates'  : total_candidates,
        'avg_score'         : round(avg_score, 1),
        'top_score'         : top_score,
        'total_jobs'        : total_jobs,
        'total_resumes'     : total_resumes,

        # Charts
        'score_dist'        : json.dumps(score_dist),
        'processing_data'   : json.dumps(processing_data),
        'candidates_per_job': json.dumps(candidates_per_job),
        'skills_chart'      : json.dumps(skills_chart),
        'avg_per_job'       : json.dumps(avg_per_job),

        # Table
        'top_candidates'    : top_candidates,
        'jobs_data'         : jobs_data,
    })




# -------------------------------------------------------------------
# Job Description Views
# -------------------------------------------------------------------

@login_required
def job_list_view(request):
    """
    Shows all job descriptions created by the logged-in HR Manager.
    Super Admin can see all jobs.
    """
    if request.user.is_super_admin():
        jobs = JobDescription.objects.all().order_by('-created_at')
    else:
        jobs = JobDescription.objects.filter(
            created_by=request.user
        ).order_by('-created_at')

    return render(request, 'jobs/job_list.html', {'jobs': jobs})


@login_required
def job_create_view(request):
    """
    Allows HR Manager to create a new job description.
    """
    if request.method == 'POST':
        form = JobDescriptionForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.created_by = request.user   # assign current HR user
            job.save()
            messages.success(request, f'Job "{job.title}" created successfully!')
            return redirect('job_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = JobDescriptionForm()

    return render(request, 'jobs/job_create.html', {'form': form})


@login_required
def job_detail_view(request, pk):
    """
    Shows full details of a single job description.
    """
    job = get_object_or_404(JobDescription, pk=pk)

    return render(request, 'jobs/job_detail.html', {
        'job': job,
        'skills_list': job.get_skills_list()
    })


@login_required
def job_edit_view(request, pk):
    """
    Allows HR Manager to edit an existing job description.
    """
    job = get_object_or_404(JobDescription, pk=pk)

    # Only the creator or super admin can edit
    if job.created_by != request.user and not request.user.is_super_admin():
        messages.error(request, 'You do not have permission to edit this job.')
        return redirect('job_list')

    if request.method == 'POST':
        form = JobDescriptionForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, f'Job "{job.title}" updated successfully!')
            return redirect('job_detail', pk=job.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = JobDescriptionForm(instance=job)

    return render(request, 'jobs/job_edit.html', {'form': form, 'job': job})


@login_required
def job_delete_view(request, pk):
    """
    Deletes a job description after confirmation.
    """
    job = get_object_or_404(JobDescription, pk=pk)

    # Only the creator or super admin can delete
    if job.created_by != request.user and not request.user.is_super_admin():
        messages.error(request, 'You do not have permission to delete this job.')
        return redirect('job_list')

    if request.method == 'POST':
        job_title = job.title
        job.delete()
        messages.success(request, f'Job "{job_title}" deleted successfully!')
        return redirect('job_list')

    return render(request, 'jobs/job_detail.html', {'job': job})


# -------------------------------------------------------------------
# Resume Views
# -------------------------------------------------------------------

@login_required
def resume_upload_view(request):
    """
    Handles resume upload via three methods:
    1. PDF file upload (text-based or scanned)
    2. Image file upload (JPG, PNG) with OCR
    3. Manual text paste
    """
    if request.method == 'POST':
        job_id      = request.POST.get('job')
        input_type  = request.POST.get('input_type', 'pdf')
        manual_text = request.POST.get('manual_text', '').strip()
        pdf_files   = request.FILES.getlist('pdf_files')
        image_files = request.FILES.getlist('image_files')

        # ── Validate job ──
        if not job_id:
            messages.error(request, 'Please select a job position.')
            return redirect('resume_upload')

        try:
            job = JobDescription.objects.get(pk=job_id, created_by=request.user)
        except JobDescription.DoesNotExist:
            messages.error(request, 'Invalid job selected.')
            return redirect('resume_upload')

        success = 0
        failed  = 0
        errors  = []

        # ════════════════════════════════
        # METHOD 1 — PDF Upload
        # ════════════════════════════════
        if input_type == 'pdf' and pdf_files:
            for pdf_file in pdf_files:
                if not pdf_file.name.lower().endswith('.pdf'):
                    failed += 1
                    errors.append(f'{pdf_file.name} — Not a PDF file')
                    continue
                if pdf_file.size > 5 * 1024 * 1024:
                    failed += 1
                    errors.append(f'{pdf_file.name} — File too large (max 5MB)')
                    continue
                try:
                    candidate = Candidate.objects.create(
                        full_name='Processing...', uploaded_by=request.user
                    )
                    resume = Resume.objects.create(
                        candidate=candidate, job=job, pdf_file=pdf_file
                    )
                    parsed            = process_resume(resume.pdf_file.path)
                    candidate.full_name = parsed['name'] or pdf_file.name
                    candidate.email     = parsed['email']
                    candidate.phone     = parsed['phone']
                    candidate.save()
                    resume.raw_text = parsed['raw_text']
                    resume.save()
                    success += 1
                except Exception as e:
                    failed += 1
                    errors.append(f'{pdf_file.name} — {str(e)}')

        # ════════════════════════════════
        # METHOD 2 — Image Upload (OCR)
        # ════════════════════════════════
        elif input_type == 'image' and image_files:
            from .services import extract_text_from_image
            allowed = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}

            for image_file in image_files:
                ext = os.path.splitext(image_file.name)[1].lower()
                if ext not in allowed:
                    failed += 1
                    errors.append(f'{image_file.name} — Not a supported image format')
                    continue
                if image_file.size > 10 * 1024 * 1024:
                    failed += 1
                    errors.append(f'{image_file.name} — File too large (max 10MB)')
                    continue
                try:
                    # Save image temporarily
                    import tempfile
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=ext
                    ) as tmp:
                        for chunk in image_file.chunks():
                            tmp.write(chunk)
                        tmp_path = tmp.name

                    # Run OCR
                    raw_text = extract_text_from_image(tmp_path)
                    os.unlink(tmp_path)  # delete temp file

                    if not raw_text:
                        failed += 1
                        errors.append(
                            f'{image_file.name} — Could not extract text from image'
                        )
                        continue

                    clean    = clean_text(raw_text)
                    name     = extract_candidate_name(clean)
                    email    = extract_email(clean)
                    phone    = extract_phone(clean)

                    candidate = Candidate.objects.create(
                        full_name   = name or image_file.name,
                        email       = email,
                        phone       = phone,
                        uploaded_by = request.user
                    )
                    resume = Resume.objects.create(
                        candidate = candidate,
                        job       = job,
                        raw_text  = raw_text,
                    )
                    success += 1

                except Exception as e:
                    failed += 1
                    errors.append(f'{image_file.name} — {str(e)}')

        # ════════════════════════════════
        # METHOD 3 — Manual Text Paste
        # ════════════════════════════════
        elif input_type == 'text' and manual_text:
            try:
                clean = clean_text(manual_text)
                name  = extract_candidate_name(clean)
                email = extract_email(clean)
                phone = extract_phone(clean)

                candidate = Candidate.objects.create(
                    full_name   = name or 'Manual Entry',
                    email       = email,
                    phone       = phone,
                    uploaded_by = request.user
                )
                resume = Resume.objects.create(
                    candidate = candidate,
                    job       = job,
                    raw_text  = manual_text,
                )
                success += 1

            except Exception as e:
                failed += 1
                errors.append(f'Manual text — {str(e)}')

        else:
            messages.error(request, 'Please provide a resume via one of the three methods.')
            return redirect('resume_upload')

        # ── Notifications and messages ──
        if success:
            create_notification(
                request.user,
                f'📄 {success} resume(s) uploaded for {job.title}.'
            )
            messages.success(
                request,
                f'✅ {success} resume(s) uploaded successfully for {job.title}.'
            )
        if failed:
            messages.error(request, f'❌ {failed} file(s) failed.')

        upload_summary = {
            'success': success,
            'failed' : failed,
            'errors' : errors,
        }
        form = ResumeUploadForm(request.user)
        return render(request, 'resumes/resume_upload.html', {
            'form': form,
            'upload_summary': upload_summary,
        })

    else:
        form = ResumeUploadForm(request.user)

    return render(request, 'resumes/resume_upload.html', {'form': form})


@login_required
def resume_list_view(request):
    """
    Shows all uploaded resumes. Can be filtered by job.
    """
    job_id = request.GET.get('job')     # optional filter from URL ?job=1

    if job_id:
        resumes = Resume.objects.filter(
            job__id=job_id
        ).select_related('candidate', 'job').order_by('-uploaded_at')
        selected_job = get_object_or_404(JobDescription, pk=job_id)
    else:
        resumes = Resume.objects.all(
        ).select_related('candidate', 'job').order_by('-uploaded_at')
        selected_job = None

    jobs = JobDescription.objects.filter(status='active')

    # Count pending (unprocessed) resumes
    pending_count = Resume.objects.filter(
        job__created_by=request.user,
        is_processed=False
    ).count()

    return render(request, 'resumes/resume_list.html', {
        'resumes'     : resumes,
        'jobs'        : jobs,
        'selected_job': selected_job,
        'pending_count': pending_count,
    })


# -------------------------------------------------------------------
# NLP Processing View
# -------------------------------------------------------------------
@login_required
def process_resume_view(request, pk):
    """
    Triggers the NLP pipeline on a specific resume.
    Extracts skills, education, and experience using spaCy.
    """
    resume = get_object_or_404(Resume, pk=pk)

    if request.method == 'POST':
        if not resume.raw_text:
            messages.error(
                request,
                'No text found in this resume. Cannot run NLP analysis.'
            )
            return redirect('resume_list')

        # Run the full NLP pipeline
        resume = run_nlp_pipeline(resume)
        create_notification(request.user, f'✅ Resume for {resume.candidate.full_name} processed successfully for {resume.job.title}.')

        skills_count = len(resume.get_extracted_skills_list())
        messages.success(
            request,
            f'NLP analysis complete! Found {skills_count} skills in '
            f'"{resume.candidate.full_name}\'s" resume.'
        )

    return redirect('resume_list')


@login_required
def resume_result_view(request, pk):
    """
    Displays the NLP extracted results for a processed resume.
    Shows skills, education, experience in a readable format.
    """
    resume = get_object_or_404(Resume, pk=pk)

    return render(request, 'resumes/resume_result.html', {
        'resume'    : resume,
        'skills'    : resume.get_extracted_skills_list(),
        'education' : resume.extracted_education,
        'experience': resume.extracted_experience,
        'candidate' : resume.candidate,
        'job'       : resume.job,
    })

@login_required
def resume_delete_view(request, pk):
    """
    Deletes a resume and its associated candidate record.
    Also removes the PDF file from disk.
    """
    resume    = get_object_or_404(Resume, pk=pk)
    candidate = resume.candidate

    if request.method == 'POST':
        # Delete the physical PDF file from disk
        if resume.pdf_file:
            import os
            if os.path.isfile(resume.pdf_file.path):
                os.remove(resume.pdf_file.path)

        candidate_name = candidate.full_name
        resume.delete()
        candidate.delete()

        messages.success(
            request,
            f'Resume for "{candidate_name}" deleted successfully.'
        )
        return redirect('resume_list')

    return redirect('resume_list')


# -------------------------------------------------------------------
# Matching Engine Views
# -------------------------------------------------------------------

@login_required
def run_matching_view(request, pk):
    """
    Triggers the matching engine for a single resume.
    Resume must be NLP processed before matching.
    """
    resume = get_object_or_404(Resume, pk=pk)

    if request.method == 'POST':

        # Must be NLP processed first
        if not resume.is_processed:
            messages.error(
                request,
                'Please run NLP analysis first before matching.'
            )
            return redirect('resume_list')

        # Run the matching engine
        match_result = run_matching_engine(resume)
        result = resume.match_result
        create_notification(request.user, f'🎯 Matching complete for {resume.candidate.full_name} — {resume.job.title}. Score: {result.match_percentage:.1f}%')

        messages.success(
            request,
            f'Matching complete! '
            f'{resume.candidate.full_name} scored '
            f'{match_result.match_percentage}% for {resume.job.title}.'
        )

    return redirect('job_ranking', pk=resume.job.pk)


@login_required
def job_ranking_view(request, pk):
    """
    Shows all candidates ranked by match score for a specific job.
    This is the main output screen for HR Managers.
    """
    job     = get_object_or_404(JobDescription, pk=pk)
    results = MatchResult.objects.filter(
        job=job
    ).select_related('candidate', 'resume').order_by('-similarity_score')

    return render(request, 'matching/job_ranking.html', {
        'job'    : job,
        'results': results,
    })

@login_required
def skill_gap_view(request, pk):
    """
    Shows detailed skill gap analysis for a specific match result.
    Compares job required skills vs candidate extracted skills.
    """
    match_result = get_object_or_404(MatchResult, pk=pk)

    matched_skills = match_result.get_matched_skills_list()
    missing_skills = match_result.get_missing_skills_list()

    return render(request, 'matching/skill_gap.html', {
    'match_result'  : match_result,
    'candidate'     : match_result.candidate,
    'job'           : match_result.job,
    'resume'        : match_result.resume,      # ← add this if missing
    'matched_skills': match_result.get_matched_skills_list(),
    'missing_skills': match_result.get_missing_skills_list(),
    'total_required': len(match_result.job.get_skills_list()),
    'matched_count' : len(match_result.get_matched_skills_list()),
    'missing_count' : len(match_result.get_missing_skills_list()),

    })


def landing_view(request):
    """ Public landing page — shown to users who are not logged in. """
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')



# -------------------------------------------------------------------
# Super Admin Panel Views
# -------------------------------------------------------------------

from functools import wraps

def super_admin_required(view_func):
    """
    Decorator that restricts access to super admin users only.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_super_admin():
            messages.error(request, 'Access denied. Super Admin only.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@super_admin_required
def admin_dashboard_view(request):
    """
    Super Admin main dashboard showing full system stats.
    """
    from .models import JobDescription, Resume, Candidate, MatchResult

    total_hr_users   = User.objects.filter(role='hr_manager').count()
    active_hr_users  = User.objects.filter(role='hr_manager', is_active=True).count()
    total_jobs       = JobDescription.objects.count()
    total_resumes    = Resume.objects.count()
    total_candidates = Candidate.objects.count()
    total_matches    = MatchResult.objects.count()

    recent_users = User.objects.filter(
        role='hr_manager'
    ).order_by('-date_joined')[:5]

    recent_jobs = JobDescription.objects.select_related(
        'created_by'
    ).order_by('-created_at')[:5]

    return render(request, 'superadmin/dashboard.html', {
        'total_hr_users'  : total_hr_users,
        'active_hr_users' : active_hr_users,
        'total_jobs'      : total_jobs,
        'total_resumes'   : total_resumes,
        'total_candidates': total_candidates,
        'total_matches'   : total_matches,
        'recent_users'    : recent_users,
        'recent_jobs'     : recent_jobs,
    })


@login_required
@super_admin_required
def admin_user_list_view(request):
    """
    Lists all HR Manager accounts with management options.
    """
    search = request.GET.get('search', '')
    users  = User.objects.filter(role='hr_manager')

    if search:
        users = users.filter(
            username__icontains=search
        ) | users.filter(
            email__icontains=search
        )

    users = users.order_by('-date_joined')

    return render(request, 'superadmin/user_list.html', {
        'users' : users,
        'search': search,
    })


@login_required
@super_admin_required
def admin_user_toggle_view(request, pk):
    """
    Toggles an HR Manager account between active and inactive.
    """
    user = get_object_or_404(User, pk=pk, role='hr_manager')

    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save()
        status = 'activated' if user.is_active else 'deactivated'
        messages.success(
            request,
            f'Account for {user.username} has been {status}.'
        )

    return redirect('admin_user_list')


@login_required
@super_admin_required
def admin_user_delete_view(request, pk):
    """
    Permanently deletes an HR Manager account.
    """
    user = get_object_or_404(User, pk=pk, role='hr_manager')

    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(
            request,
            f'Account for {username} has been permanently deleted.'
        )
        return redirect('admin_user_list')

    return render(request, 'superadmin/user_confirm_delete.html', {
        'user': user
    })


@login_required
@super_admin_required
def admin_user_detail_view(request, pk):
    """
    Shows detailed info about a specific HR Manager.
    """
    from .models import JobDescription, Resume, MatchResult

    hr_user      = get_object_or_404(User, pk=pk, role='hr_manager')
    user_jobs    = JobDescription.objects.filter(created_by=hr_user)
    user_resumes = Resume.objects.filter(candidate__uploaded_by=hr_user)
    user_matches = MatchResult.objects.filter(candidate__uploaded_by=hr_user)

    return render(request, 'superadmin/user_detail.html', {
        'hr_user'     : hr_user,
        'user_jobs'   : user_jobs,
        'user_resumes': user_resumes,
        'user_matches': user_matches,
    })


@login_required
@super_admin_required
def admin_create_hr_view(request):
    """
    Super Admin creates a new HR Manager account.
    """
    from .forms import HRSignupForm

    if request.method == 'POST':
        form = HRSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'hr_manager'
            user.save()
            messages.success(
                request,
                f'HR Manager account created for {user.username}.'
            )
            return redirect('admin_user_list')
    else:
        form = HRSignupForm()

    return render(request, 'superadmin/create_hr.html', {'form': form})


# -------------------------------------------------------------------
# Notification Views
# -------------------------------------------------------------------

@login_required
def notifications_view(request):
    """
    Shows all notifications for the logged-in HR user.
    Does NOT auto-mark as read — user must dismiss individually.
    """
    notifications = request.user.notifications.all()
    return render(request, 'notifications.html', {
        'notifications': notifications
    })


@login_required
def mark_read_view(request, pk):
    """
    Marks a single notification as read.
    """
    from .models import Notification
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    if request.method == 'POST':
        notif.is_read = True
        notif.save()
    return redirect('notifications')


@login_required
def mark_all_read_view(request):
    """
    Marks all notifications as read.
    """
    if request.method == 'POST':
        request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect('notifications')


@login_required
def unread_count_view(request):
    """
    Returns unread notification count as JSON.
    Used by the topbar bell icon to show live count.
    """
    from django.http import JsonResponse
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'count': count})


# -------------------------------------------------------------------
# Send Selection Email to Candidates
# -------------------------------------------------------------------
@login_required
def send_selection_email_view(request, pk):
    """
    HR selects candidates from ranking and sends them
    a shortlisting email for the job.
    """
    from .models import JobDescription, MatchResult

    job = get_object_or_404(JobDescription, pk=pk)

    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_candidates')

        if not selected_ids:
            messages.error(request, 'Please select at least one candidate.')
            return redirect('job_ranking', pk=pk)

        from django.core.mail import send_mail

        sent_count    = 0
        skipped_count = 0

        for match_id in selected_ids:
            try:
                match     = MatchResult.objects.get(pk=match_id, job=job)
                candidate = match.candidate
                email     = candidate.email

                if not email:
                    skipped_count += 1
                    continue

                send_mail(
                    subject=f'Congratulations! You have been shortlisted — {job.title}',
                    message=f'''Dear {candidate.full_name},

We are pleased to inform you that after carefully reviewing your resume,
you have been shortlisted for the following position:

Position  : {job.title}
Department: {job.department or 'N/A'}
Match Score: {match.match_percentage:.1f}%

Our HR team will be in touch shortly with further details regarding
the next steps in the recruitment process.

We look forward to speaking with you!

Best regards,
{request.user.get_full_name() or request.user.username}
HR Manager — ResumeInsight AI''',
                    from_email=None,
                    recipient_list=[email],
                    fail_silently=False,
                )

                # Create in-app notification for HR
                create_notification(
                    request.user,
                    f'📧 Selection email sent to {candidate.full_name} for {job.title}.'
                )

                sent_count += 1

            except Exception as e:
                skipped_count += 1
                continue

        # Summary message
        if sent_count:
            messages.success(
                request,
                f'✅ Selection email sent to {sent_count} candidate(s) successfully.'
            )
        if skipped_count:
            messages.warning(
                request,
                f'⚠️ {skipped_count} candidate(s) skipped — no email address on file.'
            )

    return redirect('job_ranking', pk=pk)


@login_required
def send_rejection_email_view(request, pk):
    """
    HR selects candidates and sends them a polite rejection email.
    """
    from .models import JobDescription, MatchResult

    job = get_object_or_404(JobDescription, pk=pk)

    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_candidates')

        if not selected_ids:
            messages.error(request, 'Please select at least one candidate.')
            return redirect('job_ranking', pk=pk)

        from django.core.mail import send_mail

        sent_count    = 0
        skipped_count = 0

        for match_id in selected_ids:
            try:
                match     = MatchResult.objects.get(pk=match_id, job=job)
                candidate = match.candidate
                email     = candidate.email

                if not email:
                    skipped_count += 1
                    continue

                send_mail(
                    subject=f'Application Update — {job.title}',
                    message=f'''Dear {candidate.full_name},

Thank you for taking the time to apply for the {job.title} position
and for your interest in joining our team.

After carefully reviewing your application and qualifications,
we regret to inform you that we will not be moving forward
with your application at this time.

This was a difficult decision as we received many strong applications.
We encourage you to apply for future openings that match your skills
and experience.

We wish you all the best in your job search and future endeavours.

Best regards,
{request.user.get_full_name() or request.user.username}
HR Manager — ResumeInsight AI''',
                    from_email=None,
                    recipient_list=[email],
                    fail_silently=False,
                )

                # In-app notification for HR
                create_notification(
                    request.user,
                    f'📧 Rejection email sent to {candidate.full_name} for {job.title}.'
                )

                sent_count += 1

            except Exception:
                skipped_count += 1
                continue

        if sent_count:
            messages.success(
                request,
                f'✅ Rejection email sent to {sent_count} candidate(s).'
            )
        if skipped_count:
            messages.warning(
                request,
                f'⚠️ {skipped_count} candidate(s) skipped — no email on file.'
            )

    return redirect('job_ranking', pk=pk)

# -------------------------------------------------------------------
# Export PDF Screening Report
# -------------------------------------------------------------------
@login_required
def export_pdf_report_view(request, pk):
    """
    Generates and downloads a PDF screening report for a job.
    """
    from .models import JobDescription, MatchResult
    from .services import generate_screening_report
    from django.http import HttpResponse

    job = get_object_or_404(JobDescription, pk=pk, created_by=request.user)

    match_results = MatchResult.objects.filter(
        job=job
    ).select_related('candidate').order_by('rank')

    if not match_results.exists():
        messages.error(request, 'No match results found. Run matching first.')
        return redirect('job_ranking', pk=pk)

    # Generate PDF
    buffer = generate_screening_report(job, match_results, request.user)

    # Stream PDF to browser as download
    filename = f"ResumeInsight_Report_{job.title.replace(' ', '_')}_{job.pk}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# -------------------------------------------------------------------
# Custom Skill Library
# -------------------------------------------------------------------

@login_required
def skill_library_view(request):
    """
    Displays all skills in the library with search and filter.
    HR can add new skills from this page.
    """
    from .models import Skill

    query    = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    skills = Skill.objects.all().order_by('category', 'name')

    if query:
        skills = skills.filter(name__icontains=query)
    if category:
        skills = skills.filter(category=category)

    # Category counts for filter badges
    from django.db.models import Count
    category_counts = Skill.objects.values('category').annotate(
        count=Count('id')
    ).order_by('category')

    CATEGORIES = Skill.CATEGORY_CHOICES

    return render(request, 'skills/skill_library.html', {
        'skills'         : skills,
        'query'          : query,
        'selected_category': category,
        'category_counts': {c['category']: c['count'] for c in category_counts},
        'categories'     : CATEGORIES,
        'total_skills'   : Skill.objects.count(),
    })


@login_required
def skill_add_view(request):
    """
    Adds a new skill to the library.
    """
    from .models import Skill

    if request.method == 'POST':
        name     = request.POST.get('name', '').strip()
        category = request.POST.get('category', 'technical').strip()

        if not name:
            messages.error(request, 'Skill name cannot be empty.')
            return redirect('skill_library')

        # Check for duplicates (case-insensitive)
        if Skill.objects.filter(name__iexact=name).exists():
            messages.warning(request, f'"{name}" already exists in the library.')
            return redirect('skill_library')

        Skill.objects.create(
            name=name,
            category=category,
            added_by=request.user
        )

        create_notification(
            request.user,
            f'📚 Skill "{name}" added to the library successfully.'
        )
        messages.success(request, f'Skill "{name}" added successfully!')

    return redirect('skill_library')


@login_required
def skill_edit_view(request, pk):
    """
    Edits an existing skill name and/or category.
    """
    from .models import Skill
    skill = get_object_or_404(Skill, pk=pk)

    if request.method == 'POST':
        name     = request.POST.get('name', '').strip()
        category = request.POST.get('category', skill.category).strip()

        if not name:
            messages.error(request, 'Skill name cannot be empty.')
            return redirect('skill_library')

        # Split by comma — allows adding multiple skills at once
        skill_names = [s.strip() for s in name.split(',') if s.strip()]

        added   = []
        skipped = []

        for skill_name in skill_names:
            if Skill.objects.filter(name__iexact=skill_name).exists():
                skipped.append(skill_name)
            else:
                Skill.objects.create(
                    name=skill_name,
                    category=category,
                    added_by=request.user
                )
                added.append(skill_name)

        if added:
            create_notification(
                request.user,
                f'📚 {len(added)} skill(s) added to the library successfully.'
            )
            messages.success(
                request,
                f'Added {len(added)} skill(s): {", ".join(added)}'
            )
        if skipped:
            messages.warning(
                request,
                f'Skipped {len(skipped)} duplicate(s): {", ".join(skipped)}'
            )

    return redirect('skill_library')


@login_required
def skill_delete_view(request, pk):
    """
    Deletes a skill from the library.
    """
    from .models import Skill
    skill = get_object_or_404(Skill, pk=pk)

    if request.method == 'POST':
        name = skill.name
        skill.delete()
        messages.success(request, f'Skill "{name}" deleted successfully.')

    return redirect('skill_library')




# -------------------------------------------------------------------
# Process All Resumes — Analyse + Match in One Click
# -------------------------------------------------------------------
@login_required
def process_all_resumes_view(request):
    """
    Runs NLP analysis AND matching engine on all unprocessed
    resumes in one click. Can be filtered by job.
    """
    if request.method == 'POST':
        job_id = request.POST.get('job_id')

        # Get unprocessed resumes
        resumes = Resume.objects.filter(
            job__created_by=request.user,
            is_processed=False
        ).select_related('candidate', 'job')

        # Filter by job if specified
        if job_id:
            resumes = resumes.filter(job__pk=job_id)

        if not resumes.exists():
            messages.warning(
                request,
                '⚠️ No pending resumes to process. All resumes are already analysed.'
            )
            return redirect('resume_list')

        # ── Process each resume ──
        nlp_success  = 0
        nlp_failed   = 0
        match_success= 0
        match_failed = 0

        for resume in resumes:
            # Step 1 — NLP Analysis
            try:
                resume = run_nlp_pipeline(resume)
                nlp_success += 1
            except Exception as e:
                nlp_failed += 1
                logger.error(
                    f'NLP failed for resume {resume.pk}: {e}'
                )
                continue

            # Step 2 — Run Matching Engine
            try:
                run_matching_engine(resume)
                match_success += 1
            except Exception as e:
                match_failed += 1
                logger.error(
                    f'Matching failed for resume {resume.pk}: {e}'
                )

        # ── Notification ──
        create_notification(
            request.user,
            f'⚡ Bulk processing complete — {nlp_success} resume(s) analysed '
            f'and {match_success} matched.'
        )

        # ── Summary message ──
        messages.success(
            request,
            f'✅ {nlp_success} resume(s) analysed and '
            f'{match_success} matched successfully!'
        )
        if nlp_failed or match_failed:
            messages.warning(
                request,
                f'⚠️ {nlp_failed} NLP failure(s), {match_failed} matching failure(s).'
            )

    return redirect('resume_list')