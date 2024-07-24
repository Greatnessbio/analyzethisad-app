import streamlit as st
import pandas as pd
import requests
import json

# Authentication function
def authenticate(username, password):
    return (username == st.secrets["login_username"] and 
            password == st.secrets["login_password"])

# OpenRouter API call
def analyze_ad_copy(ad_copy):
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {st.secrets['openrouter_api_key']}",
        },
        json={
            "model": "anthropic/claude-3.5-sonnet",
            "messages": [
                {"role": "system", "content": "You are an expert in analyzing Google Ads copy for ELISA kits. Provide a detailed analysis based on the given criteria."},
                {"role": "user", "content": f"""Analyze the following Google Ads copy for ELISA kits:

{ad_copy}

Provide a comprehensive analysis including title analysis, snippet analysis, display URL analysis, ad extensions analysis, keyword relevance and density, call-to-action analysis, and overall ad strength evaluation. Your analysis should include:

1. Keyword extraction and analysis
2. Structure, length, and brand/product mentions
3. Sentiment analysis and emotional triggers
4. Power words and USPs identification
5. Value propositions
6. Entity recognition (products, brands, features)
7. Readability scoring
8. URL structure analysis
9. Ad extensions evaluation
10. Keyword density and long-tail keywords
11. Semantic relevance to ELISA kits
12. CTA strength and placement
13. Overall ad strength and potential Quality Score
14. 2-3 alternative headlines
15. Snippet improvement suggestions
16. Ad extension recommendations
17. Personalized ad copy recommendations

Format your response as a JSON object with keys for each analysis component."""}
            ]
        }
    )
    return response.json()['choices'][0]['message']['content']

def validate_columns(df):
    expected_columns = ['title', 'snippet', 'displayed_link', 'rich_snippet.top.extensions']
    missing_columns = [col for col in expected_columns if col not in df.columns]
    return missing_columns

# Main application
def main():
    st.title("Google Ads ELISA Kit Analysis System")

    # Initialize session state for login
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    # Login form
    if not st.session_state.logged_in:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
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
                st.info("Please ensure your CSV file has the following columns: title, snippet, displayed_link, rich_snippet.top.extensions")
                return

            if st.button("Analyze Ads"):
                results = []
                for _, row in df.iterrows():
                    try:
                        ad_copy = f"""Title: {row['title']}
Snippet: {row['snippet']}
Display URL: {row['displayed_link']}
Extensions: {row['rich_snippet.top.extensions']}"""
                        analysis = analyze_ad_copy(ad_copy)
                        analysis_dict = json.loads(analysis)
                        results.append(analysis_dict)
                    except KeyError as e:
                        st.error(f"Error processing row: {e}")
                        continue

                if results:
                    results_df = pd.DataFrame(results)
                    st.write("Analysis Results:")
                    st.write(results_df)

                    # Option to download results as CSV
                    csv = results_df.to_csv(index=False)
                    st.download_button(
                        label="Download results as CSV",
                        data=csv,
                        file_name="ad_analysis_results.csv",
                        mime="text/csv",
                    )
                else:
                    st.warning("No results were generated. Please check your CSV file and try again.")

        except Exception as e:
            st.error(f"An error occurred while processing the file: {str(e)}")

    # Logout button
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.experimental_rerun()

if __name__ == "__main__":
    main()
