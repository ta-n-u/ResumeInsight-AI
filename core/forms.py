# core/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User


# -------------------------------------------------------------------
# HR Signup Form
# -------------------------------------------------------------------
class HRSignupForm(UserCreationForm):
    """
    Form for new HR Managers to register.
    """

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )

    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )

    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )

    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'username', 'email',
                  'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role  = 'hr_manager'   # all signups default to HR Manager
        if commit:
            user.save()
        return user


# -------------------------------------------------------------------
# HR Login Form
# -------------------------------------------------------------------
class HRLoginForm(AuthenticationForm):
    """
    Form for HR users to log in.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter your username'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })

# Add this import at the top if not already there
from .models import User, JobDescription


# -------------------------------------------------------------------
# Job Description Form
# -------------------------------------------------------------------
class JobDescriptionForm(forms.ModelForm):
    """
    Form for HR Managers to create and edit job descriptions.
    """

    class Meta:
        model  = JobDescription
        fields = [
            'title', 'department', 'description',
            'required_skills', 'experience_required',
            'education_required', 'status',
            'skill_weight', 'semantic_weight',
            'education_weight', 'experience_weight',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Senior Python Developer'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Engineering'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe the role, responsibilities, and expectations...'
            }),
            'required_skills': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'e.g. Python, Django, PostgreSQL, REST APIs'
            }),
            'experience_required': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 2-3 years'
            }),
            'education_required': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "e.g. Bachelor's in Computer Science"
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'required_skills': 'Required Skills (comma-separated)',
            'experience_required': 'Experience Required',
            'education_required': 'Education Required',
        }


# Add this import at the top
from .models import User, JobDescription, Resume, Candidate


# -------------------------------------------------------------------
# Resume Upload Form
# -------------------------------------------------------------------
class ResumeUploadForm(forms.Form):
    """
    Form for bulk resume upload.
    Only job selection needed — files handled via request.FILES.getlist()
    """
    job = forms.ModelChoiceField(
        queryset      = JobDescription.objects.none(),
        empty_label   = 'Select a job position...',
        widget        = forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show jobs created by this HR user
        self.fields['job'].queryset = JobDescription.objects.filter(
            created_by=user,
            status='active'
        ).order_by('-created_at')