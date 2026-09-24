import json 
import requests
import pandas as pd
from datetime import datetime, timedelta
from outreach_app.utils import Utils
from outreach_app.zoom_info import ZoomInfo
from outreach_app.constant import const
import os
from dotenv import load_dotenv, find_dotenv 
_ = load_dotenv(find_dotenv())

ZoomInfo_obj = ZoomInfo()
Utils_obj = Utils()

class linkedIn:

    def __init__(self) -> None:
        self.nubela_api_key = os.environ['NUBELA_API_KEY']
        self.api_endpoint = const.LINKEDIN_ENDPOINT

    def extract_li_information(self,profile_data):

        if(profile_data.get("summary")) is not None:
            summary = profile_data.get("summary")[:75]   #IMPLEMENT BROADLY
        else:
            summary = ""

        if(profile_data.get("headline")) is not None:
            headline = profile_data.get("headline")[:75] #IMPLEMENT BROADLY
        else:
            headline = ""


        first_name = profile_data.get('first_name')
        last_name = profile_data.get('last_name')
        headline = headline
        summary = summary
        experiences = profile_data.get('experiences', [])
        current_companies_and_titles = [(experience['company'], experience['title']) for experience in experiences if experience.get('ends_at') is None]

        return first_name, last_name, headline, summary, current_companies_and_titles

    def get_linkedIn(self,url):
        
        api_key = self.nubela_api_key
        header_dic = {'Authorization': 'Bearer ' + api_key}
        params = {
            'linkedin_profile_url': url,
            'fallback_to_cache': 'never',
            'use_cache': 'if-present'
        }
        response = requests.get(self.api_endpoint,
                                params=params,
                                headers=header_dic)

        return self.extract_li_information(json.loads(response.content))
    
    def get_person_li(self,first_name, last_name, company):
        #UPDATED ON 15 NOV 2023
        #function now updated to find the URL on Google

        result = Utils_obj.google_search(f'site:linkedin.com/in/ "{company}" "{first_name} {last_name}"',1)  # call from a google search class 
        
        if 'items' in result:
            results = [(item['title'], item['snippet'], item['link']) for item in result['items']]
            for title, snippet,link in results:
                return link
        else:
            return ""
        
    def get_company(self,url):
        api_endpoint = const.LINKEDIN_COMPANY_ENDPOINT
        api_key = self.nubela_api_key
        header_dic = {'Authorization': 'Bearer ' + api_key}
        params = {
            'url': str(url),
            'resolve_numeric_id': 'false',
            'categories': 'exclude',
            'funding_data': 'exclude',
            'extra': 'exclude',
            'exit_data': 'exclude',
            'acquisitions': 'exclude',
            'use_cache': 'if-recent',
        }
        response = requests.get(api_endpoint,
                                params=params,
                                headers=header_dic)
        return self.extract_com_information(json.loads(response.content))

    def direct_li_search(self,titles_to_look_for, company, max_roles_to_return):
        titles_to_look_for = titles_to_look_for.replace('\n', ' ')
        titles = titles_to_look_for.split(' OR ')
        api_endpoint = const.LINKEDIN_ROLE_ENDPOINT
        api_key = self.nubela_api_key
        header_dic = {'Authorization': 'Bearer ' + api_key}
        found_profiles = []
        for role in titles:
                params = {
                    'company_name': company,
                    'role': '"'+role+'"',
                    'enrich_profile': 'no'
                }
                print("Searching LinkedIn directly for "+ role)
                response = requests.get(api_endpoint,
                                params=params,
                                headers=header_dic)
                print(response.content)
                parsed_data = json.loads(response.content)
                linkedin_url = parsed_data["linkedin_profile_url"]

                if linkedin_url is not None:
                    parsed_data = self.get_linkedIn(linkedin_url)
                    print(parsed_data)
                    first_name, last_name, headline, summary, current_companies_and_titles = self.extract_li_information(parsed_data['profile'])

                    #See if a substring of company name exists in any of the current companies

                    current_companies_and_titles_string = ', '.join([f'{company} - {title}' for company, title in current_companies_and_titles])

                    matching_company_and_title = company.lower() in current_companies_and_titles_string.lower()


                    #Check if we found our company name in the list
                    if matching_company_and_title:
                        email = ZoomInfo_obj.get_email_from_zi(first_name,last_name,company,role)
                        contact = {
                            "first_name": first_name,
                            "last_name": last_name,
                            "company": company,
                            "title": role,
                            "summary": summary,
                            "headline": headline,
                            "linkedin_url": linkedin_url,
                            "email": email
                        }

                    if not any(existing_contact["linkedin_url"] == linkedin_url for existing_contact in found_profiles):
                        found_profiles.append(contact)
                        max_roles_to_return = max_roles_to_return - 1

                    if max_roles_to_return == 0:
                        break

        return found_profiles
    

    def direct_li_search_bulk(self,titles_to_look_for, company_url, max_titles = 5):
        titles_to_look_for = titles_to_look_for.replace('\n', ' ')

        titles = titles_to_look_for.split(' OR ')

        final_response_frame = pd.DataFrame()
        api_endpoint = const.NUBELA_EMPLOYEE_SEARCH
        api_key = self.nubela_api_key
        header_dic = {'Authorization': 'Bearer ' + api_key}

        regex =  Utils_obj.create_regex(titles_to_look_for)
        params = {
            'linkedin_company_profile_url': company_url,
            'keyword_regex':regex,
            'use_cache': 'if-recent'
        }

        #Just get all the employees in 1 run because you pay 10 credits for each run!
        response = requests.get(api_endpoint,
                                params=params,
                                headers=header_dic) # why is this not used ?

        return final_response_frame # why did you return a empty dataframe ?
    


    def get_credits(self):
        api_endpoint = const.NUBELA_CREDITS_ENDPOINT
        api_key = self.nubela_api_key
        header_dic = {'Authorization': 'Bearer ' + api_key}
        response = requests.get(api_endpoint,
                                headers=header_dic)
        result = json.loads(response.content)
        return result['credit_balance']


    def extract_com_information(self,company_data):
        company_size = company_size = company_data.get('company_size_on_linkedin', '10')
        recent_updates = []
        two_months_ago = datetime.now() - timedelta(days=60)
        if 'updates' in company_data:
            for update in company_data['updates']:
                posted_on = update.get('posted_on')
                if posted_on:
                    post_date = datetime(posted_on['year'], posted_on['month'], posted_on['day'])
                    if post_date >= two_months_ago:
                        recent_updates.append(update)
                        if len(recent_updates) == 3:
                            break

        return company_size, recent_updates[:3]