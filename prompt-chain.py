import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()
class AiAssistant:
    def __init__(self, api_endpoint, api_key):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def call_with_prompt(self, prompt):
        url = f"{self.api_endpoint}?key={self.api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3}
        }
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            return f"Error: {e}"

class SessionState:
    def __init__(self):
        self.data = {}
    
    def __contains__(self, key):
        return key in self.data
    
    def __getattr__(self, key):
        return self.data.get(key)
    
    def __setattr__(self, key, value):
        if key == 'data':
            super().__setattr__(key, value)
        else:
            self.data[key] = value

class PromptChainProcessor:
    CATEGORIES = """
- Account Opening
- Billing Issue
- Account Access
- Transaction Inquiry
- Card Services
- Account Statement
- Loan Inquiry
- General Information
"""
    
    def __init__(self, ai_assistant):
        self.ai = ai_assistant
    
    def step1_interpret_intent(self, user_input):
        prompt = f"""You are a Bank Assistant. Interpret the customer's intent clearly and concisely.
            Customer message: {user_input}
            Provide a clear interpretation of what the customer wants or needs. Be specific and professional."""
        return self.ai.call_with_prompt(prompt)
    
    def step2_suggest_categories(self, interpreted_message):
        prompt = f"""Map the query to one or more possible categories that may apply.
            Available Categories:
            {self.CATEGORIES}

            Interpreted customer request: 
            {interpreted_message}

            Return the suggested categories (one or more) that best match this request. Format: list the category names."""
        return self.ai.call_with_prompt(prompt)
    
    def step3_select_category(self, interpreted_message, suggested_categories):
        prompt = f"""Select the MOST appropriate single category from the suggestions.

            Suggested Categories:
            {suggested_categories}

            Interpreted customer request:
            {interpreted_message}

            Return ONLY the single most appropriate category name, nothing else."""
        return self.ai.call_with_prompt(prompt)
    
    def step4_extract_details(self, interpreted_message, user_input, selected_category, context_data):
        collected_info = json.dumps(context_data, indent=2) if context_data else "None yet"     
        prompt = f"""You are handling a banking request. Based on the category and information collected so far, determine what's needed next.

            Selected Category: {selected_category}

            Customer's original message: {user_input}

            Interpreted intent: {interpreted_message}

            Information already collected: 
            {collected_info}

            Task: 
            1. If you need more information to process this request, ask ONE specific follow-up question
            2. If you have enough information, acknowledge this and prepare to resolve the request
            3. Extract any new details from the customer's message

            Return your response in this JSON format:
            {{
                "status": "needs_info" or "ready_to_resolve",
                "extracted_data": {{"key": "value"}},
                "follow_up_question": "your question here" or null,
                "response_to_user": "friendly message to the customer"
            }}"""
        return self.ai.call_with_prompt(prompt)
    
    def step5_generate_response(self, selected_category, context_data):
        collected_info = json.dumps(context_data, indent=2)     
        prompt = f"""You are a professional banking assistant. Generate a helpful, friendly response to satisfy the customer.

            Request Category: {selected_category}

            Collected Information:
            {collected_info}

            Generate a concise, professional response that:
            1. Confirms what action you're taking or what information you're providing
            2. Addresses the customer's needs based on the category
            3. Is warm and reassuring
            4. Ends with an offer to help further if needed

            Keep it short and natural."""
        return self.ai.call_with_prompt(prompt)

def run_prompt_chain(customer_query, session_state=None):
    user_input = customer_query.strip()
    if not user_input:
        return ["Error: Empty input", None, None, None, None]
    
    if session_state is None:
        session_state = SessionState()
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
        session_state.ai_assistant = AiAssistant(api_url, gemini_api_key)
        session_state.processor = PromptChainProcessor(session_state.ai_assistant)
    
    if 'history' not in session_state:
        session_state.history = []
    session_state.history.append(user_input)   
    full_history = "\n".join(session_state.history)
    
    intermediate_outputs = []
    
    if 'interpreted_message' not in session_state:
        interpreted = session_state.processor.step1_interpret_intent(user_input)
        session_state.interpreted_message = interpreted
    else:
        interpreted = session_state.interpreted_message
    intermediate_outputs.append(interpreted)
    
    if 'suggested_categories' not in session_state:
        suggested_categories = session_state.processor.step2_suggest_categories(interpreted)
        session_state.suggested_categories = suggested_categories
    else:
        suggested_categories = session_state.suggested_categories
    intermediate_outputs.append(suggested_categories)
    
    if 'category' not in session_state:
        selected_category = session_state.processor.step3_select_category(interpreted, suggested_categories)
        if not selected_category:
            intermediate_outputs.append("Error: Failed to select category")
            intermediate_outputs.append(None)
            intermediate_outputs.append(None)
            return intermediate_outputs
        
        session_state.category = selected_category
        session_state.context_data = {}
    else:
        selected_category = session_state.category
    intermediate_outputs.append(selected_category)
    
    extraction_result = session_state.processor.step4_extract_details(
        interpreted,
        full_history,  
        session_state.category,
        session_state.context_data
    )   
    if not extraction_result:
        intermediate_outputs.append("Error: Failed to process request")
        intermediate_outputs.append(None)
        return intermediate_outputs
    
    intermediate_outputs.append(extraction_result)
    
    match = re.search(r'\{.*\}', extraction_result, re.DOTALL)
    final_response = None
    
    if match:
        try:
            response_data = json.loads(match.group())         
            if 'extracted_data' in response_data and response_data['extracted_data']:
                session_state.context_data.update(response_data['extracted_data'])
            
            if response_data.get('status') == 'ready_to_resolve':
                final_response = session_state.processor.step5_generate_response(
                    session_state.category,
                    session_state.context_data
                )
                if not final_response:
                    final_response = response_data.get('response_to_user', 'Your request has been processed.')
            else:
                final_response = response_data.get('response_to_user', 'Could you provide more details?')
        except:
            final_response = extraction_result
    else:
        final_response = extraction_result
    
    intermediate_outputs.append(final_response)
    
    return intermediate_outputs

def initialize_session():
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    
    session_state = SessionState()
    session_state.ai_assistant = AiAssistant(api_url, gemini_api_key)
    session_state.processor = PromptChainProcessor(session_state.ai_assistant)
    session_state.messages = [
        {"role": "assistant", "content": "Hello! Welcome. I'm your secure AI banking assistant. How can I help you today?"}
    ]   
    return session_state

if __name__ == '__main__':
    session = initialize_session()  
    print(session.messages[0]["content"])
    print()
    
    while True:
        user_input = input("You: ").strip()     
        if not user_input:
            continue
        
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print("Assistant: Thank you for using our banking service. Goodbye!")
            break
        
        session.messages.append({"role": "user", "content": user_input})
        
        intermediate_outputs = run_prompt_chain(user_input, session)
        
        final_response = intermediate_outputs[-1] if intermediate_outputs else "Error processing request"
        
        session.messages.append({"role": "assistant", "content": final_response})
        
        print(f"\n--- Intermediate Outputs ---")
        print(f"Stage 1 (Intent): {intermediate_outputs[0]}")
        print(f"Stage 2 (Categories): {intermediate_outputs[1]}")
        print(f"Stage 3 (Selected): {intermediate_outputs[2]}")
        print(f"Stage 4 (Extraction): {intermediate_outputs[3][:100]}..." if len(str(intermediate_outputs[3])) > 100 else f"Stage 4 (Extraction): {intermediate_outputs[3]}")
        print(f"Stage 5 (Final): {intermediate_outputs[4]}")
        print("----------------------------\n")
        
        print(f"Assistant: {final_response}")
        print()