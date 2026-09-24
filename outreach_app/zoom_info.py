
import pandas as pd
import time 
import requests
import zi_api_auth_client
import json 
from outreach_app.constant import const
import os
from dotenv import load_dotenv, find_dotenv 
_ = load_dotenv(find_dotenv())

class ZoomInfo:
    def __init__(self) -> None:
        self.jwt_token = ""
        self.token_timestamp = 0

        self.switcher = {
        "sponsor_micro":const.SMALL_SPONSORS,
        "sponsor_small": const.SMALL_SPONSORS,
        "sponsor_medium": const.MEDIUM_SPONSORS,
        "sponsor_large": const.LARGE_SPONSORS,
        "cro_micro":const.SMALL_CROS,
        "cro_small": const.SMALL_CROS,
        "cro_medium": const.MEDIUM_CROS,
        "cro_large": const.LARGE_CROS
        }

    def return_jwt_token(self):
        jwt_token = self.jwt_token 
        token_timestamp= self.token_timestamp
        
        if (time.time() - token_timestamp > 50 * 60) or jwt_token == "":
            jwt_token = zi_api_auth_client.pki_authentication("tanya.docheva@castoredc.com", "605cb102-2222-4079-bb5a-9b27ee83df72", os.environ['ZOOM_INFO_KEY'].replace("\\n", "\n"))
            token_timestamp = time.time()

        return jwt_token
    
    def get_titles(self,category):
        return self.switcher.get(category, "Invalid category")

    def get_zoominfo_person(self,first_name, last_name, company_name,title):

        url = const.ZOOM_INFO_CONTACT_ENDPOINT
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.return_jwt_token()
        }


        data = {
            "firstName": first_name,
            "lastName": last_name,
            "companyName": company_name,
            "jobTitle": title,
            "rpp": 100
        }

        response = requests.post(url, headers=headers, data=json.dumps(data))
        response_json = json.loads(response.text)
        if 'data' in response_json:
            response_frame = pd.DataFrame(response_json['data'])
        else:
            print("Error in Zoominfo response")
        print(response.text)
        response_frame =  pd.DataFrame()
        return response_frame
  
    #No longer using this, we can't rely on Zoominfo for this intel. ************** Syed will ask
    def get_zoominfo(self,titles_to_look_for, company, max_titles):

        url = const.ZOOM_INFO_CONTACT_ENDPOINT
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.return_jwt_token()
        }

        titles = titles_to_look_for.split(' OR ')
        title_sets = []
        all_contacts = []

        # Initialize variables for the current subset of titles and its total length
        current_subset = []
        current_length = 0

        for title in titles:
            # Length of the title plus the length of the ' OR ' separator
            title_length = len(title) + 4  # Adding 4 for ' OR '

            # Check if adding the current title exceeds the max length
            if current_length + title_length > 500:
                # Join the current subset titles and add them to the list
                subset_titles = ' OR '.join(current_subset)
                title_sets.append(subset_titles)

                # Reset for the next subset
                current_subset = [title]
                current_length = len(title)
            else:
                # Add the title to the current subset and update the length
                current_subset.append(title)
                current_length += title_length

        # Add the last subset if it's not empty
        if current_subset:
            subset_titles = ' OR '.join(current_subset)
            title_sets.append(subset_titles)

        # Now, you can loop through all_contacts to process each subset_titles
        for subset_titles in title_sets:

            #print("Searching Zoominfo for" + subset_titles)
            data = {
                "jobTitle": subset_titles,
                "companyName": company,
                "rpp": 100
            }

            response = requests.post(url, headers=headers, data=json.dumps(data))
            response_json = json.loads(response.text)
            response_frame = pd.DataFrame(response_json['data'])
            all_contacts.append(response_frame)

            #stop when we have found enough good quality roles
            if(len(all_contacts) > max_titles-1):
                break

        return all_contacts
    

    def get_email_from_zi(self,first_name, last_name, company_name,title):
        person = self.get_zoominfo_person(first_name, last_name, company_name,"")
        if len(person) > 0:
            if len(person) > 1:
                person_refined = self.get_zoominfo_person(first_name, last_name, company_name,title)
            if len(person_refined) == 1:
                person = person_refined

            person_id = person.iloc[0]['id']
            details = self.get_zoominfo_details(str(person_id))
            email = details['data']['result'][0]['data'][0]['email']
            phone = details['data']['result'][0]['data'][0]['phone']
            return email,phone

        else:
            return False, False
        

    def get_zoominfo_details(self,personId):
        jwt_token = self.return_jwt_token()
        url_enrich = const.ZOOM_INFO_ENRICH_ENDPOINT
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer "+jwt_token  # replace YOUR_ACCESS_TOKEN with your actual token
            }
        data = {
            "matchPersonInput": [{
                "personId": personId
                }],
            "outputFields": [
                    "email",
                    "phone",
                    "externalurls"
                ]
        }


        response = requests.post(url_enrich, headers=headers, data=json.dumps(data))
        response_json = json.loads(response.text)
        return response_json