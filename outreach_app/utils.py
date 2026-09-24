from pytrials.client import ClinicalTrials
import pandas as pd
import requests
from collections import defaultdict
from json_repair import repair_json
from bs4 import BeautifulSoup
import json 
import openai
from openai import AzureOpenAI
import re 
from outreach_app.constant import const
import os 
import threading
import neverbounce_sdk
from dotenv import load_dotenv, find_dotenv 
_ = load_dotenv(find_dotenv())

openai.api_type = const.OPENAI_API_TYPE
openai.api_base = const.OPENAI_API_ENDPOINT
openai.api_version = const.OPENAI_API_VERSION
openai.api_key = os.environ['OPENAI_KEY']

class Utils:
    def __init__(self) -> None:
        pass

    def make_gpt_call(self,system, temp, prompt, engine="castor-gpt-4", max_tokens=1000 ):

        # gets the API Key from environment variable AZURE_OPENAI_API_KEY
        client = AzureOpenAI(
            api_key=openai.api_key,
            api_version=openai.api_version,
            azure_endpoint=openai.api_base ,
        )

        response = client.chat.completions.create(
            model=engine,
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt }
                ],
            temperature=temp,
            max_tokens = max_tokens )

        return response.choices[0].message.content
    
    def create_regex(self,titles):
        prefix_dict = defaultdict(list)

        # Group titles by their first word
        for title in titles:
            first_word, rest = title.split(' ', 1)
            prefix_dict[first_word].append(rest)

        patterns = []
        for prefix, suffixes in prefix_dict.items():
            if suffixes:
                patterns.append(prefix + '\\s(' + '|'.join(suffixes) + ')')
            else:
                patterns.append(prefix)

        return '|'.join(patterns)

    def is_valid_email(self,email:str)->bool:
        '''This method will check if the email is valid or not by 
            hitting sending the email to "NeverBounce" a service offered by 
            ZoomInfo
            args:
                email: email you want to validate
            returns:
                if the email is valid then returns TRUE else FALSE
        '''
        is_valid = False
        api_key = os.environ["NEVER_BOUNCE_KEY"]
        if email: 
            client = neverbounce_sdk.client(api_key=api_key,timeout=30)
            resp = client.single_check(email)
            if resp["result"] == "valid":
                is_valid=True
            
        return is_valid


    def find_trials(self,companyName, timeout_seconds=60):
        def target_function():
            nonlocal trial_data
            ct = ClinicalTrials()
            trial_data = ct.get_study_fields(
                search_expr=companyName,
                fields=["LeadSponsorName", "Condition", "Phase", "StartDate", "BriefSummary"],
                max_studies=500,
            )

        trial_data = None
        thread = threading.Thread(target=target_function)
        thread.start()
        thread.join(timeout=timeout_seconds)
        if thread.is_alive():
            print("Request timed out")
            return pd.DataFrame({"trial":"not found"}), 0  # Return an empty DataFrame and 0 trials as a timeout response
        else:
            # Process the trial_data as before
            header = trial_data[0]
            rows = trial_data[1:]
            df = pd.DataFrame(rows, columns=header)
            df['StartDate'] = pd.to_datetime(df['StartDate'], errors='coerce')
            df = df.sort_values(by='StartDate', ascending=False)
            if len(df) > 10:
                df = df[df['LeadSponsorName'].str.contains(companyName, case=False, na=False)]
            return df.drop(columns=['LeadSponsorName', 'Rank']).head(5), len(df)


    def gpt_json_request(self,system, temp, prompt, engine="castor-gpt-4" ):
        reply_content =  self.make_gpt_call(system,temp,prompt,engine)
        cleaned_json = repair_json(reply_content)
        if cleaned_json != '':
            cleaned_content = cleaned_json
        else:
            cleaned_content = None
        try:
            json_object = json.loads(cleaned_content)
        except Exception as e:
            print(f"An error occurred while processing the GPT response: {e}")
            print(f"********** clean content ******************\n{cleaned_content}")
            return {}
        return json_object


    def google_search(self,search_term, num=1):
        service_url = const.GOOGLE_SEARCH_ENPOINT
        params = {
            'q': search_term,
            'key': os.environ['SEARCH_KEY'],
            'cx':os.environ['SEARCH_CX'],
        }
        params.update(num=num)
        response = requests.get(service_url, params=params)

        return response.json()

    def truncate_text(self,text, max_chars=4000):
        if not isinstance(max_chars, int):
            return text

        if not isinstance(text, str):
            return text

        if len(text) > max_chars:
            return text[:max_chars]
        else:
            return text

    def ensure_https(self,url):
        if not isinstance(url, str):
            return None

        if not url.startswith('http'):
            url = 'https://' + url
        return url

    def remove_whitespace(self,text):
        return ' '.join(text.split())

    def get_website(self,url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        else:
            print(f'Request failed with status code {response.status_code}.')

    def extract_page_content(self,url, keywords):
        try:
            response = self.get_website(url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            return None

        soup = BeautifulSoup(response.content, "html.parser")

        for keyword in keywords:
            link = soup.find("a", href=re.compile(f".*{keyword}.*", re.IGNORECASE))
            if link:
                try:
                    subpage_url = self.urljoin(url, link['href'])  # Add this line
                    subpage_response = requests.get(self.ensure_https(subpage_url))  # Update this line

                    subpage_response.raise_for_status()
                    subpage_soup = BeautifulSoup(subpage_response.content, "html.parser")
                    return self.remove_whitespace(subpage_soup.get_text())
                except requests.exceptions.RequestException as e:
                    print(f"Error: {e}")
                    continue

        return self.remove_whitespace(soup.get_text())

    def extract_json_string(self,s):
        start_index = s.find('{')
        end_index = s.rfind('}') + 1 # Adding 1 to include the closing brace

        if start_index != -1 and end_index != -1 and start_index < end_index:
            return s[start_index:end_index]
        else:
            return None
        
    
    def clean_json_string(self,json_str):
        """Due to GPT granularity, sometimes newlines can be added outside of key and value fields that hinder JSON parsing. Remove any newlines outside of key and value fields."""

        # Remove \n, \\n, \n\n, \\n\\n right before "{"
        json_str = re.sub(r'(\s*\\n\s*|\s*\\n\\n\s*|\s*\n\s*|\s*\n\n\s*)({)', r'\2', json_str)

        # Remove \n, \\n, \n\n, \\n\\n right before or after "\"title\""
        json_str = re.sub(r'(\s*\\n\s*|\s*\\n\\n\s*|\s*\n\s*|\s*\n\n\s*)("title")', r'\2', json_str)
        json_str = re.sub(r'("title")(\s*\\n\s*|\s*\\n\\n\s*|\s*\n\s*|\s*\n\n\s*)', r'\1', json_str)

        # Remove \n, \\n, \n\n, \\n\\n right before the value of "title"
        json_str = re.sub(r'("title"\s*:\s*)(\s*\\n\s*|\s*\\n\\n\s*|\s*\n\s*|\s*\n\n\s*)(")', r'\1\3', json_str)

        # Remove \n, \\n, \n\n, \\n\\n right before or after "\"body\""
        json_str = re.sub(r'(\s*\\n\s*|\s*\\n\\n\s*|\s*\n\s*|\s*\n\n\s*)("body")', r'\2', json_str)
        json_str = re.sub(r'("body")(\s*\\n\s*|\s*\\n\\n\s*|\s*\n\s*|\s*\n\n\s*)', r'\1', json_str)

        # Remove \n, \\n, \n\n, \\n\\n right before the value of "body"
        json_str = re.sub(r'("body"\s*:\s*)(\s*\\n\s*|\s*\\n\\n\s*|\s*\n\s*|\s*\n\n\s*)(")', r'\1\3', json_str)

        # Remove \n, \\n, \n\n, \\n\\n right before "}"
        json_str = re.sub(r'(\s*\\n\s*|\s*\\n\\n\s*|\s*\n\s*|\s*\n\n\s*)}', r'}', json_str)

        # Remove \n, \\n, \n\n, \\n\\n right after "}"
        json_str = re.sub(r'(})(\s*\\n\s*|\s*\\n\\n\s*|\s*\n\s*|\s*\n\n\s*)', r'\1', json_str)

        return json_str
    
    #@title Check JSON string validity
    def is_valid_json(self,myjson):
        try:
            json_object = json.loads(myjson)
        except ValueError as e:
            return False
        return True