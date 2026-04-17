# core/services.py

import pdfplumber
import re
import spacy
import logging


def create_notification(user, message):
    """
    Creates an in-app notification for an HR user.
    """
    from .models import Notification
    Notification.objects.create(user=user, message=message)

logger = logging.getLogger(__name__)

# Load the spaCy model once at module level (not inside functions)
# This avoids reloading the model on every request — much faster
try:
    nlp = spacy.load('en_core_web_md')
    logger.info("spaCy model loaded successfully.")
except OSError:
    logger.error("spaCy model 'en_core_web_md' not found. Run: python -m spacy download en_core_web_md")
    nlp = None

import pdfplumber
import re
import logging

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# STEP 1: Extract raw text from a PDF file
# Handles both single-column and two-column layouts
# -------------------------------------------------------------------
def extract_text_from_pdf(pdf_file_path):
    """
    Extracts text from PDF using two strategies:
    1. Standard extraction (works for single-column PDFs)
    2. Word-sorted extraction (fixes two-column layout scrambling)
    """
    extracted_text = ""

    try:
        with pdfplumber.open(pdf_file_path) as pdf:
            for page in pdf.pages:

                # Strategy 1 — try standard extraction first
                page_text = page.extract_text()

                # Strategy 2 — if text looks scrambled (sidebar mixing),
                # extract words sorted by vertical position (top to bottom)
                # then horizontal (left to right) within each line
                if page_text:
                    words = page.extract_words()
                    if words:
                        # Sort words by vertical position first, then horizontal
                        # Group words that are on the same line (within 3px tolerance)
                        lines = {}
                        for word in words:
                            # Round top position to nearest 3px to group same line
                            line_key = round(word['top'] / 3) * 3
                            if line_key not in lines:
                                lines[line_key] = []
                            lines[line_key].append(word)

                        # Sort lines top to bottom, words left to right
                        sorted_lines = sorted(lines.items(), key=lambda x: x[0])
                        line_texts = []
                        for _, line_words in sorted_lines:
                            line_words.sort(key=lambda w: w['x0'])
                            line_texts.append(' '.join(w['text'] for w in line_words))

                        page_text = '\n'.join(line_texts)

                if page_text:
                    extracted_text += page_text + "\n"

        logger.info(f"Successfully extracted text from: {pdf_file_path}")

    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        extracted_text = ""

    # If pdfplumber returned nothing — try OCR fallback
    if not extracted_text.strip():
        logger.warning(f"pdfplumber returned empty — trying OCR fallback")
        extracted_text = extract_text_from_scanned_pdf(pdf_file_path)

    return extracted_text



# -------------------------------------------------------------------
# OCR: Extract text from image files (JPG, PNG, etc.)
# -------------------------------------------------------------------
def extract_text_from_image(image_path):
    """
    Uses Tesseract OCR to extract text from an image file.
    Supports JPG, PNG, BMP, TIFF formats.
    """
    try:
        import pytesseract
        from PIL import Image

        # Set Tesseract path for Windows
        pytesseract.pytesseract.tesseract_cmd = \
            r'C:\Program Files\Tesseract-OCR\tesseract.exe'

        image = Image.open(image_path)
        text  = pytesseract.image_to_string(image)

        logger.info(f"OCR extraction complete: {image_path}")
        return text.strip()

    except Exception as e:
        logger.error(f"OCR failed for image {image_path}: {e}")
        return ""


# -------------------------------------------------------------------
# OCR: Extract text from scanned/image-based PDF
# -------------------------------------------------------------------
def extract_text_from_scanned_pdf(pdf_path):
    """
    Converts each page of a PDF to an image then runs OCR.
    Used when pdfplumber returns empty text (scanned PDFs).
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
        from PIL import Image

        pytesseract.pytesseract.tesseract_cmd = \
            r'C:\Program Files\Tesseract-OCR\tesseract.exe'

        # Convert PDF pages to images
        poppler_path = r'C:\Users\TANU\Downloads\Release-25.12.0-0\poppler-25.12.0\Library\bin'
        pages = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)

        full_text = ""
        for i, page in enumerate(pages):
            text = pytesseract.image_to_string(page)
            full_text += text + "\n"
            logger.info(f"OCR page {i+1} complete")

        return full_text.strip()

    except Exception as e:
        logger.error(f"Scanned PDF OCR failed: {e}")
        return ""



# -------------------------------------------------------------------
# STEP 2: Clean the extracted raw text
# -------------------------------------------------------------------
def clean_text(raw_text):
    """
    Cleans up messy PDF text by removing unwanted characters,
    extra spaces, and formatting artifacts.

    Args:
        raw_text: The raw string extracted from the PDF.

    Returns:
        A cleaned, normalized string.
    """
    if not raw_text:
        return ""

    # Remove non-ASCII characters (symbols, weird encodings)
    text = raw_text.encode('ascii', 'ignore').decode('ascii')

    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)

    # Replace multiple newlines with a single newline
    text = re.sub(r'\n+', '\n', text)

    # Remove special characters but keep letters, numbers,
    # spaces, newlines, and basic punctuation
    text = re.sub(r'[^a-zA-Z0-9\s\n\.\,\-\+\#\/\@]', ' ', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


# -------------------------------------------------------------------
# STEP 3: Extract candidate name
# -------------------------------------------------------------------
def extract_candidate_name(text):
    """
    Extracts candidate name using multiple strategies.
    Handles various real-world resume formats.
    """
    if not text:
        return "Unknown Candidate"

    # ── Common words that are NOT names ──
    NOT_NAMES = {
        'personal', 'info', 'information', 'contact', 'details',
        'profile', 'summary', 'objective', 'experience', 'education',
        'skills', 'career', 'professional', 'about', 'address',
        'curriculum', 'vitae', 'resume', 'cv', 'portfolio',
        'web', 'software', 'senior', 'junior', 'developer', 'engineer',
        'designer', 'manager', 'analyst', 'intern', 'consultant',
        'specialist', 'coordinator', 'director', 'lead', 'head',
        'phone', 'email', 'mobile', 'tel', 'fax', 'linkedin',
        'twitter', 'github', 'website', 'www', 'http',
        'date', 'birth', 'nationality', 'gender', 'married',
        'single', 'male', 'female', 'india', 'nepal', 'usa',
        'street', 'city', 'state', 'country', 'district',
        'nagar', 'road', 'lane', 'avenue', 'block', 'sector',
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
    }

    def is_valid_name(name):
        """Check if extracted text looks like a real name."""
        words = name.strip().split()
        if not 2 <= len(words) <= 4:
            return False
        for word in words:
            clean = word.replace('-', '').replace('.', '').replace("'", '')
            if not clean.isalpha():
                return False
            if clean.lower() in NOT_NAMES:
                return False
            # Names don't start with lowercase
            if clean[0].islower():
                return False
            # Skip very short single letters (initials only)
            if len(clean) < 2:
                return False
        return True

    # ── Strategy 1: spaCy PERSON entity ──
    if nlp:
        try:
            # Check more text for name — first 800 chars
            doc = nlp(text[:800])
            for ent in doc.ents:
                if ent.label_ == 'PERSON':
                    if is_valid_name(ent.text):
                        return ent.text.strip()
        except Exception:
            pass

    # ── Strategy 2: First line that looks like a name ──
    # Clean the text first — remove addresses and numbers
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Skip lines with digits (addresses, phones, dates)
        if any(char.isdigit() for char in line):
            continue
        # Skip lines with common symbols
        if any(sym in line for sym in ['@', '/', '|', '\\', '#', '+']):
            continue
        # Skip very long lines (paragraphs, not names)
        if len(line) > 40:
            continue
        lines.append(line)

    for line in lines[:8]:
        # Handle names that might be all caps e.g. "ALLEN CHAUDHARI"
        if line.isupper() and 2 <= len(line.split()) <= 4:
            candidate = line.title()  # Convert to Title Case
            if is_valid_name(candidate):
                return candidate
        # Normal title case names
        if is_valid_name(line):
            return line

    # ── Strategy 3: Regex — look for Title Case word pairs ──
    import re
    # Match two or three capitalised words in a row
    pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b'
    matches = re.findall(pattern, text[:600])
    for match in matches:
        if is_valid_name(match):
            return match

    return "Unknown Candidate"


# -------------------------------------------------------------------
# STEP 4: Extract email address
# -------------------------------------------------------------------
def extract_email(text):
    """
    Extracts email using regex. Handles common obfuscations like
    spaces around @ symbol.
    """
    if not text:
        return ""

    # Normalize common obfuscations: "name [at] gmail.com"
    text = re.sub(r'\s*\[at\]\s*', '@', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*\(at\)\s*', '@', text, flags=re.IGNORECASE)

    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    matches = re.findall(email_pattern, text)

    # Filter out image file extensions mistaken for emails
    filtered = [m for m in matches
                if not m.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]

    return filtered[0] if filtered else ""


# -------------------------------------------------------------------
# STEP 5: Extract phone number
# -------------------------------------------------------------------
def extract_phone(text):
    """
    Extracts phone number supporting Nepali (+977), US, and
    international formats.
    """
    if not text:
        return ""

    # Patterns ordered from most specific to most general
    patterns = [
        r'\+977[-.\s]?\d{9,10}',           # Nepali: +977-9841234567
        r'\+\d{1,3}[-.\s]?\d{6,12}',       # International: +1-555-1234
        r'\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}',  # US: (781) 470-8889
        r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',    # US no brackets: 781-470-8889
        r'\d{10}',                           # Plain 10 digits
        r'\d{7,}',                           # Fallback 7+ digits
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            digits = re.sub(r'\D', '', match)
            if len(digits) >= 7:
                return match.strip()

    return ""


# -------------------------------------------------------------------
# MASTER FUNCTION: Process a full resume PDF
# -------------------------------------------------------------------
def process_resume(pdf_file_path):
    """
    Master function that runs the full parsing pipeline on a PDF.
    Calls all the helper functions above in sequence.

    Args:
        pdf_file_path: Full path to the uploaded PDF file.

    Returns:
        A dictionary with all extracted data.
    """
    # Step 1: Extract raw text
    raw_text = extract_text_from_pdf(pdf_file_path)

    # Step 2: Clean the text
    clean = clean_text(raw_text)

    # Step 3: Extract personal info
    name  = extract_candidate_name(clean)
    email = extract_email(clean)
    phone = extract_phone(clean)

    return {
        'raw_text'  : raw_text,
        'clean_text': clean,
        'name'      : name,
        'email'     : email,
        'phone'     : phone,
    }


# -------------------------------------------------------------------
# SKILLS LIBRARY
# A predefined list of common technical and soft skills.
# spaCy will match resume text against this list.
# -------------------------------------------------------------------
SKILLS_LIBRARY = [
    # Programming Languages
    "python", "java", "javascript", "typescript", "c", "c++", "c#",
    "ruby", "php", "swift", "kotlin", "go", "rust", "scala", "r",
    "matlab", "perl", "bash", "shell",

    # Web Frameworks & Libraries
    "django", "flask", "fastapi", "react", "angular", "vue",
    "node", "express", "spring", "laravel", "rails",
    "bootstrap", "tailwind", "jquery",

    # Databases
    "postgresql", "mysql", "sqlite", "mongodb", "redis",
    "oracle", "sql server", "firebase", "cassandra",

    # Data Science & ML
    "machine learning", "deep learning", "neural network",
    "natural language processing", "nlp", "computer vision",
    "pandas", "numpy", "scikit-learn", "tensorflow", "keras",
    "pytorch", "matplotlib", "seaborn", "opencv",

    # Cloud & DevOps
    "aws", "azure", "google cloud", "docker", "kubernetes",
    "jenkins", "ci/cd", "terraform", "ansible", "linux",

    # Tools & Practices
    "git", "github", "gitlab", "jira", "agile", "scrum",
    "rest api", "graphql", "microservices", "mvc",
    "unit testing", "test driven development",

    # Soft Skills
    "communication", "teamwork", "leadership", "problem solving",
    "critical thinking", "time management", "adaptability",
]


# -------------------------------------------------------------------
# NLP FUNCTION 1: Extract Skills using spaCy
# -------------------------------------------------------------------
def extract_skills_nlp(text):
    """
    Extracts skills from resume text using two sources:
    1. Hardcoded SKILLS_LIBRARY (existing)
    2. Custom Skill Library from the database (new)

    Uses direct string matching + spaCy NER.

    Args:
        text: Cleaned resume text string.

    Returns:
        A list of matched skill strings.
    """
    if not nlp or not text:
        return []

    text_lower = text.lower()
    found_skills = []

    # ── Source 1: Hardcoded SKILLS_LIBRARY ──
    for skill in SKILLS_LIBRARY:
        if skill.lower() in text_lower:
            found_skills.append(skill.title())

    # ── Source 2: Custom Skill Library from Database ──
    # This is where HR-added skills get checked against the resume
    try:
        from .models import Skill as SkillModel
        db_skills = SkillModel.objects.values_list('name', flat=True)

        for skill in db_skills:
            if skill.lower() in text_lower:
                # Only add if not already found
                if skill.title() not in [s.title() for s in found_skills]:
                    found_skills.append(skill)
    except Exception as e:
        # Never break the pipeline if DB lookup fails
        logger.warning(f"Could not load skills from database: {e}")

    # ── spaCy NER — catch additional tech entities ──
    doc = nlp(text[:10000])

    for ent in doc.ents:
        if ent.label_ in ['ORG', 'PRODUCT']:
            ent_lower = ent.text.lower()
            if any(skill.lower() in ent_lower for skill in SKILLS_LIBRARY):
                if ent.text.title() not in [s.title() for s in found_skills]:
                    found_skills.append(ent.text.title())

    # ── Remove duplicates while preserving order ──
    seen = set()
    unique_skills = []
    for skill in found_skills:
        if skill.lower() not in seen:
            seen.add(skill.lower())
            unique_skills.append(skill)

    return unique_skills


# -------------------------------------------------------------------
# NLP FUNCTION 2: Extract Education using Regex + Keywords
# -------------------------------------------------------------------
def extract_education_nlp(text):
    """
    Finds education-related information in the resume text.
    Extracts degree + university + year as a complete sentence.
    """
    if not text:
        return ""

    found = []

    # ── Strategy 1: Find the EDUCATION section and extract lines from it ──
    # Looks for an "EDUCATION" heading and grabs the lines below it
    education_section = re.search(
        r'education[:\s\n]+(.*?)(?=\n[A-Z]{2,}|\Z)',
        text,
        re.IGNORECASE | re.DOTALL
    )

    if education_section:
        section_text = education_section.group(1).strip()

        # Extract degree lines from the section
        lines = [l.strip() for l in section_text.split('\n') if l.strip()]
        for line in lines[:4]:  # take first 4 lines max
            if len(line) > 5:   # ignore very short lines
                found.append(line)

    # ── Strategy 2: Regex patterns to find degree + context ──
    # Captures degree AND surrounding words (university, year)
    degree_patterns = [
        # B.E. / B.Tech / M.Tech with context
        r'b\.?\s*e\.?\s+in\s+[\w\s]+',
        r'b\.?\s*tech[\w\s,]+(?:university|college|institute)?[\w\s,]*',
        r'm\.?\s*tech[\w\s,]+(?:university|college|institute)?[\w\s,]*',
        # B.Sc. variants
        r'b\.?\s*sc\.?\s*(?:csit|it|cs)?[\w\s,]*',
        r'm\.?\s*sc\.?\s*(?:csit|it|cs)?[\w\s,]*',
        # Bachelor/Master full words
        r'bachelor\s+of\s+[\w\s]+(?:engineering|science|technology|computer)[^\n]*',
        r'master\s+of\s+[\w\s]+(?:engineering|science|technology|computer)[^\n]*',
        # BCA / MCA / BIT
        r'\b(?:bca|mca|bit|bim)\b[\w\s,]*',
        # PhD
        r'ph\.?\s*d\.?[\w\s,]*(?:university|college)?[\w\s,]*',
        # University line — catches "Tribhuvan University | B.E. | 2020"
        r'(?:tribhuvan|pokhara|kathmandu|purbanchal|far western)[\w\s,|]+university[^\n]*',
        r'[\w\s]+university[\w\s,|]+(?:b\.e|b\.sc|b\.tech|m\.sc|m\.tech)[^\n]*',
        # Year + degree combo
        r'(?:b\.e|b\.sc|b\.tech|m\.sc|m\.tech|bca|mca)[\w\s,|]+\d{4}',
    ]

    for pattern in degree_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            cleaned = match.strip().strip('|').strip()
            # Only add if meaningful and not already captured
            if len(cleaned) > 5 and cleaned not in found:
                found.append(cleaned)

    # ── Strategy 3: spaCy ORG entities near degree keywords ──
    if nlp and not found:
        doc = nlp(text[:5000])
        degree_keywords = [
            'university', 'college', 'institute',
            'school', 'academy', 'engineering'
        ]
        for ent in doc.ents:
            if ent.label_ in ['ORG', 'GPE']:
                if any(kw in ent.text.lower() for kw in degree_keywords):
                    if ent.text not in found:
                        found.append(ent.text)

    # ── Clean up and deduplicate ──
    seen    = set()
    cleaned = []
    for item in found:
        # Normalize whitespace
        item = re.sub(r'\s+', ' ', item).strip()
        item_lower = item.lower()
        if item_lower not in seen and len(item) > 3:
            seen.add(item_lower)
            cleaned.append(item)

    return " | ".join(cleaned[:3]) if cleaned else "Not specified"


# -------------------------------------------------------------------
# NLP FUNCTION 3: Extract Experience using Regex
# -------------------------------------------------------------------
def extract_experience_nlp(text):
    """
    Finds experience-related information in the resume text.
    Looks for year mentions, job titles, and experience phrases.

    Args:
        text: Cleaned resume text string.

    Returns:
        A string summarizing experience found.
    """
    if not text:
        return ""

    text_lower = text.lower()
    found = []

    # Pattern: "X years of experience" or "X+ years"
    year_patterns = [
        r'\d+\+?\s+years?\s+of\s+experience',
        r'\d+\+?\s+years?\s+experience',
        r'over\s+\d+\s+years?',
        r'more\s+than\s+\d+\s+years?',
    ]

    for pattern in year_patterns:
        matches = re.findall(pattern, text_lower)
        found.extend(matches)

    # Look for seniority level keywords
    seniority_keywords = [
        'junior', 'mid-level', 'senior', 'lead',
        'principal', 'intern', 'fresher', 'entry level'
    ]

    for keyword in seniority_keywords:
        if keyword in text_lower:
            found.append(keyword.title())

    # Remove duplicates
    found = list(set(found))

    return ", ".join(found) if found else "Not specified"


# -------------------------------------------------------------------
# MASTER NLP FUNCTION: Run full NLP pipeline on a resume
# -------------------------------------------------------------------
def run_nlp_pipeline(resume):
    """
    Runs the complete NLP pipeline on a Resume object.
    Extracts skills, education, and experience then saves
    the results back to the Resume model.

    Args:
        resume: A Resume model instance with raw_text available.

    Returns:
        The updated Resume instance.
    """
    if not resume.raw_text:
        logger.warning(f"Resume {resume.pk} has no raw text to process.")
        return resume

    text = resume.raw_text

    # Run all three extractors
    skills     = extract_skills_nlp(text)
    education  = extract_education_nlp(text)
    experience = extract_experience_nlp(text)

    # Save results to the Resume model
    resume.extracted_skills     = ", ".join(skills)
    resume.extracted_education  = education
    resume.extracted_experience = experience
    resume.is_processed         = True  # mark as done
    resume.save()

    logger.info(
        f"NLP pipeline complete for Resume {resume.pk}. "
        f"Skills found: {len(skills)}"
    )

    return resume

# -------------------------------------------------------------------
# MATCHING ENGINE
# -------------------------------------------------------------------
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


def get_text_vector(text):
    """
    Converts a text string into a numerical vector using
    spaCy's word embeddings (en_core_web_md).

    This is what allows SEMANTIC matching — meaning
    "Developer" and "Engineer" will have similar vectors
    even though they are different words.

    Args:
        text: Any string of text.

    Returns:
        A numpy array representing the text vector.
        Returns None if text is empty or model not loaded.
    """
    if not nlp or not text:
        return None

    # Limit text length for performance
    doc = nlp(text[:10000])

    # doc.vector is the average of all word vectors in the text
    if doc.vector.any():
        return doc.vector.reshape(1, -1)   # reshape for sklearn

    return None


def calculate_similarity(text1, text2):
    """
    Calculates the Cosine Similarity score between two texts.
    Score ranges from 0.0 (no match) to 1.0 (perfect match).

    Cosine Similarity measures the ANGLE between two vectors,
    not their magnitude — so it focuses on meaning, not length.

    Args:
        text1: Job description text.
        text2: Resume text.

    Returns:
        A float between 0.0 and 1.0.
    """
    vec1 = get_text_vector(text1)
    vec2 = get_text_vector(text2)

    if vec1 is None or vec2 is None:
        return 0.0

    # Calculate cosine similarity
    score = cosine_similarity(vec1, vec2)[0][0]

    # Clamp between 0 and 1 to avoid floating point issues
    score = float(np.clip(score, 0.0, 1.0))

    return score


def calculate_skill_match(jd_skills, resume_skills):
    """
    Compares job description skills vs resume skills.
    Returns matched and missing skills lists.

    Uses both exact matching and semantic similarity
    via spaCy vectors for fuzzy skill matching.

    Args:
        jd_skills   : List of required skills from job description.
        resume_skills: List of skills extracted from resume.

    Returns:
        A tuple of (matched_skills, missing_skills)
    """
    matched = []
    missing = []

    # Normalize all skills to lowercase for comparison
    resume_lower = [s.lower().strip() for s in resume_skills]

    for jd_skill in jd_skills:
        jd_skill_lower = jd_skill.lower().strip()
        found = False

        # Step 1: Try exact match first
        if jd_skill_lower in resume_lower:
            matched.append(jd_skill)
            found = True

        # Step 2: Try semantic similarity with spaCy
        if not found and nlp:
            jd_token = nlp(jd_skill_lower)

            for resume_skill in resume_lower:
                resume_token = nlp(resume_skill)

                # Only compare if both have vectors
                if jd_token.vector_norm and resume_token.vector_norm:
                    similarity = jd_token.similarity(resume_token)

                    # Threshold of 0.75 — high enough to avoid false matches
                    if similarity >= 0.75:
                        matched.append(jd_skill)
                        found = True
                        break

        if not found:
            missing.append(jd_skill)

    return matched, missing


def run_matching_engine(resume):
    """
    Master matching function.
    Runs the full matching pipeline for one resume against its job.

    Steps:
    1. Calculate semantic similarity score (spaCy cosine)
    2. Calculate skill overlap score (Jaccard-based)
    3. Calculate education match score
    4. Calculate experience match score
    5. Combine using HR-configurable weights
    6. Save results to MatchResult model
    7. Re-rank all candidates for this job
    """
    from .models import MatchResult

    job       = resume.job
    candidate = resume.candidate

    # ── 1. Semantic Score ──
    jd_text     = f"{job.title} {job.description} {job.required_skills}"
    resume_text = resume.raw_text or ""
    semantic_score = calculate_similarity(jd_text, resume_text)

    # ── 2. Skill Overlap Score ──
    jd_skills     = job.get_skills_list()
    resume_skills = resume.get_extracted_skills_list()

    matched_skills, missing_skills = calculate_skill_match(
        jd_skills, resume_skills
    )

    if len(jd_skills) > 0:
        skill_score = len(matched_skills) / len(jd_skills)
    else:
        skill_score = 0.0

    # ── 3. Education Match Score ──
    education_score = 0.5  # neutral default if no data

    if job.education_required and resume.extracted_education:
        edu_levels = {
            'phd'        : 5,
            'doctorate'  : 5,
            'master'     : 4,
            'm.sc'       : 4,
            'm.tech'     : 4,
            'mca'        : 4,
            'bachelor'   : 3,
            'b.e'        : 3,
            'b.sc'       : 3,
            'b.tech'     : 3,
            'bca'        : 3,
            'bit'        : 3,
            'diploma'    : 2,
            'high school': 1,
            'slc'        : 1,
            'see'        : 1,
        }

        required_level  = 0
        candidate_level = 0

        edu_req = job.education_required.lower()
        edu_res = resume.extracted_education.lower()

        for edu, level in edu_levels.items():
            if edu in edu_req:
                required_level = max(required_level, level)
            if edu in edu_res:
                candidate_level = max(candidate_level, level)

        if required_level > 0:
            # Full score if meets or exceeds requirement
            education_score = min(candidate_level / required_level, 1.0)
        else:
            education_score = 1.0  # no requirement = full score

    # ── 4. Experience Match Score ──
    experience_score = 0.5  # neutral default if no data

    if job.experience_required and resume.extracted_experience:
        req_years = re.findall(r'\d+', job.experience_required)
        res_years = re.findall(r'\d+', resume.extracted_experience)

        if req_years and res_years:
            required  = int(req_years[0])
            candidate_years = int(res_years[0])

            if required > 0:
                # Full score if meets or exceeds requirement
                experience_score = min(candidate_years / required, 1.0)
            else:
                experience_score = 1.0
        else:
            experience_score = 0.5  # unknown — neutral score

    # ── 5. Hybrid Score using HR-configurable weights ──
    similarity_score = (
        job.skill_weight      * skill_score      +
        job.semantic_weight   * semantic_score   +
        job.education_weight  * education_score  +
        job.experience_weight * experience_score
    )

    # Clamp to 0.0 - 1.0 range
    similarity_score = round(min(max(similarity_score, 0.0), 1.0), 4)
    match_percentage = round(similarity_score * 100, 2)

    # ── 6. Save or update MatchResult ──
    match_result, created = MatchResult.objects.update_or_create(
        resume   = resume,
        defaults = {
            'job'             : job,
            'candidate'       : candidate,
            'similarity_score': similarity_score,
            'match_percentage': match_percentage,
            'matched_skills'  : ', '.join(matched_skills),
            'missing_skills'  : ', '.join(missing_skills),
        }
    )

    # ── 7. Re-rank all candidates for this job ──
    all_results = MatchResult.objects.filter(
        job=job
    ).order_by('-similarity_score')

    for index, result in enumerate(all_results, start=1):
        result.rank = index
        result.save()

    logger.info(
        f"Matching complete: {candidate.full_name} → "
        f"{job.title} | Score: {match_percentage}% "
        f"(Skill:{skill_score:.2f} Semantic:{semantic_score:.2f} "
        f"Edu:{education_score:.2f} Exp:{experience_score:.2f})"
    )

    return match_result


# -------------------------------------------------------------------
# PDF Report Generator
# Generates a professional screening report for a job using ReportLab
# -------------------------------------------------------------------
def generate_screening_report(job, match_results, generated_by):
    """
    Generates a professional PDF screening report for a job.

    Args:
        job:            JobDescription instance
        match_results:  QuerySet of MatchResult for this job
        generated_by:   User instance (the HR manager)

    Returns:
        BytesIO object containing the PDF — ready to stream to browser
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table,
        TableStyle, HRFlowable, PageBreak
    )
    from reportlab.platypus import KeepTogether
    from io import BytesIO
    from datetime import datetime

    buffer = BytesIO()

    # ── Page Setup ──
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    # ── Colour Palette ──
    BLUE       = colors.HexColor('#2563EB')
    DARK       = colors.HexColor('#0F172A')
    GREY       = colors.HexColor('#64748B')
    LIGHT_GREY = colors.HexColor('#F8FAFC')
    BORDER     = colors.HexColor('#E2E8F0')
    GREEN      = colors.HexColor('#059669')
    ORANGE     = colors.HexColor('#D97706')
    RED        = colors.HexColor('#DC2626')
    WHITE      = colors.white

    # ── Styles ──
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        'ReportTitle',
        fontSize=22, fontName='Helvetica-Bold',
        textColor=WHITE, alignment=TA_LEFT, leading=28,
    )
    style_subtitle = ParagraphStyle(
        'ReportSubtitle',
        fontSize=10, fontName='Helvetica',
        textColor=colors.HexColor('#BFDBFE'),
        alignment=TA_LEFT, leading=14,
    )
    style_section = ParagraphStyle(
        'SectionHeader',
        fontSize=11, fontName='Helvetica-Bold',
        textColor=BLUE, spaceBefore=14, spaceAfter=6,
    )
    style_body = ParagraphStyle(
        'Body',
        fontSize=9, fontName='Helvetica',
        textColor=DARK, leading=14,
    )
    style_small = ParagraphStyle(
        'Small',
        fontSize=8, fontName='Helvetica',
        textColor=GREY, leading=12,
    )
    style_label = ParagraphStyle(
        'Label',
        fontSize=8, fontName='Helvetica-Bold',
        textColor=GREY, leading=12,
    )
    style_tag_green = ParagraphStyle(
        'TagGreen',
        fontSize=8, fontName='Helvetica',
        textColor=GREEN,
    )
    style_tag_red = ParagraphStyle(
        'TagRed',
        fontSize=8, fontName='Helvetica',
        textColor=RED,
    )
    style_header = ParagraphStyle(
        'TableHeader',
        fontSize=9, fontName='Helvetica-Bold',
        textColor=WHITE, leading=12,
    )

    story = []

    # ════════════════════════════════════
    # HEADER BANNER
    # ════════════════════════════════════
    header_data = [[
        Paragraph(f"Screening Report", style_title),
        Paragraph(
            f"Generated by {generated_by.get_full_name() or generated_by.username}<br/>"
            f"{datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            ParagraphStyle('Right', fontSize=9, fontName='Helvetica',
                           textColor=colors.HexColor('#BFDBFE'),
                           alignment=TA_RIGHT, leading=14)
        )
    ]]
    header_table = Table(header_data, colWidths=[4.5 * inch, 2.5 * inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), BLUE),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
        ('LEFTPADDING',   (0, 0), (0, -1),  20),
        ('RIGHTPADDING',  (-1, 0), (-1, -1), 20),
        ('ROUNDEDCORNERS', [8, 8, 8, 8]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    # ════════════════════════════════════
    # JOB DETAILS CARD
    # ════════════════════════════════════
    story.append(Paragraph("Job Details", style_section))

    job_info = [
        ['Position',    job.title],
        ['Department',  job.department or 'N/A'],
        ['Status',      job.get_status_display()],
        ['Experience',  job.experience_required or 'N/A'],
        ['Education',   job.education_required or 'N/A'],
        ['Required Skills', job.required_skills],
    ]

    job_table = Table(
        [[Paragraph(k, style_label), Paragraph(str(v), style_body)]
         for k, v in job_info],
        colWidths=[1.4 * inch, 5.6 * inch]
    )
    job_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), LIGHT_GREY),
        ('ROWBACKGROUNDS',(0, 0), (-1, -1), [WHITE, LIGHT_GREY]),
        ('GRID',          (0, 0), (-1, -1), 0.5, BORDER),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    story.append(job_table)
    story.append(Spacer(1, 16))

    # ════════════════════════════════════
    # SUMMARY STATS ROW
    # ════════════════════════════════════
    story.append(Paragraph("Screening Summary", style_section))

    total      = match_results.count()
    avg_score  = sum(m.match_percentage for m in match_results) / total if total else 0
    shortlisted= sum(1 for m in match_results if m.match_percentage >= 70)

    stats_data = [[
        Paragraph(f"<b>{total}</b><br/>Total Candidates", style_body),
        Paragraph(f"<b>{avg_score:.1f}%</b><br/>Average Score",  style_body),
        Paragraph(f"<b>{shortlisted}</b><br/>Shortlisted (70%+)", style_body),
        Paragraph(f"<b>{total - shortlisted}</b><br/>Below Threshold", style_body),
    ]]
    stats_table = Table(stats_data, colWidths=[1.75 * inch] * 4)
    stats_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), LIGHT_GREY),
        ('GRID',          (0, 0), (-1, -1), 0.5, BORDER),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 16))

    # ════════════════════════════════════
    # CANDIDATE RANKINGS TABLE
    # ════════════════════════════════════
    story.append(Paragraph("Candidate Rankings", style_section))

    # Table header
    rank_header = [
        Paragraph('Rank',            style_header),
        Paragraph('Candidate',       style_header),
        Paragraph('Email',           style_header),
        Paragraph('Score',           style_header),
        Paragraph('Matched Skills',  style_header),
        Paragraph('Missing Skills',  style_header),
    ]
    rank_rows = [rank_header]

    for match in match_results:
        # Score color
        pct = match.match_percentage
        if pct >= 70:
            score_color = GREEN
        elif pct >= 40:
            score_color = ORANGE
        else:
            score_color = RED

        score_style = ParagraphStyle(
            'Score', fontSize=9, fontName='Helvetica-Bold',
            textColor=score_color
        )

        matched = ', '.join(match.get_matched_skills_list()) or '—'
        missing = ', '.join(match.get_missing_skills_list()) or '—'

        rank_rows.append([
            Paragraph(f"#{match.rank}", style_body),
            Paragraph(match.candidate.full_name, style_body),
            Paragraph(match.candidate.email or '—', style_small),
            Paragraph(f"{pct:.1f}%", score_style),
            Paragraph(matched, style_tag_green),
            Paragraph(missing, style_tag_red),
        ])

    rank_table = Table(
        rank_rows,
        colWidths=[0.45*inch, 1.3*inch, 1.5*inch, 0.6*inch, 1.5*inch, 1.65*inch]
    )
    rank_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND',    (0, 0), (-1, 0),  BLUE),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  WHITE),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        # Alternating rows
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
        ('GRID',          (0, 0), (-1, -1), 0.5, BORDER),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    story.append(rank_table)
    story.append(Spacer(1, 20))

    # ════════════════════════════════════
    # FOOTER
    # ════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated by ResumeInsight AI  •  {generated_by.get_full_name() or generated_by.username}  "
        f"•  {datetime.now().strftime('%B %d, %Y')}  •  CONFIDENTIAL",
        ParagraphStyle('Footer', fontSize=8, fontName='Helvetica',
                       textColor=GREY, alignment=TA_CENTER)
    ))

    # ── Build PDF ──
    doc.build(story)
    buffer.seek(0)
    return buffer