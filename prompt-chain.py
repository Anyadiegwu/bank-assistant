import os
import re
import json
import requests
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

class AiAssistant:
    def __init__(self, api_endpoint, api_key, default_model):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.default_model = default_model

    def call_with_prompt(self, prompt, model=None):
        url = f"{self.api_endpoint}?key={self.api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3}
        }
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"Error: {e}")
            return None

# Initialize AI Assistant
gemini_api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
gemini_api_key = os.getenv('GEMINI_API_KEY')
gemi = AiAssistant(gemini_api_url, gemini_api_key, "gemini-2.5-flash-lite")

categories = """
- Account Opening
- Billing Issue
- Account Access
- Transaction Inquiry
- Card Services
- Account Statement
- Loan Inquiry
- General Information
"""

# Store sessions (in production, use Redis or database)
sessions = {}

@app.route('/')
def home():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bank AI Assistant</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            #chat-box { border: 1px solid #ccc; height: 400px; overflow-y: auto; padding: 15px; margin-bottom: 20px; background: #f9f9f9; }
            .message { margin: 10px 0; padding: 10px; border-radius: 5px; }
            .user { background: #007bff; color: white; text-align: right; }
            .bot { background: #e9ecef; }
            #user-input { width: 80%; padding: 10px; }
            #send-btn { width: 18%; padding: 10px; background: #007bff; color: white; border: none; cursor: pointer; }
            #send-btn:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <h1>🏦 Bank AI Assistant</h1>
        <div id="chat-box"></div>
        <input type="text" id="user-input" placeholder="Type your message..." />
        <button id="send-btn" onclick="sendMessage()">Send</button>

        <script>
            let sessionId = Math.random().toString(36).substring(7);
            
            window.onload = function() {
                addBotMessage("Hello! Welcome. I'm your secure AI banking assistant. How can I help you today?");
            };

            function addBotMessage(message) {
                const chatBox = document.getElementById('chat-box');
                chatBox.innerHTML += '<div class="message bot"><strong>Bot:</strong> ' + message + '</div>';
                chatBox.scrollTop = chatBox.scrollHeight;
            }

            function addUserMessage(message) {
                const chatBox = document.getElementById('chat-box');
                chatBox.innerHTML += '<div class="message user"><strong>You:</strong> ' + message + '</div>';
                chatBox.scrollTop = chatBox.scrollHeight;
            }

            async function sendMessage() {
                const input = document.getElementById('user-input');
                const message = input.value.trim();
                
                if (!message) return;
                
                addUserMessage(message);
                input.value = '';

                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: message, session_id: sessionId })
                    });
                    
                    const data = await response.json();
                    addBotMessage(data.response);
                } catch (error) {
                    addBotMessage('Sorry, an error occurred. Please try again.');
                }
            }

            document.getElementById('user-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') sendMessage();
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/chat', methods=['POST'])
def run_prompt_chain():
    data = request.json
    user_input = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    # Initialize session if new
    if session_id not in sessions:
        sessions[session_id] = {
            'context_data': {},
            'predicted_category': None,
            'conversation_history': []
        }
    
    session = sessions[session_id]
    
    # Extract details
    prompt1 = f"""
    You are a precise requirements-extraction assistant for a bank.
    Extract key information from the user's message as a JSON object.
    
    Current context: {json.dumps(session['context_data'], indent=2)}
    User message: {user_input}
    
    Output ONLY a JSON object.
    """
    
    extracted_detail = gemi.call_with_prompt(prompt1)
    new_data = {}
    match = re.search(r'(\{.*\})', extracted_detail, re.DOTALL)
    if match:
        try:
            new_data = json.loads(match.group())
            for key, value in new_data.items():
                if value:
                    session['context_data'][key] = value
        except:
            pass
    
    # Classify category
    if session['predicted_category'] is None:
        prompt2 = f"""
        Classify this banking request into one category:
        {categories}
        
        User message: {user_input}
        Return ONLY the category name.
        """
        session['predicted_category'] = gemi.call_with_prompt(prompt2).strip()
    
    # Controller
    prompt3 = f"""
    You are a banking conversation controller.
    
    Category: {session['predicted_category']}
    Collected info: {json.dumps(session['context_data'], indent=2)}
    User message: {user_input}
    
    Required for Account Opening: full_name, date_of_birth, address, account_type
    
    - Do NOT ask for information already collected
    - Ask for ONE missing field at a time
    - If all info collected, say "All information collected. Routing to handler."
    
    Already collected: {', '.join(session['context_data'].keys())}
    """
    
    controller_response = gemi.call_with_prompt(prompt3)
    
    session['conversation_history'].append({
        'user_input': user_input,
        'response': controller_response
    })
    
    return jsonify({'response': controller_response})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)