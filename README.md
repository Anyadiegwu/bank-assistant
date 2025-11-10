🏦 Bank AI Assistant

A simple Flask-based **AI banking chatbot** that uses **Google Gemini** and **prompt chaining** to handle banking-related conversations like account opening, billing issues, and loan inquiries.


## 🚀 Features

* Uses **Gemini 2.5 Flash Lite** via REST API
* Extracts and stores user details as JSON
* Classifies messages into banking categories
* Dynamically asks for missing info
* Interactive web chat interface



## ⚙️ Setup

```bash
git clone https://github.com/yourusername/bank-ai-assistant.git
cd bank-ai-assistant
pip install -r requirements.txt
```

Create a `.env` file:

```
GEMINI_API_KEY=your_google_gemini_api_key
```

Run:

```bash
python prompt-chain.py
```

Then open [http://127.0.0.1:5000/](http://127.0.0.1:5000/).



## 🧩 Tech Stack

* **Flask**
* **Requests**
* **Dotenv**
* **Google Gemini API**

