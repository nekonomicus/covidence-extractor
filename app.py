import os
import json
import base64
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max total
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure Gemini client
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

EXTRACTION_PROMPT = """You are a systematic review data extraction assistant for a META-ANALYSIS ON SEX DIFFERENCES in burst fracture treatment outcomes.

=== CRITICAL: THOROUGH PDF SEARCH STRATEGY ===
You MUST systematically search the ENTIRE document for sex/gender-related information:

1. KEYWORD SEARCH - Scan for these terms throughout:
   - sex, gender, male, female, men, women, M/F, m/f
   - stratified, subgroup, covariate, adjusted, interaction
   - "by sex", "by gender", "sex-specific", "gender-specific"

2. LOCATIONS TO CHECK (in order):
   - TITLE & ABSTRACT: Often mentions if sex analysis was performed
   - METHODS → Participants/Inclusion: Sex distribution
   - METHODS → Statistical Analysis: Sex as covariate? Subgroup analysis? Interaction terms?
   - RESULTS → Baseline Characteristics Table: ALWAYS check for M/F breakdown
   - RESULTS → ALL Tables: Look for sex-stratified rows/columns
   - RESULTS → Figures: Forest plots with sex subgroups? Any sex-stratified figures?
   - RESULTS → Subgroup Analyses section: Sex-specific outcomes?
   - DISCUSSION → Often mentions sex findings or lack thereof
   - DISCUSSION → Limitations: "did not analyze by sex" or similar
   - SUPPLEMENTARY MATERIALS: Often contains sex-stratified data not in main text

3. TABLE DEEP-DIVE:
   - For EACH table, check if data is broken down by sex
   - Look for rows labeled "Male" / "Female" or columns with M/F headers
   - Check table footnotes for sex-related notes

=== EXTRACTION INSTRUCTIONS ===
- If information is NOT found after thorough search: respond with "NR" (Not Reported)
- For each field with data: provide EXACT quote with location (e.g., "Table 2", "Methods, p.4", "Figure 3 legend")
- Be precise with numbers - extract exact values
- Calculate percentages if only raw numbers given

=== REQUIRED FIELDS (return as JSON) ===

{
  "general_information": {
    "authors_year": {
      "value": "First author et al. YYYY",
      "evidence": "From title/header"
    },
    "country": {
      "value": "One of: United States, Australia, Europe, Asia, Other (specify)",
      "evidence": "Quote with location"
    }
  },
  "methods": {
    "aim_objective": {
      "value": "The stated aim/objective of the study",
      "evidence": "Quote from paper"
    },
    "study_procedure": {
      "value": "One of: Operative treatment techniques, Operative vs conservative, Conservative treatment",
      "evidence": "Quote with location"
    },
    "study_design": {
      "value": "One of: Randomised controlled trial, Non-randomised prospective study, Cohort study, Case control study, Retrospective Study, Other (specify)",
      "evidence": "Quote with location"
    },
    "start_date": {
      "value": "Date or period when study started",
      "evidence": "Quote with location"
    },
    "end_date": {
      "value": "Date or period when study ended",
      "evidence": "Quote with location"
    }
  },
  "participants": {
    "total_number": {
      "value": "Number",
      "evidence": "Quote with location"
    },
    "females_total_number": {
      "value": "Number",
      "evidence": "Quote with location (e.g., 'Table 1: Female n=45')"
    },
    "females_percentage": {
      "value": "Percentage (e.g., 32.5%)",
      "evidence": "Quote or show calculation"
    },
    "males_total_number": {
      "value": "Number",
      "evidence": "Quote with location"
    },
    "males_percentage": {
      "value": "Percentage",
      "evidence": "Quote or show calculation"
    },
    "sex_ratio_reported_per_treatment_arm": {
      "value": "Yes/No - If Yes, specify: e.g., 'Operative: 30M/15F, Conservative: 25M/20F'",
      "evidence": "Quote with location"
    },
    "age_female_mean": {
      "value": "Number",
      "evidence": "Quote with location"
    },
    "age_female_sd": {
      "value": "Number",
      "evidence": "Quote with location"
    },
    "age_male_mean": {
      "value": "Number",
      "evidence": "Quote with location"
    },
    "age_male_sd": {
      "value": "Number",
      "evidence": "Quote with location"
    },
    "age_overall_mean": {
      "value": "Number (if sex-specific not available)",
      "evidence": "Quote with location"
    },
    "age_overall_sd": {
      "value": "Number",
      "evidence": "Quote with location"
    }
  },
  "sex_analysis_methods": {
    "sex_used_as_covariate": {
      "value": "Yes/No/NR",
      "evidence": "Quote from Statistical Analysis section"
    },
    "sex_stratified_subgroup_analysis": {
      "value": "Yes/No/NR",
      "evidence": "Quote describing subgroup analysis"
    },
    "sex_interaction_tested": {
      "value": "Yes/No/NR - If Yes, report p-value for interaction",
      "evidence": "Quote with statistical result"
    },
    "sex_mentioned_in_limitations": {
      "value": "Yes/No - If Yes, what was said?",
      "evidence": "Quote from Discussion/Limitations"
    }
  },
  "sex_differences_results": {
    "any_sex_stratified_outcomes_reported": {
      "value": "Yes/No",
      "evidence": "List ALL locations where sex-stratified data appears (tables, figures, text)"
    },
    "primary_outcome_by_sex": {
      "value": "Describe if primary outcome was reported separately for M/F",
      "evidence": "Quote with exact values if available"
    },
    "secondary_outcomes_by_sex": {
      "value": "Describe any secondary outcomes reported by sex",
      "evidence": "Quote with exact values if available"
    },
    "complications_by_sex": {
      "value": "Were complications/adverse events reported by sex?",
      "evidence": "Quote if available"
    },
    "statistically_significant_sex_difference_found": {
      "value": "Yes/No/Not tested - If Yes, describe finding and p-value",
      "evidence": "Exact quote with statistical values"
    },
    "direction_of_sex_difference": {
      "value": "If difference found: Males better / Females better / Mixed / NR",
      "evidence": "Quote supporting direction"
    }
  },
  "outcomes_overall": {
    "primary_outcome_name": {
      "value": "Name of primary outcome measure",
      "evidence": "Quote"
    },
    "intervention1_name": {
      "value": "Name of intervention 1",
      "evidence": "Quote"
    },
    "intervention1_mean": {
      "value": "Number",
      "evidence": "Quote with location"
    },
    "intervention1_sd": {
      "value": "Number",
      "evidence": "Quote with location"
    },
    "intervention1_n": {
      "value": "Sample size for intervention 1",
      "evidence": "Quote"
    },
    "intervention2_name": {
      "value": "Name of intervention 2",
      "evidence": "Quote"
    },
    "intervention2_mean": {
      "value": "Number",
      "evidence": "Quote with location"
    },
    "intervention2_sd": {
      "value": "Number",
      "evidence": "Quote with location"
    },
    "intervention2_n": {
      "value": "Sample size for intervention 2",
      "evidence": "Quote"
    }
  },
  "outcomes_by_sex": {
    "intervention1_female": {
      "n": {"value": "Number", "evidence": "Quote"},
      "mean": {"value": "Number", "evidence": "Quote"},
      "sd": {"value": "Number", "evidence": "Quote"}
    },
    "intervention1_male": {
      "n": {"value": "Number", "evidence": "Quote"},
      "mean": {"value": "Number", "evidence": "Quote"},
      "sd": {"value": "Number", "evidence": "Quote"}
    },
    "intervention2_female": {
      "n": {"value": "Number", "evidence": "Quote"},
      "mean": {"value": "Number", "evidence": "Quote"},
      "sd": {"value": "Number", "evidence": "Quote"}
    },
    "intervention2_male": {
      "n": {"value": "Number", "evidence": "Quote"},
      "mean": {"value": "Number", "evidence": "Quote"},
      "sd": {"value": "Number", "evidence": "Quote"}
    }
  },
  "extraction_notes": "Summary of sex-related reporting: What was reported, what was missing, any concerns about the extraction, notable findings for the meta-analysis"
}

=== FINAL REMINDERS ===
- Use "NR" for any field where information is not reported after thorough search
- ALWAYS include evidence with LOCATION (table number, section name, page if visible)
- If multiple PDFs provided, synthesize across all documents
- For study design keywords: "randomized", "prospective", "retrospective", "cohort"
- Check Methods section for enrollment periods/dates
- BE AGGRESSIVE in searching for sex data - check every table and figure

Return ONLY the JSON object, no additional text."""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract_data():
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    
    if len(files) > 3:
        return jsonify({'error': 'Maximum 3 PDFs allowed'}), 400
    
    if len(files) == 0 or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files selected'}), 400
    
    # Process PDFs
    pdf_parts = []
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            # Read file content directly
            file_content = file.read()
            pdf_parts.append(
                types.Part.from_bytes(
                    data=file_content,
                    mime_type='application/pdf'
                )
            )
    
    if not pdf_parts:
        return jsonify({'error': 'No valid PDF files found'}), 400
    
    try:
        # Build content with PDFs and prompt
        content_parts = pdf_parts + [EXTRACTION_PROMPT]
        
        # Use Gemini 3 Flash (thinking is enabled by default)
        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=content_parts,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=8192
            )
        )
        
        # Parse the response
        response_text = response.text
        
        # Try to extract JSON from response
        # Sometimes the model wraps it in markdown code blocks
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]
        
        try:
            extracted_data = json.loads(response_text.strip())
        except json.JSONDecodeError:
            # Return raw text if JSON parsing fails
            return jsonify({
                'success': True,
                'raw_response': response_text,
                'parse_error': True
            })
        
        return jsonify({
            'success': True,
            'data': extracted_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
