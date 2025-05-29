# finance-assistant
# 🎙️ Finance Voice & Document Assistant

## A Resourceful Build on Limited Hardware

**Built in just one day**, this project is a testament to what can be achieved even with significant hardware constraints. Developed on a **9-year-old laptop with only 4GB of RAM**, the methodology emphasizes direct API integrations and efficient processing to deliver a functional multi-source finance assistant without relying on heavy, resource-intensive models that would overwhelm the system.

## Overview

This Streamlit application serves as a versatile finance assistant, combining voice interaction with document analysis to provide quick access to financial information. It's designed to be intuitive and efficient, even on less powerful machines.

## Features

* **🎙️ Voice Query Analysis:**
    * **Live Microphone Input:** Record your financial questions directly in the browser.
    * **Speech-to-Text (AssemblyAI):** Transcribes your spoken queries into text.
    * **Intelligent Stock Search:** Extracts potential company names and stock symbols from your voice input.
    * **Real-time Stock Information:** Fetches current prices, daily/weekly changes, market cap, and business summaries using `yfinance` and Financial Modeling Prep (FMP) API.
    * **Audio Responses (gTTS):** Synthesizes spoken summaries of stock information back to you.

* **📄 PDF Document Analysis:**
    * **PDF Text Extraction:** Upload financial PDF documents (e.g., earnings reports) and extract all text content.
    * **Text Preview & Chunking:** Displays a preview of the extracted text and demonstrates how it's broken down into smaller chunks, a foundational step for future RAG (Retrieval-Augmented Generation) implementations.
    * **PDF Stock Identification:** Attempts to automatically identify stock symbols and relevant financial keywords within the document's content.

## Methodology & Technology Choices

Given the constraints of a 4GB RAM, 9-year-old laptop, the focus was on leveraging external APIs for compute-heavy tasks like Speech-to-Text and financial data retrieval, minimizing local processing overhead.

* **Frontend & Application Framework:** [Streamlit](https://streamlit.io/) provides a fast and easy way to build interactive web applications in Python, minimizing complex frontend development.
* **Voice Input:** A custom HTML/JavaScript component embedded via Streamlit's `st.components.v1.html` was used for direct microphone access and audio recording. This avoids reliance on external Python libraries that might introduce heavier dependencies or compatibility issues.
* **Speech-to-Text (STT):** [AssemblyAI](https://www.assemblyai.com/) is used for high-accuracy speech transcription. This offloads the intensive STT processing to a powerful external service.
* **Financial Data:**
    * [YFinance](https://pypi.org/project/yfinance/) (Yahoo Finance) is a reliable and free source for historical and real-time stock data.
    * [Financial Modeling Prep (FMP) API](https://financialmodelingprep.com/) is used for broader company/symbol search capabilities. (Note: FMP's free tier has strict rate limits.)
* **Text-to-Speech (TTS):** [gTTS (Google Text-to-Speech)](https://pypi.org/project/gTTS/) generates natural-sounding audio responses from text summaries.
* **PDF Processing:** [PyMuPDF (fitz)](https://pypi.org/project/PyMuPDF/) is an incredibly fast and efficient library for extracting text from PDFs, making it suitable for limited resources.
* **Data Handling:** `requests` for API interactions, `io` and `base64` for audio data manipulation.

## Setup and Running Locally

To run this application on your local machine, follow these steps:

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <your-repository-name>
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    ```

3.  **Activate the Virtual Environment:**
    * **On Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
    * **On macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```

4.  **Install Dependencies:**
    The project relies on the following libraries. Ensure your `requirements.txt` file contains:
    ```
    streamlit
    requests
    yfinance
    PyMuPDF
    gTTS
    ```
    Then install them:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Run the Streamlit Application:**
    ```bash
    streamlit run main.py
    ```
    This will open the application in your default web browser.

## API Keys (Important Note)

For the purpose of quick development and demonstration, the AssemblyAI and FMP API keys are **hardcoded directly in `main.py`**.

**Security Warning:** In a production environment or when sharing your code publicly, it is highly recommended to use [Streamlit Secrets](https://docs.streamlit.io/deploy/streamlit-cloud/configure-your-app/secrets) or environment variables (`os.getenv()`) to manage API keys securely. If you fork this repository for your own use, please replace the embedded keys with your own or set up Streamlit Secrets.

## Deployment

This application can be easily deployed to [Streamlit Cloud](https://streamlit.io/cloud) by connecting your GitHub repository. Ensure your `requirements.txt` file is correctly set up.

## Usage Notes

* **Microphone Access:** The first time you use the voice feature, your browser will ask for permission to access your microphone. Please grant this permission.
* **FMP API Rate Limits:** The free tier of the Financial Modeling Prep API has strict rate limits. If you make too many requests quickly, you might encounter `429` (Too Many Requests) errors.

---
