# Covidence Data Extractor

A web app to semi-automate systematic review data extraction for Covidence using Google's Gemini AI.

## Features

- **Drag & Drop PDF Upload**: Upload up to 3 PDFs at once
- **AI-Powered Extraction**: Uses Gemini 2.0 Flash Thinking to read and extract data
- **Covidence-Ready Output**: Fields formatted exactly for Covidence extraction forms
- **Citation Evidence**: Each extracted value includes a quote from the paper for verification
- **One-Click Copy**: Copy individual fields or all data at once
- **Human-in-the-Loop**: Review AI suggestions with source citations before use

## Extracted Fields

### General Information
- Authors & Year
- Country

### Methods
- AIM/Objective
- Study procedure (Operative/Conservative)
- Study design (RCT, Cohort, etc.)
- Start/End dates

### Participants
- Total number
- Female count & percentage
- Gender differences reported
- Age (Mean/SD by gender)

### Outcomes
- Intervention outcomes (Mean/SD)
- Gender-stratified outcomes

## Deployment

### Environment Variables

Set the following environment variable:

```
GEMINI_API_KEY=your_google_ai_api_key
```

Get your API key from: https://makersuite.google.com/app/apikey

### Deploy to Render

1. Connect your GitHub repo to Render
2. Create a new Web Service
3. Set the environment variable `GEMINI_API_KEY`
4. Deploy!

## Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variable
export GEMINI_API_KEY=your_key_here

# Run
python app.py
```

Visit http://localhost:5000

## Usage

1. Open the app
2. Drag & drop or select PDF(s) of your study
3. Click "Extract Data with Gemini"
4. Review extracted data with citations
5. Copy individual fields or use "Copy All" for plain text
6. Paste into Covidence

## Notes

- NR = Not Reported (information not found in paper)
- Always verify extracted data against the source
- Citations help identify where data was found

