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

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def analyze_ad(ad_copy, search_term):
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {st.secrets['openrouter_api_key']}",
                "HTTP-Referer": "https://your-app-url.com",  # Replace with your actual app URL
                "X-Title": "Ad Copy Analysis App",  # Replace with your app's name
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "messages": [
                    {"role": "system", "content": "You are an expert in analyzing Google Ads copy. Provide concise, objective analyses based on the given criteria."},
                    {"role": "user", "content": f"""Analyze this Google Ad for {search_term} products:

Title: {ad_copy['title']}
Snippet: {ad_copy['snippet']}
Display URL: {ad_copy['displayed_link']}

Provide a comprehensive analysis including:
1. Title analysis (effectiveness, keywords, suggestions)
2. Snippet analysis (informativeness, keywords, suggestions)
3. URL analysis (structure, brand presence, relevance)
4. Overall ad strength (strengths, weaknesses, effectiveness, suggestions)

Format your response as a JSON object with keys for each analysis component."""}
                ]
            }
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Failed to parse API response as JSON"}
    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {str(e)}"}

def validate_columns(df):
    expected_columns = ['title', 'snippet', 'displayed_link']
    missing_columns = [col for col in expected_columns if col not in df.columns]
    return missing_columns

def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, ', '.join(map(str, v))))
        else:
            items.append((new_key, str(v)))
    return dict(items)

# Main application
def main():
    st.title("Google Ads Analysis System")

    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'results' not in st.session_state:
        st.session_state.results = None
    if 'progress' not in st.session_state:
        st.session_state.progress = 0
    if 'total_ads' not in st.session_state:
        st.session_state.total_ads = 0

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
    
    # Add input for search term
    search_term = st.text_input("Enter the search term you used to generate this data:", "")
    
    if uploaded_file is not None and search_term:
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

            st.info(f"Analysis will be performed for the search term: {search_term}")

            if st.button("Analyze Ads"):
                # Check rate limits
                rate_limit, interval = check_rate_limits()
                if rate_limit is None:
                    return

                # Reset progress
                st.session_state.progress = 0
                st.session_state.total_ads = len(df)

                progress_bar = st.progress(0)
                status_text = st.empty()

                results = []
                for index, row in df.iterrows():
                    ad_copy = {
                        'title': row['title'],
                        'snippet': row['snippet'],
                        'displayed_link': row['displayed_link']
                    }
                    analysis = analyze_ad(ad_copy, search_term)
                    
                    # Combine original ad data with analysis
                    result = {**ad_copy, **analysis}
                    results.append(result)

                    # Update progress
                    st.session_state.progress += 1
                    progress = st.session_state.progress / st.session_state.total_ads
                    progress_bar.progress(progress)
                    status_text.text(f"Analyzed {st.session_state.progress} out of {st.session_state.total_ads} ads")

                    # Respect rate limits
                    if (index + 1) % rate_limit == 0 and index < len(df) - 1:
                        time.sleep(int(interval[:-1]))  # Remove 's' from interval string

                if results:
                    # Flatten and normalize results
                    flattened_results = [flatten_dict(result) for result in results]
                    
                    # Get all unique keys
                    all_keys = set().union(*flattened_results)
                    
                    # Normalize the dictionaries
                    normalized_results = []
                    for result in flattened_results:
                        normalized_result = {key: result.get(key, 'N/A') for key in all_keys}
                        normalized_results.append(normalized_result)
                    
                    # Create DataFrame
                    results_df = pd.DataFrame(normalized_results)
                    
                    st.session_state.results = results_df
                    st.success(f"Analysis complete! Successfully analyzed {len(results)} out of {len(df)} ads.")
                else:
                    st.warning("No results were generated. Please check your CSV file and try again.")

                # Clear progress bar and status text
                progress_bar.empty()
                status_text.empty()

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

    elif uploaded_file is not None and not search_term:
        st.warning("Please enter the search term you used to generate this data.")
    elif search_term and not uploaded_file:
        st.warning("Please upload a CSV file to analyze.")

    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.results = None
        st.session_state.progress = 0
        st.session_state.total_ads = 0
        st.experimental_rerun()

if __name__ == "__main__":
    main()
