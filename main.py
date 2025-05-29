import streamlit as st
import requests
import time
import yfinance as yf
import pyttsx3

st.set_page_config(page_title="Finance Voice Assistant")
st.title("🎙️ Voice Finance Assistant")

# 🔑 Your AssemblyAI API Key
API_KEY = "a5c865ecb6cd4152ad9c91564a753cd2"
headers = {"authorization": API_KEY}

# Initialize the TTS engine
engine = pyttsx3.init()

# Upload audio file
audio_file = st.file_uploader("Upload an MP3 file", type=["mp3"])

# Function to fetch stock summary
def get_stock_summary(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        return {
            "name": info.get("longName", "N/A"),
            "price": info.get("currentPrice", "N/A"),
            "open": info.get("open", "N/A"),
            "high": info.get("dayHigh", "N/A"),
            "low": info.get("dayLow", "N/A"),
            "marketCap": info.get("marketCap", "N/A"),
            "summary": info.get("longBusinessSummary", "N/A")
        }
    except Exception as e:
        return {"error": str(e)}

# Function to search for stock tickers by keyword
def search_stock_tickers(keyword):
    try:
        tickers = yf.Tickers(keyword)
        if tickers.tickers:
            # Return the first ticker found - we can refine this later
            first_ticker = list(tickers.tickers.keys())[0]
            return first_ticker
        else:
            return None
    except Exception as e:
        print(f"Error searching tickers for '{keyword}': {e}")
        return None

# Function to speak text
def speak(text):
    engine.say(text)
    engine.runAndWait()

# Main logic
if audio_file and st.button("Transcribe & Fetch Stock"):
    with st.spinner("Uploading audio..."):
        upload_res = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers=headers,
            files={"file": audio_file}
        )
        if upload_res.status_code != 200:
            st.error("❌ Upload failed.")
            st.write(upload_res.text)
        else:
            audio_url = upload_res.json()["upload_url"]

            with st.spinner("Sending transcription request..."):
                json_data = {"audio_url": audio_url}
                transcript_res = requests.post(
                    "https://api.assemblyai.com/v2/transcript",
                    json=json_data,
                    headers=headers
                )

                if transcript_res.status_code != 200:
                    st.error("❌ Transcription request failed.")
                    st.write(transcript_res.text)
                else:
                    transcript_id = transcript_res.json()["id"]

                    with st.spinner("Transcribing..."):
                        status = "queued"
                        while status not in ["completed", "error"]:
                            polling_res = requests.get(
                                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                                headers=headers
                            )
                            status = polling_res.json()["status"]
                            time.sleep(3)

                        if status == "completed":
                            transcribed_text = polling_res.json()["text"]
                            st.success("✅ Transcription Complete:")
                            st.write(transcribed_text)
                            speak(f"Transcription complete. You said: {transcribed_text}")

                            # Attempt to find stock symbol by searching keywords
                            keywords = transcribed_text.split()
                            found_symbol = None
                            for keyword in keywords:
                                symbol = search_stock_tickers(keyword)
                                if symbol:
                                    found_symbol = symbol
                                    break  # Stop at the first found symbol for now

                            if found_symbol:
                                st.info(f"🔎 Found stock symbol: {found_symbol}")
                                data = get_stock_summary(found_symbol)

                                if "error" in data:
                                    st.error("❌ Couldn't fetch stock data for {found_symbol}.")
                                    st.write(data["error"])
                                    speak(f"Could not fetch stock data for {found_symbol}.")
                                else:
                                    st.write(f"📊 {data['name']}")
                                    speak(data['name'])
                                    st.write(f"💰 Current Price: ${data['price']}")
                                    speak(f"Current price is ${data['price']}")
                                    st.write(f"📈 Open: ${data['open']}, High: ${data['high']}, Low: ${data['low']}")
                                    speak(f"Opened at ${data['open']}, reached a high of ${data['high']}, and a low of ${data['low']}")
                                    st.write(f"🏢 Market Cap: {data['marketCap']}")
                                    speak(f"Market capitalization is {data['marketCap']}")
                                    st.markdown(f"📝 {data['summary']}")
                                    speak("Here's a brief summary: " + data['summary'])
                            else:
                                st.warning("⚠️ No stock symbol found in your voice.")
                                speak("No stock symbol found in your voice.")
                        else:
                            st.error("❌ Transcription failed.")
                            st.write(polling_res.json())
                            speak("Transcription failed.")
