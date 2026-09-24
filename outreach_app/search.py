
import requests
import time 
from outreach_app.utils import Utils
from bs4 import BeautifulSoup
from outreach_app.zoom_info import ZoomInfo
from outreach_app.linkedin import linkedIn
from outreach_app.constant import const
import os
from outreach_app.timeout_decorator import timeout
from dotenv import load_dotenv, find_dotenv 
_ = load_dotenv(find_dotenv())
Utils_obj = Utils()
ZoomInfo_obj = ZoomInfo()
linkedIn_obj = linkedIn()

class Search:
    def __init__(self) -> None:
        pass

    def google_search(self,search_term, num=1):
        service_url = const.GOOGLE_SEARCH_ENPOINT
        params = {
            'q': search_term,
            'key': os.environ['SEARCH_KEY'],
            'cx':os.environ['SEARCH_CX'],
        }
        #TODO LOW PRIO: Run multiple searches if we need more than 10 results
        params.update(num=num)
        
        response = requests.get(service_url, params=params,timeout=60)

        return response.json()

    def google_search_for_roles(self,company, roles, max_roles_to_return ):
        #  lot of indentation issues here 
        top_contacts = []
        #Split all the roles in the list by OR
        terms = roles.split(" OR ")
        base_query = "site:linkedin.com/in/ \""+str(company)+"\" "
        #Go through each term
        for term in terms:
            if max_roles_to_return == 0:
                break
            foundRole = False
            term = term.strip()
            #Turn it into an exact match for Google
            exact_match_term = '+"' + term + '"'
            #if we surpass a certain query length, run it
            #2 reasons: 1) Google does not support more than 32 word searches, 2) We want to get the best roles in first

            full_query = base_query+" "+exact_match_term
            print("Running search for "+full_query)

            results = self.google_search(full_query,3)

            if 'items' in results:

                #extract all the linkedin profiles from this search, this be max 10, as Google Custom search only returns up to 10 in one go
                #TODO LOW PRIO: make sure we don't consistently lose out on good people because of this limit.
                linkedIn_data = [(item['link'], item['snippet']) for item in results['items']]

                #Check if these people still work at the company we are lookig for, if so, store their details
                for url, snippet in linkedIn_data:
                    print(snippet)
                    if term not in snippet:
                        print(term+ " was not found in "+ snippet)
                        continue
                    first_name, last_name, headline, summary, current_companies_and_titles = linkedIn_obj.get_linkedIn(url)

                    #See if a substring of company name exists in any of the current companies
                    matching_company_and_title = next(((li_company, li_title) for li_company, li_title in current_companies_and_titles if company.lower() in li_company.lower()), (None, None))

                    #Check if we found our company name in the list
                    if any(item is not None for item in matching_company_and_title):


                        company_name, associated_title = matching_company_and_title

                        print ("Is "+term+" in "+associated_title)
                        #check if the term and associated title match
                        if term.lower() in associated_title.lower() or associated_title.lower() in term.lower():

                            print("Found "+first_name+" "+last_name+" at "+company+" as "+associated_title)

                        email = ZoomInfo_obj.get_email_from_zi(first_name, last_name, company_name,associated_title)
                        contact = {
                            "first_name": first_name,
                            "last_name": last_name,
                            "company": company,
                            "title": associated_title,
                            "summary": summary,
                            "headline": headline,
                            "linkedin_url": url,
                            "email": email
                        }


                        top_contacts.append(contact)
                        max_roles_to_return = max_roles_to_return - 1
                        if max_roles_to_return == 0:
                            return top_contacts
                        foundRole = True
                        break
            else:
                print("Does not work at company anymore")
            if foundRole:
                continue


    
    def google_gpt_search(self,company, roles, max_roles_to_return,products_to_sell = "Modular Clinical Trial platform for all types of trials"):
        found_contacts = []
        found_names = ""
        terms = roles.split(" OR ")

        #Go through each role
        for role in terms:
            if max_roles_to_return == 0:
                break
            
            role = role.strip()
            result = self.google_search(f'site:linkedin.com/in/ "Experience" AROUND (7) "{company}" {role}',5)

            time.sleep(0.25)
            if 'items' in result:
                results = [(item['title'], item['snippet'], item['link']) for item in result['items']]
                gpt_eval_string =""
                for title, snippet,link in results:
                    gpt_eval_string = gpt_eval_string + " [Link= " +link
                    gpt_eval_string = gpt_eval_string + " ,Title= " +title
                    gpt_eval_string = gpt_eval_string + " ,Snippet=" + snippet + "]"
            else:
                continue
            gpt_result = {}
            prompt = f"""
            We are trying to find certain people who are CURRENTLY working in as a '{role}' at the following company: '{company}'.
            We want to reach out to these people to sell them Castor's eCLinical solutions, specifically '{products_to_sell}'
            You will decide who from a list of Google results is relevant for '{role}' and a good target to reach out to for selling Castor.
            You can ususally tell from direclty from the title, but it may not always be available so then make your best guess.
            FIRST select ONLY people who you think have a HIGH likelihood of being a match for both the role and selling Castor
            Only select contacts where you have a high degree of certainty.
            Include a short (max 10 words) reason for selecting the contact
            Also include the role / title if you can extract it from the given information.

            THEN RETURN a JSON Object with selected people and the reason for selecting.
            IF YOU CAN'T SELECT ANYONE, Return and empty JSON object e.g. {{"no results": [{{}}]}}

            Please ignore contacts that were already found, listed here: {found_names}

            OUTPUT EXMAMPLE:
            {{"contacts": [{{
                "name": "Karina Palafox",
                "role": "Short Role Title",
                "link": "LINKEDIN URL",
                "short_reason": "works in clin ops good fit for clinical operations"
            }}, etc]}}
            Here are the initial search results
            """ + gpt_eval_string
            time.sleep(0.25)
            #print(prompt)
            
            gpt_result = Utils_obj.gpt_json_request(prompt=prompt, system="You identify relevant contacts as BDR for selling Castor, return only JSON",temp=0.01, engine='castor-gpt-4')

            if 'contacts' in gpt_result and type(gpt_result)!=str:
                #DECREASE MAX ROLES HERE SO WE CAN GET MULTIPLE RESULTS FOR EACH SEARCH
                max_roles_to_return = max_roles_to_return - 1
                for contact in gpt_result['contacts']:
                    if(max_roles_to_return == 0):
                        break
                    name = contact['name']
                    link = contact['link']
                    role = contact['role']
                    reason = contact['short_reason']

                    #TODO Nov 17: have a fall back for when LI is NONE
                    first_name, last_name, headline, summary, current_companies_and_titles = linkedIn_obj.get_linkedIn(link)
                    if first_name is None:
                        continue
                    #print(f"Got LI, getting email from ZI")
                    email, phone = ZoomInfo_obj.get_email_from_zi(first_name,last_name,company,role)
                    contact = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "company": company,
                        "title": role,
                        "summary": summary ,
                        "headline": headline,
                        "linkedin_url": link,
                        "email": email,
                        "phone": phone,
                        "reason":reason,
                        "email_body": "",
                        "email_subject": ""
                    }
        
                    found_contacts.append(contact)
                    found_names = found_names + f"[{name}],"
                    #DON'T REDUCE MAX ROLES HERE BECAUSE WE ARE GOING TO ASK GPT TO SELECT THE BEST RESULTS
                    

        return(found_contacts)
    
    @timeout(300)
    def google_search_for_pipeline(self,website):
        full_query = "site:"+str(website)+" intitle:pipeline"
        results = self.google_search(full_query,1)

        if 'items' not in results:
            full_query = "site:"+str(website)+" intitle:R&D"
            results = self.google_search(full_query,1)

        if 'items' not in results:
            full_query = "site:"+str(website)+" pipeline"
            results = self.google_search(full_query,1)

        if 'items' not in results:
            full_query = "site:"+str(website)+" \"research\""
            results = self.google_search(full_query,1)

        if 'items' not in results:
            full_query = "site:"+str(website)+" \"publications\""
            results = self.google_search(full_query,1)

        if 'items' not in results:
            full_query = "site:"+str(website)+" \"science\""
            results = self.google_search(full_query,1)

        if 'items' in results:
            pipeline_data = [(item['link'], item['snippet']) for item in results['items']]
            
            #Don't need a loop because we only have one result, but OK
            soup = None
            for url, snippet in pipeline_data:
                if url:
                    html = Utils_obj.get_website(url)
                    if html:
                        soup = BeautifulSoup(html, 'html.parser')


            # Get the body
            if soup:
                body = soup.body
            else: 
                body= None

            if body is not None:
                text = body.get_text()
                body = ' '.join(text.split())
                body = Utils_obj.truncate_text(body, max_chars=25000)
            else:
                body = ""


            output = Utils_obj.gpt_json_request('You are a life sciences BDR that is looking to determine a biotech/pharma pipeline from a website. You MUST reply only in JSON, no comments.{"type": "text","content": "Pipeline information"}',
                        0.2,"""
                        Determine wether or not this HTML page lists a therapeutic pipeline for a biotech of pharma company in text, of if it is presented in an image.
                        If the pipeline is presented in text, list all the trials in the pipeline and return it in the content JSON variable content.
                        Do not summarize or paraphrase. You must return ONLY each trial you can find.


                        Here is the website information: ###START HTML###""" + str(body) + """###END HTML###

                        Return only valid json, that does not include
                        You MUST only return the pipeline itself, no additional commentary.

                        Example JSON for text based pipeline: {"type": "text", "content": "Pipeline information"}

                        Example JSON for image based pipeline: {"type": "image", "content": "https://website.com/path/to/image.png"}

                        """)

            if(output['type'] == "text"):
                return output['content']
            else:
                #TODO low prio: OCR THE IMAGE AND RETURN AS TEXT
                return "Pipeline as Image file, to be OCRed"
        else:
            return "Did not fine pipeline"


    def get_all_li_profiles(self,company, titles_to_look_for, max_num_roles):
        json_data = self.google_search_for_roles("site:https://linkedin.com/in/ "+str(company),titles_to_look_for,max_num_roles)
        linkedIn_urls = [item['link'] for item in json_data['items']]
        return set(linkedIn_urls)


    