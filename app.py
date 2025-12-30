import os
import json
import base64
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max total
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure Gemini
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

EXTRACTION_PROMPT = """You are a systematic review data extraction assistant. Your task is to extract specific data from medical/scientific research papers about burst fracture treatment for a Covidence systematic review.

CRITICAL INSTRUCTIONS:
1. Read the PDF(s) carefully and extract ALL requested information
2. If information is NOT found or NOT clearly stated, respond with "NR" (Not Reported)
3. For each field where you FOUND information, provide a brief QUOTE or CITATION from the paper as evidence
4. Be precise with numbers - extract exact values when available
5. For percentages, calculate them if raw numbers are given but percentage isn't stated

Extract the following fields and return as JSON:

{
  "general_information": {
    "authors_year": {
      "value": "First author et al. YYYY",
      "evidence": "Quote or page reference"
    },
    "country": {
      "value": "One of: United States, Australia, Europe, Asia, Other (specify)",
      "evidence": "Quote or page reference"
    }
  },
  "methods": {
    "aim_objective": {
      "value": "The stated aim/objective of the study",
      "evidence": "Quote from paper"
    },
    "study_procedure": {
      "value": "One of: Operative treatment techniques, Operative vs conservative, Conservative treatment",
      "evidence": "Quote or description"
    },
    "study_design": {
      "value": "One of: Randomised controlled trial, Non-randomised prospective study, Cohort study, Case control study, Retrospective Study, Other (specify)",
      "evidence": "Quote or description"
    },
    "start_date": {
      "value": "Date or period when study started",
      "evidence": "Quote"
    },
    "end_date": {
      "value": "Date or period when study ended",
      "evidence": "Quote"
    }
  },
  "participants": {
    "total_number": {
      "value": "Number",
      "evidence": "Quote"
    },
    "females_total_number": {
      "value": "Number",
      "evidence": "Quote"
    },
    "females_percentage": {
      "value": "Percentage",
      "evidence": "Quote or calculation"
    },
    "gender_differences_reported": {
      "value": "Yes or No",
      "evidence": "Quote if Yes, or 'Not mentioned' if No"
    },
    "treatment_outcome_gender_differences": {
      "value": "Yes, No, or Unknown/Not reported",
      "evidence": "Quote if applicable"
    },
    "age_female_mean": {
      "value": "Number",
      "evidence": "Quote"
    },
    "age_female_sd": {
      "value": "Number",
      "evidence": "Quote"
    },
    "age_male_mean": {
      "value": "Number",
      "evidence": "Quote"
    },
    "age_male_sd": {
      "value": "Number",
      "evidence": "Quote"
    }
  },
  "outcomes_timepoint1": {
    "intervention1_name": {
      "value": "Name of intervention 1",
      "evidence": "Quote"
    },
    "intervention1_mean": {
      "value": "Number",
      "evidence": "Quote"
    },
    "intervention1_sd": {
      "value": "Number",
      "evidence": "Quote"
    },
    "intervention2_name": {
      "value": "Name of intervention 2",
      "evidence": "Quote"
    },
    "intervention2_mean": {
      "value": "Number",
      "evidence": "Quote"
    },
    "intervention2_sd": {
      "value": "Number",
      "evidence": "Quote"
    }
  },
  "outcomes_by_gender": {
    "intervention1": {
      "name": {"value": "Name", "evidence": "Quote"},
      "female_mean": {"value": "Number", "evidence": "Quote"},
      "female_sd": {"value": "Number", "evidence": "Quote"},
      "male_mean": {"value": "Number", "evidence": "Quote"},
      "male_sd": {"value": "Number", "evidence": "Quote"}
    },
    "intervention2": {
      "name": {"value": "Name", "evidence": "Quote"},
      "female_mean": {"value": "Number", "evidence": "Quote"},
      "female_sd": {"value": "Number", "evidence": "Quote"},
      "male_mean": {"value": "Number", "evidence": "Quote"},
      "male_sd": {"value": "Number", "evidence": "Quote"}
    }
  },
  "extraction_notes": "Any important notes, limitations, or clarifications about the extraction"
}

IMPORTANT REMINDERS:
- Use "NR" for any field where information is not reported/found
- Always include evidence quotes to support your extraction
- If multiple PDFs are provided, synthesize information across them (they may be the same study)
- Pay attention to tables, figures, and supplementary materials in the PDFs
- For study design, look for keywords like "randomized", "prospective", "retrospective", "cohort"
- For dates, check the methods section for enrollment periods

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
            pdf_parts.append({
                'mime_type': 'application/pdf',
                'data': base64.standard_b64encode(file_content).decode('utf-8')
            })
    
    if not pdf_parts:
        return jsonify({'error': 'No valid PDF files found'}), 400
    
    try:
        # Use Gemini 2.0 Flash Thinking
        model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21')
        
        # Build content with PDFs and prompt
        content_parts = []
        for i, pdf in enumerate(pdf_parts):
            content_parts.append({
                'inline_data': {
                    'mime_type': pdf['mime_type'],
                    'data': pdf['data']
                }
            })
        content_parts.append(EXTRACTION_PROMPT)
        
        response = model.generate_content(
            content_parts,
            generation_config={
                'temperature': 0.1,
                'max_output_tokens': 8192,
            }
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

