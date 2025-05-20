from flask import Flask, render_template, request, send_file, jsonify, session, redirect, url_for, send_from_directory
from docx import Document
import pdfkit
import uuid
from bs4 import BeautifulSoup
from html2docx import html2docx
from datetime import timedelta
from flask_session import Session
import os
import json
import mammoth
import collections
import collections.abc
collections.Hashable = collections.abc.Hashable

from pydocx import PyDocX

# Initialize Flask app
app = Flask(__name__)
app.config.update(
    SECRET_KEY='your-secret-key-here',
    UPLOAD_FOLDER='uploads',
    SESSION_COOKIE_SECURE=False,  # For development
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    SESSION_TYPE='filesystem',
    SESSION_FILE_DIR='./flask_sessions',
    SESSION_FILE_THRESHOLD=100
)

# PDFKit configuration
path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

# Initialize server-side session storage
Session(app)

# Ensure required directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/fonts', exist_ok=True)
os.makedirs('drafts', exist_ok=True)

@app.route('/')
def upload_page():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file uploaded!", 400

    file = request.files['file']
    if file.filename == '':
        return "No file selected!", 400

    if file and file.filename.endswith('.docx'):
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        
        filename = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{file.filename}")
        file.save(filename)
        
        session['original_filename'] = file.filename
        return redirect(f'/editor?filename={file.filename}')
    else:
        return "Only .docx files allowed!", 400

@app.route('/editor')
def editor():
    filename = request.args.get('filename')
    if not filename or 'session_id' not in session:
        return redirect('/')
    
    session_id = session['session_id']
    doc_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{filename}")
    # Convert DOCX to HTML using mammoth
    with open(doc_path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file)
        html_content = result.value  # Formatted HTML content
    # # ✅ Convert DOCX to HTML with PyDocX (preserves alignment better)
    # html_content = PyDocX.to_html(doc_path)
    return render_template('editor.html', content=html_content, filename=filename)
    # return render_template('editor.html', content=paragraphs, filename=filename)

@app.route('/save_draft', methods=['POST'])
def save_draft():
    try:
        if 'session_id' not in session:
            return jsonify({'status': 'error', 'message': 'Session expired'}), 400
        
        content = request.form.get('content', '')
        filename = request.form.get('filename', '')
        
        # Generate unique draft ID
        draft_id = str(uuid.uuid4())
        draft_path = os.path.join('drafts', f"{draft_id}.json")
        
        # Save with UTF-8 encoding
        with open(draft_path, 'w', encoding='utf-8') as f:
            json.dump({
                'content': content,
                'filename': filename
            }, f, ensure_ascii=False)
        
        # Store just the draft ID in session
        session['current_draft'] = draft_id
        return jsonify({'status': 'success'})
    
    except Exception as e:
        app.logger.error(f"Error saving draft: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/prepare_fill_fields', methods=['POST'])
def prepare_fill_fields():
    try:
        if 'session_id' not in session:
            return jsonify({'status': 'error', 'message': 'Session expired'}), 400
        
        content = request.form.get('content', '')
        filename = request.form.get('filename', '')
        
        # Create a clean HTML structure with buyer template
        full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Times New Roman', serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
        }}
        .buyer-template {{
            margin-bottom: 30px;
            padding: 15px;
            border: 1px dashed #ccc;
            background-color: #f9f9f9;
        }}
        .field-placeholder {{
            background-color: #e7f5ff;
            border: 1px dashed #228be6;
            padding: 2px 4px;
            border-radius: 4px;
            color: #228be6;
        }}
    </style>
</head>
<body>
    <div class="document-content">
        {content}
        <!-- Buyer 1 Section -->
    <div class="buyer-section">
        <h3>Buyer 1 Details</h3>
        <p>Name: <span data-field="name_1" class="field-placeholder">[Name]</span></p>
        <p>PAN No: <span data-field="pan_no_1" class="field-placeholder">[PAN]</span></p>
        <p>Aadhaar No: <span data-field="aadhaar_no_1" class="field-placeholder">[Aadhaar]</span></p>
        <p>Address Line 1: <span data-field="address1_1" class="field-placeholder">[Address 1]</span></p>
        <p>Address Line 2: <span data-field="address2_1" class="field-placeholder">[Address 2]</span></p>
    </div>
    
    <!-- Buyer 2 Section -->
    <div class="buyer-section">
        <h3>Buyer 2 Details</h3>
        <p>Name: <span data-field="name_2" class="field-placeholder">[Name]</span></p>
        <p>PAN No: <span data-field="pan_no_2" class="field-placeholder">[PAN]</span></p>
        <p>Aadhaar No: <span data-field="aadhaar_no_2" class="field-placeholder">[Aadhaar]</span></p>
        <p>Address Line 1: <span data-field="address1_2" class="field-placeholder">[Address 1]</span></p>
        <p>Address Line 2: <span data-field="address2_2" class="field-placeholder">[Address 2]</span></p>
    </div>
    </div>
</body>
</html>
"""
        
        # Save the complete HTML
        draft_id = str(uuid.uuid4())
        draft_path = os.path.join('drafts', f"{draft_id}.html")
        
        with open(draft_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        session['current_draft'] = draft_id
        return jsonify({
            'status': 'success', 
            'redirect': url_for('fill_fields')
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/fill_fields')
def fill_fields():
    if 'current_draft' not in session:
        return redirect(url_for('upload_page'))
    
    draft_path = os.path.join('drafts', f"{session['current_draft']}.html")
    try:
        with open(draft_path, 'r', encoding='utf-8') as f:
            document_content = f.read()
        
        # If it's a POST request, we are saving the user's input
        if request.method == 'POST':
            buyer_data = {
                'name': request.form.get('name'),
                'pan_no': request.form.get('pan_no'),
                'aadhaar_no': request.form.get('aadhaar_no'),
                'address1': request.form.get('address1'),
                'address2': request.form.get('address2')
            }
            
            # Replace placeholders in document content with actual values
            for field, value in buyer_data.items():
                document_content = document_content.replace(f'<span data-field="{field}" class="field-placeholder">[Enter {field.capitalize()}]</span>', value)
            
            # Save the filled document content in the session
            session['filled_document'] = document_content
            
            return redirect(url_for('export_pdf'))  # Automatically redirect to export route

        # Render the fill_fields.html template with document content
        return render_template('fill_fields.html',
                            document_content=document_content,
                            filename=session.get('original_filename', 'document'))
    except Exception as e:
        return redirect(url_for('upload_page'))
    
# @app.route('/export_word', methods=['POST'])
# def export_word():
    
#     try:
#         if 'session_id' not in session:
#             return "Session expired", 400
#         # Get the filled HTML document
#         filled_html = request.form.get('filled_document', '')
#         filename = request.form.get('filename', 'document.docx')
        
#         # edited_content = request.form.get('edited_content', '')
#         # filename = request.form.get('filename', 'document.docx')

#         field_values = {}
#         for key in request.form:
#             if key.startswith('field_'):
#                 field_values[key[6:]] = request.form[key]
#         # Process the HTML to replace field placeholders with values
#         soup = BeautifulSoup(filled_html, 'html.parser')

#         # Replace all field placeholders with their values
#         for field_name, value in field_values.items():
#             for element in soup.find_all(attrs={"data-field": field_name}):
#                 element.string = value
#                 element.attrs.pop('data-field', None)
#                 element.attrs.pop('contenteditable', None)
#                 element.attrs.pop('class', None)
#         for style_tag in soup.find_all('style'):
#             style_tag.decompose()
#         clean_html = str(soup)
#         # html = f"""
#         # <!DOCTYPE html>
#         # <html>
#         # <head>
#         #     <meta charset="UTF-8">
#         #     <style>
#         #         body {{ font-family: Arial; line-height: 1.6; }}
#         #         h1 {{ color: #2c3e50; }}
#         #         .content {{ margin: 20px; }}
#         #     </style>
#         # </head>
#         # <body>
#         #     <div class="content">
#         #         {edited_content}
#         #     </div>
#         # </body>
#         # </html>
#         # """
        
#         # soup = BeautifulSoup(html, 'html.parser')
#         # for style_tag in soup.find_all('style'):
#         #     style_tag.decompose()
#         # clean_html = str(soup)
        
#         buffer = html2docx(clean_html, title="Document")
#         word_filename = filename if filename.endswith('.docx') else f"{filename}.docx"
#         word_path = os.path.join(app.config['UPLOAD_FOLDER'], word_filename)

#         with open(word_path, 'wb') as f:
#             f.write(buffer.getvalue())

#         return send_file(word_path, as_attachment=True, download_name=word_filename)
    
#     except Exception as e:
#         app.logger.error(f"Error exporting Word: {str(e)}")
#         return f"Word export failed: {str(e)}", 500

@app.route('/export', methods=['POST'])
def export_pdf():
    
    try:
        if 'session_id' not in session:
            return "Session expired", 400
        
        # Get the filled HTML document
        filled_html = request.form.get('filled_document', '')
        filename = request.form.get('filename', 'document.pdf')
        
        
        # Get all field values
        field_values = {}
        for key in request.form:
            if key.startswith('field_'):
                field_values[key[6:]] = request.form[key]

        # Process the HTML to replace field placeholders with values
        soup = BeautifulSoup(filled_html, 'html.parser')
        
        # Replace all field placeholders with their values
        for field_name, value in field_values.items():
            for element in soup.find_all(attrs={"data-field": field_name}):
                element.string = value
                element.attrs.pop('data-field', None)
                element.attrs.pop('contenteditable', None)
                element.attrs.pop('class', None)
        
        clean_html = str(soup)
        # html = f"""
        # <!DOCTYPE html>
        # <html>
        # <head>
        #     <meta charset="UTF-8">
        #     <title>Document</title>
        #     <style>
        #         body {{ font-family: Arial; line-height: 1.6; }}
        #         h1 {{ color: #2c3e50; }}
        #         .content {{ margin: 20px; }}
        #     </style>
        # </head>
        # <body>
        #     <div class="content">
        #         {edited_content}
        #     </div>
        # </body>
        # </html>
        # """

        pdf_filename = filename.replace('.docx', '.pdf') if filename.endswith('.docx') else filename
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)

        pdfkit.from_string(clean_html, pdf_path, configuration=config)
        return send_file(pdf_path, as_attachment=True, download_name=pdf_filename)
    
    except Exception as e:
        app.logger.error(f"Error exporting PDF: {str(e)}")
        return f"PDF generation failed: {str(e)}", 500

@app.route('/static/fonts/<path:filename>')
def serve_fonts(filename):
    fonts_dir = os.path.join(app.root_path, 'static', 'fonts')
    return send_from_directory(fonts_dir, filename)

if __name__ == '__main__':
    app.run(debug=True)