import streamlit as st
import pandas as pd
import requests
import json
import time
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Authentication function
def authenticate(username, password):
    return (username == st.secrets["login_username"] and 
            password == st.secrets["login_password"])

# Function to check API rate limits
def check_rate_limits():
    response = requests.get(
        "https://openrouter.ai/api/v1/auth/key",
        headers={"Authorization": f"Bearer {st.secrets['openrouter_api_key']}"},
    )
    if response.status_code == 200:
        data = response.json()['data']
        return data['rate_limit']['requests'], data['rate_limit']['interval']
    else:
        st.error("Failed to check rate limits. Please try again later.")
        return None, None

# OpenRouter API call with retry logic and improved error handling
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def analyze_ad_copy(ad_copy):
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {st.secrets['openrouter_api_key']}",
                "HTTP-Referer": "https://your-app-url.com",  # Replace with your actual app URL
                "X-Title": "ELISA Kit Analysis App",  # Replace with your app's name
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "messages": [
                    {"role": "system", "content": "You are an expert in analyzing Google Ads copy for ELISA kits. Provide a detailed analysis based on the given criteria."},
                    {"role": "user", "content": f"""Analyze the following Google Ads copy for ELISA kits:

    {ad_copy}

    Provide a comprehensive analysis including title analysis, snippet analysis, display URL analysis, keyword relevance and density, call-to-action analysis, and overall ad strength evaluation. Your analysis should include:

    1. Keyword extraction and analysis
    2. Structure, length, and brand/product mentions
    3. Sentiment analysis and emotional triggers
    4. Power words and USPs identification
    5. Value propositions
    6. Entity recognition (products, brands, features)
    7. Readability scoring
    8. URL structure analysis
    9. Keyword density and long-tail keywords
    10. Semantic relevance to ELISA kits
    11. CTA strength and placement
    12. Overall ad strength and potential Quality Score
    13. 2-3 alternative headlines
    14. Snippet improvement suggestions
    15. Personalized ad copy recommendations

    Format your response as a JSON object with keys for each analysis component."""}
                ]
            }
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        
        # Try to parse the content as JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # If parsing fails, return the raw content
            return {"error": "Failed to parse API response as JSON", "raw_content": content}
    
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {str(e)}")
        return {"error": f"API request failed: {str(e)}"}

def validate_columns(df):
    expected_columns = ['title', 'snippet', 'displayed_link']
    missing_columns = [col for col in expected_columns if col not in df.columns]
    return missing_columns

# Main application
def main():
    st.title("Google Ads ELISA Kit Analysis System")

    # Initialize session state for login and results
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'results' not in st.session_state:
        st.session_state.results = None

    # Login form
    if not st.session_state.logged_in:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                if authenticate(username, password):
                    st.session_state.logged_in = True
                    st.experimental_rerun()
                else:
                    st.error("Invalid username or password")
        return

    # Main application (only accessible after login)
    uploaded_file = st.file_uploader("Upload your CSV file", type="csv")
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.write("Uploaded CSV file:")
            st.write(df)

            # Validate columns
            missing_columns = validate_columns(df)
            if missing_columns:
                st.error(f"The following required columns are missing from your CSV: {', '.join(missing_columns)}")
                st.info("Please ensure your CSV file has the following columns: title, snippet, displayed_link")
                return

            if st.button("Analyze Ads"):
                # Check rate limits
                rate_limit, interval = check_rate_limits()
                if rate_limit is None:
                    return

                with st.spinner("Analyzing ads... This may take a few minutes."):
                    results = []
                    for index, row in df.iterrows():
                        try:
                            ad_copy = f"""Title: {row['title']}
Snippet: {row['snippet']}
Display URL: {row['displayed_link']}"""
                            analysis = analyze_ad_copy(ad_copy)
                            
                            # Check if the analysis contains an error
                            if "error" in analysis:
                                st.error(f"Error processing row {index}: {analysis['error']}")
                                if "raw_content" in analysis:
                                    st.text(f"Raw API response: {analysis['raw_content']}")
                                continue
                            
                            results.append(analysis)
                            
                            # Respect rate limits
                            if (index + 1) % rate_limit == 0:
                                st.info(f"Pausing for rate limit. Resuming in {interval} seconds...")
                                time.sleep(int(interval[:-1]))  # Remove 's' from interval string
                        except Exception as e:
                            st.error(f"Error processing row {index}: {str(e)}")
                            continue

                    if results:
                        st.session_state.results = pd.DataFrame(results)
                        st.success("Analysis complete!")
                    else:
                        st.warning("No results were generated. Please check your CSV file and try again.")

            # Display results if they exist in session state
            if st.session_state.results is not None:
                st.subheader("Analysis Results:")
                st.write(st.session_state.results)

                # Option to download results as CSV
                csv = st.session_state.results.to_csv(index=False)
                st.download_button(
                    label="Download results as CSV",
                    data=csv,
                    file_name="ad_analysis_results.csv",
                    mime="text/csv",
                )

        except Exception as e:
            st.error(f"An error occurred while processing the file: {str(e)}")

    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.results = None
        st.experimental_rerun()

if __name__ == "__main__":
    main()
