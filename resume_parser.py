import pdfplumber
import spacy
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import re

# Load spaCy model
nlp = spacy.load('en_core_web_sm')

# Connect to PostgreSQL
conn = psycopg2.connect(
    dbname="your_dbname",
    user="your_username",
    password="your_password",
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

# Create table for candidates if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS candidates (
    id SERIAL PRIMARY KEY,
    name TEXT,
    skills TEXT,
    education TEXT
);
""")
conn.commit()

# Extract text from PDF
def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# Extract candidate details using spaCy and regex heuristics
def extract_candidate_details(text):
    doc = nlp(text)

    # Extract name - first PERSON entity assuming it's the candidate name
    name = None
    for ent in doc.ents:
        if ent.label_ == 'PERSON':
            name = ent.text
            break

    # Extract skills - match common tech keywords or read from a "Skills" section
    skills = []
    skill_list = ['Python', 'Java', 'C++', 'SQL', 'Flask', 'Django', 'PostgreSQL', 'Machine Learning', 'Data Analysis', 'NLP', 'spaCy']
    # Case insensitive search for skills
    for skill in skill_list:
        if re.search(r'\b' + re.escape(skill) + r'\b', text, re.I):
            skills.append(skill)
    skills_str = ", ".join(skills)

    # Extract education info - find education-related keywords and grab surrounding text
    education = []
    edu_keywords = ['Bachelor', 'Master', 'B.Sc', 'M.Sc', 'PhD', 'University', 'College', 'Institute']
    lines = text.split('\n')
    for line in lines:
        if any(keyword in line for keyword in edu_keywords):
            education.append(line.strip())
    education_str = "; ".join(education)

    return {
        "name": name,
        "skills": skills_str,
        "education": education_str
    }

# Save candidate info to the database
def save_candidate_to_db(candidate):
    cursor.execute(
        "INSERT INTO candidates (name, skills, education) VALUES (%s, %s, %s) RETURNING id",
        (candidate['name'], candidate['skills'], candidate['education'])
    )
    conn.commit()
    return cursor.fetchone()[0]

# Flask web app for uploading resumes and parsing
app = Flask(_name_)

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and file.filename.endswith('.pdf'):
        file_path = "./temp_resume.pdf"
        file.save(file_path)
        text = extract_text_from_pdf(file_path)
        candidate = extract_candidate_details(text)
        candidate_id = save_candidate_to_db(candidate)
        return jsonify({"message": "Resume parsed successfully", "candidate_id": candidate_id, "candidate": candidate})
    else:
        return jsonify({"error": "Only PDF files are supported"}), 400

if _name_ == "_main_":
    app.run(debug=True)