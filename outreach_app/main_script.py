import pandas as pd
import json

from collections import defaultdict
import gspread
from IPython.display import HTML, display
from datetime import datetime
from outreach_app.search import Search
from outreach_app.utils import Utils
from outreach_app.linkedin import linkedIn
from outreach_app.zoom_info import ZoomInfo
import numpy as np
import traceback
from oauth2client.service_account import ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
import threading
import itertools
from outreach_app.constant import const
from google.oauth2.credentials import Credentials
import os
import time 
from outreach_app.salesforce import *
# from outreach_app.views import sf


total_output = ""
Utils_obj = Utils()
linkedIn_obj = linkedIn()
ZoomInfo_obj = ZoomInfo()
Search_obj = Search()
sf = initialize_salesforce()



def ph(output):
  global total_output
  total_output = total_output + str(output)
  print(output)



#@title Generate the outbound message function
def create_outbound(prompt, system, contact, company_info, retry = 0, temp = 0.5):

  #ask for user input
  def handle_none(value):
    try:
        return str(value) if value is not None else ''
    except:
        return ''

  trials_for_prompt = company_info["trials"].to_json(orient='records') if not company_info["trials"].empty else ''

  # Conditional addition of trials information
  trials_info = f"Top 5 recently conducted trials: {json.dumps(trials_for_prompt)}" if trials_for_prompt != '' else ""
  

  # Get today's date
  current_date = datetime.now()

  # Convert to string
  current_date_str = current_date.strftime("%d %b %Y")

  #IMPLEMENT BROADLY
  prompt = prompt+"""
  Here is the information about the company and the person we are trying to target. The goal is to get a response from them.
  Today's date = """+current_date_str+""" (use this to asses how recent events are)

  ##COMPANY INFORMATION:
  target company name: """+handle_none(company_info["name"])+"""
  description of target company: """+handle_none(company_info["description"])+"""
  company headcount: """+handle_none(company_info["size"])+"""
  funding: """ + handle_none(company_info["funding"]) + """
  Total number of trials: """+handle_none(company_info["number_of_trials"])+"""
  industry of the target company: """+handle_none(company_info["industry"])+"""
  Therapeutic Areas: """+handle_none(company_info["therapeutic_areas"])+"""
  Future trials (pipeline): """+handle_none(company_info["pipeline"] )+"""
  """ + trials_info + """

  ##CONTACT INFORMATION:
  contact at the company (including role): """+str(contact)+"""

  Return only a valid JSON string with two key-value pairs: one for the email subject and one for the body of the outbound message. Always use 'title' and 'body' as keys.
  Do NOT include any greetings, closing or signature at the end.
  Always separate sentence
  Split each paragraph with: #split_paragraph#
  For example:{"title":"Email SUBJECT","body":"{{Recipient.FirstName}}#split_paragraph#This is paragraph 1\n#split_paragraph#this is paragraph 2#This is paragraph 3#split_paragraph#"}
  Return only a valid JSON string, escape control characters like \\ and \\n for new lines. Don't insert newlines in your return anywhere outside of the message body.

  """
  return_json = Utils_obj.make_gpt_call(system=system, prompt=prompt, temp=temp)

  return return_json

#Find all company info

def find_company_info(company_name:str,is_description:bool = True,is_company_web:bool= True,is_classify:bool= True,is_linkedIn:bool= True,is_funding:bool=True,is_company_size:bool=True,is_trials:bool=True,is_pipeline:bool=True)-> dict:
  '''
  This function finds info regarding company name that is provided, like its description, website,type,linkedIn details etc
  args:
    - company_name : name of the company to process
    - is_description: to get the description of the company from linkedIn,etc
    - is_company_web : get the company website url and their pipeline
    - is_classify : to classify the type of company (small,medium,large,etc)
    - is_linkedIn : to get company linkedIn related details
    - is_funcding : to get funding detail of the company 
    - is_company_size : get the size of the company in terms of the number of employees
    - is_trial : to get clinical trials from National clinical trial database, get thraputic trials,etc
    - is_pipeline: will find the pipeline from the company website, for this to activate you need to keep is_company_web flag to TRUE
  returns:
    - a dictionary containing all the info of the company where the flags was turn on. 
  '''
  company_info = {}
  company_info["name"] = str(company_name)

  ph("<h3>"+"Starting sleuthing for: " +str(company_name)+"</h3>")
  ph("<ul>")

  # get description of company
  if is_description:
    company_description_json = Search_obj.google_search("what does \"" + str(company_name) + "\" do? -site:linkedin.com -facebook.com", 1)
    company_snip = company_description_json.get("items",[{"snippet":"not found"}])[0].get("snippet")

    company_info["description"] = company_snip

    ph("<li>"+"Company snippet: "+str(company_snip)+"</li>")

    #classify the company
    chat_output = Utils_obj.gpt_json_request('You are a life sciences web researcher. Return only JSON, eg. {"type": "company_type"}',0.3, """
                      Company description: """+str(company_snip)+"""
                      Make a best guess as to what type of company this is. Choose from: "Academic" (including Hospitals), "Research site", "Medical Device", "Digital Therapeutic", "Diagnostic", "Biotech", "Pharmaceutical company" or "eClinincal Vendor".

                      Return only JSON.
                      Return in this format: {"type": "company_type"}
                      """)

    company_info["industry"] = chat_output.get("type")

  # get website url
  if is_company_web:
    try:
      company_info["website"] = company_description_json.get("items",[{"displaylink":"not found"}])[0].get("displayLink")
    except Exception as e:
      company_info["website"] = "Not found"
    
    ph("<li>"+"Website: " + str(company_info.get("website","Not found")) +"</li>")
    #Get pipeline information
    if "website" in company_info and company_info['website']!= "not found" and is_pipeline:
      try:
        company_info["pipeline"]  = (Search_obj.google_search_for_pipeline(company_info.get("website")))
        ph("<li>"+"Pipeline found: "+str(company_info.get("pipeline"))+"</li>")
      
      except Exception as e:
        print(f"Exception occured in pipeline code {e}")
        company_info["pipeline"] = "not found"
    else:
      company_info["pipeline"] = "not found"



  #get company linkedIn url
  if is_linkedIn: 
    try: 
      company_li_url_json = Search_obj.google_search("site:linkedin.com "+str(company_name), 1)
      company_info["li_url"] =  company_li_url_json.get("items",[{"link":"not found"}])[0].get("link")
    except Exception as e:
      company_info['li_url'] = "not found"

    ph("<li>"+"LinkedIn URL: "+str(company_info.get("li_url"))+"</li>")

  #get funding amount
  #TODO, this needs to be improved, it does not return the funding amount
  #TODO: We need this to return the amount and last raise
  def get_company_funding(company_name):
    company_funding = ""

    # First search query
    company_funding_json1 = Search_obj.google_search('site:crunchbase.com/organization/ inurl:company_financials +"'+str(company_name)+'"  +" has raised a total"', 1)
    company_funding += company_funding_json1.get("items",[{"snippet":"not found"}])[0].get("snippet")

    # Second search query
    company_funding_json2 = Search_obj.google_search('site:crunchbase.com/organization/ inurl:company_financials +"'+str(company_name)+'"  +" Their latest funding was raised "', 1)
    company_funding += company_funding_json2.get("items",[{"snippet":"not found"}])[0].get("snippet")
    return company_funding

  if is_funding:
    try:   
      company_funding = get_company_funding(company_name)
      company_info["funding"] = company_funding
    except Exception as e:
      company_info["funding"] = "not found"
    ph("<li>"+"Company funding: "+str(company_funding)+"</li>")
  
  #get company size from linkedin
  if is_company_size:
    company_size, recent_updates = linkedIn_obj.get_company(company_info.get("li_url"))
    company_info["size"] = company_size
    company_info["recent_updates"] = recent_updates
    ph("<li>"+"Company size: "+str(company_size)+"</li>")

  # get all trials
  if is_trials: 
    try:
      company_info["trials"], company_info["number_of_trials"] = Utils_obj.find_trials(company_name)
    except Exception as e:
      company_info["trials"], company_info["number_of_trials"]= "Not found","Not found" 
    ph("<li>Trials found: "+ str(company_info["number_of_trials"]) +"</li>")
    try:
      company_info["newest_trial"] =  company_info["trials"]['StartDate'].max()    
    except Exception as e:
      company_info["newest_trial"] =  "Not found"
    try :
      chat_output = Utils_obj.gpt_json_request('You are a life sciences web researcher. Return only JSON, e.g. {"therapeutic_areas": "list, of, therapeutic ares"}',0.5, """
                      Company description: """+str(company_info.get("description"))+"""
                      Last 5 conducted Trials: """+str(company_info.get("trials")) +"""
                      Make a best guess as to what Therapeutic Areas this company operates in. E.g. Oncology, Vaccine, etc.
                      return a comma seperate list of the top 3 Therapeutic areas.
                      Return only JSON.
                      Return in this format: {"therapeutic_areas": "list, of, therapeutic ares"}
                      """)
     
      company_info["therapeutic_areas"] = chat_output.get('therapeutic_areas',"not found")
    
    except Exception as e:
      company_info["therapeutic_areas"] = "Not found"

    ph("<li>"+"Industry: " + str(company_info["industry"])+"</li>")
    ph("<li>"+"TAs: " + str(company_info["therapeutic_areas"]) +"</li>")
  
  if is_classify:
    chat_output = Utils_obj.gpt_json_request('You are a life sciences web researcher. Return only JSON, eg. {"type": "sponsor_small"}',0.3,"""
                      <instructions>
                      Based on the information below, decide if this company is micro/small/medium/large and if it is a sponsor/cro/hostpital/eClincal vendor
                      Examples outputs would be sponsor_small, cro_large etc.
                      Think carefully, and consider the industry, size of the company and number of trials when deciding how to classify the company.
                      Below I have provided some examples, these are not exact, but should help you consider the ranges.
                      </instructions>

                      <examples>
                      - 2 person company with 1 trial: micro.
                      - 25 person company with 3-5 trials: small
                      - 500 person company with 10 trials: medium
                      - 4000 person company with 75 trials: large
                      </examples>

                      Company name: """+str(company_name)+"""
                      Company size: """+str(company_size)+"""
                      Number of trials: """+str(company_info.get("number_of_trials"))+"""
                      Company industry:"""+str(company_info.get("industry"))+"""

                      Return only JSON.
                      Return in this format: {"type": "sponsor_small"}
                      """)
    company_class = chat_output.get('type',"not found")
    company_info["company_class"] = company_class
    ph("<li>"+"Company classification: " + str(company_class)+"</li>")

  return company_info

#@title Extract contact inference info
def extract_contact_inference_info(contacts):
  """From found contacts (list of dictionaries), extract info needed to infer missing emails"""

  output_list = []

  # Group contacts by company
  company_contacts_known = defaultdict(list)
  company_contacts_unknown = defaultdict(list)

  for contact in contacts:
      email = contact.get('email', None)
      company = contact.get('company', 'Unknown')
      first_name = contact.get('first_name', 'Unknown')
      last_name = contact.get('last_name', 'Unknown')

      if email and email.lower() not in ['none', 'na', '', 'null']:
          company_contacts_known[company].append((first_name, last_name, email))
      else:
          company_contacts_unknown[company].append((first_name, last_name))

  # Store grouped contacts with known emails
  known_output = ""
  for company, contact_list in company_contacts_known.items():
      known_output += f"Company: {company}\n"
      for first_name, last_name, email in contact_list:
          known_output += f"{first_name} {last_name}: {email}\n"
  output_list.append(known_output)

  # Store grouped contacts with unknown emails
  unknown_output = ""
  for company, contact_list in company_contacts_unknown.items():
      unknown_output += f"Company: {company}\n"
      for first_name, last_name in contact_list:
          unknown_output += f"{first_name} {last_name}: \n"
  output_list.append(unknown_output)

  return output_list

#@title Infer email addresses
def infer_email_addresses(inference_info_list):
  prompt_system = """You will be asked to infer the email addresses of employees of a company. Your task is to analyze the patterns in the known email addresses to guess the email addresses for the employees in the unknown data set.
  Return ONLY your answer as a list of dictionaries in valid JSON-formatted strings, where each dictionary contains the first name, last name, and the inferred email address. If there is only one email to infer, a single dictionary is sufficient. Do not include any additional text or explanation in your output.

  For example, if you are inferring multiple emails:
  [
    {"first_name": "Adam", "last_name": "Ressler", "email": "a.ressler@company.com"},
    {"first_name": "Betty", "last_name": "Smith", "email": "b.smith@company.com"}
  ]

  Note: Your output will have to be used to convert valid JSON-formatted strings to Python objects. Escape control characters like \\ and \\n for new lines.
  """

  prompt_template = """Based on the provided Known Data and Unknown Data, please infer the email addresses for the employees with missing email information.

  ### Known Data
  {}

  ### Unknown Data
  {}

  Return ONLY your answer as a list of dictionaries in valid JSON-formatted strings. If there is only one email to infer, a single dictionary is sufficient. Do not include any additional text or explanation in your output.
  If there is no Known Data, or no Unknown Data to work with, return an empty string "".
  """
  prompt = prompt_template.format(inference_info_list[0], inference_info_list[1])

  return Utils_obj.make_gpt_call(system=prompt_system,prompt=prompt,temp=0.2)


#@title Update list of dictionaries with inferred emails
def update_contacts_with_inferred_emails(output_string, contacts):
    # Check if the output_string is a valid JSON
    if not Utils_obj.is_valid_json(output_string):
        print("No valid JSON format")
        return contacts

    # Parse the outputted string to a list of dictionaries
    inferred_emails = json.loads(output_string)

    # Loop through each dictionary in the inferred_emails list
    for inferred in inferred_emails:
        inferred_first_name = inferred.get("first_name", "")
        inferred_last_name = inferred.get("last_name", "")
        inferred_email = inferred.get("email", "")

        # Loop through each dictionary in the contacts list to find a match
        for contact in contacts:
            if (contact.get("first_name", "") == inferred_first_name and
                contact.get("last_name", "") == inferred_last_name):
                contact["email"] = inferred_email

    return contacts

#@title Supplement the missing emails in contacts
def supplement_emails_in_contacts(contacts):
    # Extract the information needed for inference
    inference_info_list = extract_contact_inference_info(contacts)

    # Infer the email addresses
    inferred_info = infer_email_addresses(inference_info_list=inference_info_list)

    # Update the contacts list with the inferred emails
    contacts_updated = update_contacts_with_inferred_emails(inferred_info, contacts)

    return contacts_updated

#@title Find all contacts with supplemented emails
def find_contacts_and_create_messages(company_info, system, prompt_email, max_titles=10,products_to_sell = "Modular Clinical Trial platform for all types of trials",validate_email=False):
    titles_to_look_for = ZoomInfo_obj.get_titles(company_info["company_class"])
    company_name = company_info["name"]
    contacts_found_on_zi = ZoomInfo_obj.get_zoominfo(titles_to_look_for, company_info["name"], max_titles)
    total_zi_rows = sum(df.shape[0] for df in contacts_found_on_zi)
    ph(company_info["name"])
    print(total_zi_rows)
    counter = 1

    found_contacts = []
    zi_names = set()
    # Step 1: Collect all contacts first
    if(total_zi_rows > 0):
      ph("<h4>"+"Contacts found on ZoomInfo!:"+"</h4>")
      for contact in contacts_found_on_zi:
        if counter > max_titles:
          ph("Counter > Max")
          break
        else:
          for index, row in contact.iterrows():
            if counter > max_titles:
              ph("<h4>"+"max_titles reached </h4>")
              break
            # get zoominfo provided linkedin url
            time.sleep(1)
            zoominfo_out = ZoomInfo_obj.get_zoominfo_details(row["id"])["data"]["result"][0]["data"][0]
            
            # TO DO FIND THIS PROFILE ON GOOGLE WITH SEARCH WHICH WILL BE WAY FASTER
            linkedin_url =  linkedIn_obj.get_person_li(row['firstName'], row['lastName'], company_info['name'])

            first_name, last_name, headline, summary, current_companies_and_titles = linkedIn_obj.get_linkedIn(linkedin_url)

            if validate_email:
              valid_email = Utils_obj.is_valid_email(zoominfo_out['email'])
              next_contact = {
                "first_name": row['firstName'],
                "last_name": row['lastName'],
                "company": company_name,
                "title": row['jobTitle'],
                "summary": summary,
                "headline": headline,
                "email": zoominfo_out["email"],
                "email Status":valid_email,
                "phone": zoominfo_out["phone"],
                "linkedin_url": linkedin_url,
                "email_body": "",
                "email_subject": ""
                }
            else:  
              next_contact = {
                  "first_name": row['firstName'],
                  "last_name": row['lastName'],
                  "company": company_name,
                  "title": row['jobTitle'],
                  "summary": summary,
                  "headline": headline,
                  "email": zoominfo_out["email"],
                  "phone": zoominfo_out["phone"],
                  "linkedin_url": linkedin_url,
                  "email_body": "",
                  "email_subject": ""
                  }
            ph("<h3>CONTACT #"+str(counter)+"</h3>")
            ph("<li>"+row['firstName']+" "+row['lastName']+ " "+row['jobTitle']+" "+next_contact['email']+"</li>")
            ph("<li>EMAIL: "+next_contact["email"]+"</li>")
            counter = counter+1
            found_contacts.append(next_contact)

            # Create a set of names from ZoomInfo for quick lookup
            for contact in found_contacts:
                zi_names.add((contact['first_name'].lower(), contact['last_name'].lower()))

      #end of zoominfo loop

    if 1 < max_titles:

        num_to_find = max_titles
        profiles = Search_obj.google_gpt_search(company_name,titles_to_look_for,num_to_find)
        if len(profiles) > 0:
          ph("<h4>"+"Contacts found on Linkedin!: </h4>")
          for contact in profiles:
  
            # Check if this LinkedIn contact is already in the ZoomInfo list
            if (contact['first_name'].lower(), contact['last_name'].lower()) in zi_names:
              ph("<li>{} {} already found with ZoomInfo. Skipping.</li>".format(contact['first_name'], contact['last_name']))
              continue  # Skip this iteration and move to the next contact

            next_contact = contact
            ph("<h3>CONTACT #"+str(counter)+"</h3>")
            ph("<li>"+next_contact['first_name']+" "+next_contact['last_name']+ " "+next_contact['title']+"</li>")

            counter = counter+1
            found_contacts.append(next_contact)

    # Step 2: Supplement missing emails
    for next_contact in found_contacts:
      if not next_contact.get("email"):  # Check if email is missing
          ph("<h3>Missing email for {} {}. Attempting to infer.</h3>".format(next_contact['first_name'], next_contact['last_name']))
          next_contact["email_inferred"] = False

    # Call the function to supplement emails
    found_contacts = supplement_emails_in_contacts(found_contacts)

    for next_contact in found_contacts:
      if next_contact.get("email") and not next_contact.get("email_inferred", True):  # Check if email was inferred
        ph("<li>Email inferred for {} {}: {}</li>".format(next_contact['first_name'], next_contact['last_name'], next_contact['email']))
        next_contact["email_inferred"] = True
      
      # check if email is valid
      if validate_email:
        valid_email = Utils_obj.is_valid_email(str(next_contact.get("email")))
        next_contact["email Status"] = valid_email

    selected_contacts = found_contacts

    #if we have more than the allowed total, let GPT choose
    if(len(found_contacts) > max_titles):
        selected_data = {i: {'title': contact.get('title', ''), 'headline': contact.get('headline', ''), 'email': contact.get('email', '')}
                    for i, contact in enumerate(found_contacts)}
        prompt = f"""
          We want to reach out to select the best roles to people to sell them Castor's eCLinical solutions, specifically '{products_to_sell}'
          This is a {company_info['industry']} with {company_info['size']} employees (take that into account)
          You will decide who from a list or titles and headlines who the most likely users and champions for Castor technology, the people who run or organize the trials and data management.
          Focus on the people that will be the decision maker, influencer, NOT the Economic Buyer perse (e.g. Data Management > Clin Ops > Procurement).
          FIRST select ONLY people who you think have a HIGH likelihood of being a match for both the role and selling Castor to (getting to a demo).

          PRIORITIZE contacts that have a known email address.
          DO NOT choose all similar contacts (e.g. not 3x Clinical Operations) If you have one ClinOps already, focus on e.g.  Data Management next.

          Select {max_titles} persons.

          Return only the index (starting with 0) of the persons you are selected. e.g. for 3 persons to search, a result can be '2,6,9'
          E.g. if you want to select {{0: {{'title': 'Clinical Operations', 'headline': 'TITLE'}}}} the index is 0


          """+ json.dumps(selected_data)

        gpt_result = Utils_obj.make_gpt_call(prompt=prompt, system="You identify relevant contacts as BDR for selling Castor, return only a string",temp=0.01, engine='castor-gpt-4')

        # Convert the string to a list of integers
        indices_to_select = [int(i.strip().strip('"').strip("'")) for i in gpt_result.split(',') if i.strip()]

        # Extract the specific items
        selected_contacts = [found_contacts[i] for i in indices_to_select if i < len(found_contacts)]
        #remove the selected contacts from found_contacts so we can merge them back later
        found_contacts = [contact for i, contact in enumerate(found_contacts) if i not in indices_to_select]


    # Step 3: Generate outbound messages for contacts with complete email addresses
    counter = 1

    # because we want to generate as many emails as possible
    if len(found_contacts)>len(selected_contacts):
      selected_contacts = found_contacts

    final_contact_list = []
    for next_contact in selected_contacts:
      # Initialize email_subject and email_body as empty strings
      email_subject = ""
      email_body = ""
      if next_contact.get("email"): # Check if email exists
        outbound_json_str = create_outbound(prompt=prompt_email, contact=next_contact, system=system, company_info=company_info)

        # Clean JSON string
        outbound_json_clean = Utils_obj.clean_json_string(outbound_json_str)

        # Check if JSON string is in valid format
        if Utils_obj.is_valid_json(outbound_json_clean):
          ph("<li>Message in valid JSON format</li>")
          outbound_json = json.loads(outbound_json_clean)
          email_subject = outbound_json.get("title", "N/A")
          email_body = outbound_json.get("body", "N/A")

        else:
          ph("<li>Message is invalid JSON string: " + outbound_json_clean)

      #UPDATE NOV 17: Keep contacts that have no email so we can still reach out to them.
      # Updget_creditsate next_contact with email subject and body (empty strings if invalid JSON format)
      next_contact["email_subject"] = email_subject
      next_contact["email_body"] = email_body

      ph("<h2>EMAIL #{}:</h2>".format(counter))
      ph("<li>{} {} {} {}</li>".format(next_contact['first_name'], next_contact['last_name'], next_contact['title'], next_contact['email']))
      ph("<li>LinkedIn: <a href='{}' target='_blank'>{}</a></li>".format(next_contact["linkedin_url"], next_contact["linkedin_url"]))
      ph("<li>Headline: {}</li>".format(next_contact["headline"]))
      ph("<li>EMAIL SUBJECT: {}</li>".format(next_contact["email_subject"]))
      ph("<li>EMAIL Body: {}</li>".format(next_contact["email_body"]))

      counter += 1
      final_contact_list.append(next_contact)

    #Merge the list with the emails back with the rest so we retain all contacts.
    final_contact_list = final_contact_list +found_contacts
    return final_contact_list

#@title Flatten Company info with Excel
def flatten_company_info(company_info):
    # Flatten nested structures in company_info
    flattened_info = {}
    for key, value in company_info.items():
        if isinstance(value, list):
            # Convert list to a string or handle appropriately
            flattened_info[key] = str(value)
        elif isinstance(value, pd.DataFrame):
            # Convert DataFrame to a string representation or handle as needed
            flattened_info[key] = value.to_string()
        else:
            flattened_info[key] = value
    return flattened_info

def convert_timestamp_to_string(element):
    if isinstance(element, pd.Timestamp):
        return element.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return element

def update_google_sheet(df, sheet_url: str, new_worksheet_title: str) -> None:
    df.replace([np.inf, -np.inf, np.nan], None, inplace=True)
    df.fillna("", inplace=True)

    # If you choose to use applymap despite the warning:
    df = df.applymap(convert_timestamp_to_string)
    sheet_id = sheet_url.split('/d/')[1].split('/edit')[0]
    sh = gc.open_by_key(sheet_id)

    try:
        new_worksheet = sh.add_worksheet(title=new_worksheet_title, rows=str(len(df)+1), cols=str(len(df.columns)))
    except gspread.exceptions.APIError:
        new_worksheet = sh.worksheet(new_worksheet_title)

    values = [df.columns.tolist()] + df.astype(str).values.tolist()  # Ensure all values are strings
    new_worksheet.update('A1', values)  # Use positional arguments for range and values

    return

def get_company_names(sheet_url:str, worksheet_name:str='RUNNING LIST')->str:
    '''This function returns all the company names present in the "ACCOUNT NAME" col into
       as a comma seperated string
       args:
          sheet_url: url of the google sheet
          worksheet_name: name of the sheet within the google sheet to fetch the data from
      return:
          comma seperated string of company names
    '''
    # Extract the Sheet ID from the URL
    sheet_id = sheet_url.split('/d/')[1].split('/edit')[0]

    # Open the Google Spreadsheet by ID
    sh = gc.open_by_key(sheet_id)

    # Select the worksheet by name
    worksheet = sh.worksheet(worksheet_name)

    # Get all the values from the worksheet
    data = worksheet.get_all_values()

    # Convert to a DataFrame
    df = pd.DataFrame(data)

    # Set the first row as the header
    df.columns = df.iloc[0]
    df = df[1:]

    return list(df['ACCOUNT NAME'].iloc[1:])

def get_name_email_dict(sheet_url:str,worksheet_name:str="RUNNING LIST")-> dict:
    ''' This function gets company name and their email number (if no email num is provided then 1 is set as default).
        Key is the company name and value is the email number
        args:
          sheet_url: url of the google sheet
          worksheet_name: name of the sheet within the google sheet to fetch the data from
        return:
          dictionary where key = company name and value= number of email to be sent
    '''
    # Extract the Sheet ID from the URL
    sheet_id = sheet_url.split('/d/')[1].split('/edit')[0]

    # Open the Google Spreadsheet by ID
    sh = gc.open_by_key(sheet_id)

    # Select the worksheet by name
    worksheet = sh.worksheet(worksheet_name)

    # Get all the values from the worksheet
    data = worksheet.get_all_values()

    # Convert to a DataFrame
    df = pd.DataFrame(data)

    # Set the first row as the header
    df.columns = df.iloc[0]
    df = df[2:] # because first row col name , second row examples hence 2 here
    result_dict = {
    row['ACCOUNT NAME']: (
        1 if pd.isna(row['# EMAILS (LINKED TO CONTACTS) ']) or row['# EMAILS (LINKED TO CONTACTS) '] == ''
        else max(map(int, row['# EMAILS (LINKED TO CONTACTS) '].split('-')))
    )
    for _, row in df.dropna(subset=['ACCOUNT NAME']).iterrows() if row['ACCOUNT NAME'].strip()
    }
    return result_dict

def get_google_sheet_col(sheet_url:str, col_name:str,worksheet_name:str='RUNNING LIST') -> list:
    '''This function returns all the company names present in the "ACCOUNT NAME" col into
       as a comma seperated string
       args:
          sheet_url: url of the google sheet
          worksheet_name: name of the sheet within the google sheet to fetch the data from
      return:
          comma seperated string of company names
    '''
    # Extract the Sheet ID from the URL
    sheet_id = sheet_url.split('/d/')[1].split('/edit')[0]

    # Open the Google Spreadsheet by ID
    sh = gc.open_by_key(sheet_id)

    # Select the worksheet by name
    worksheet = sh.worksheet(worksheet_name)

    # Get all the values from the worksheet
    data = worksheet.get_all_values()

    # Convert to a DataFrame
    df = pd.DataFrame(data)

    # Set the first row as the header
    df.columns = df.iloc[0]
    df = df[2:]
    if col_name in df:
      results_list = df[col_name].to_list()
    else:
      results_list = []
    return results_list

# Define a function to process each part of the dictionary
def process_company_part(part,sheet_url,sheet_contacts,sheet_company,is_enrich_list,is_description = True,is_company_web= True,is_classify = True,is_linkedIn = True,is_funding=True,is_company_size=True,is_trials=True,is_pipeline=True,is_valid_email = False):
  count = 0
  print("*******inside function process_company_part *********")
  for current_company, max_emails_to_send in part.items():
      try:
          # will check if the file needs to be enriched or not
          if is_enrich_list and is_enrich_list[count]=='NO':
            print(f"current company {current_company} skipped because it is already enriched and count = {count}")
            count+=1
            continue
          
          else:
            print(f"starting enriching of {current_company} and count = {count}")
            count+=1
          
          max_emails_to_send = int(max_emails_to_send)
          print(f"max emails {max_emails_to_send}")
          print(f"current company {current_company}")

          company_info = find_company_info(current_company,is_description=is_description,is_company_web=is_company_web,is_classify=is_classify,is_linkedIn = is_linkedIn,is_funding=is_funding,is_company_size=is_company_size,is_trials=is_trials,is_pipeline=is_pipeline)
          print("Starting credits: " + str(linkedIn_obj.get_credits()))
          if max_emails_to_send > 0:
              contacts = find_contacts_and_create_messages(
                  company_info=company_info, prompt_email=const.PROMPT_EMAIL, system=const.PROMPT_SYSTEM, max_titles=max_emails_to_send,validate_email=is_valid_email)

              for contact in contacts:
                  contact.pop('headline', None)
                  contact.pop('summary', None)

          company_info_flat = flatten_company_info(company_info)
          company_list.append(company_info_flat)
          if max_emails_to_send > 0:
              contact_list.extend(contacts)

          print("Ending credits: " + str(linkedIn_obj.get_credits()))

          # saving data
          if max_emails_to_send > 0:
              for contact in contact_list:
                  try:
                      paragraphs = contact['email_body'].split("#split_paragraph#")
                      for i, paragraph in enumerate(paragraphs, 1):
                          contact[f'paragraph{i}'] = paragraph.strip()
                  except KeyError:
                      print("Key 'email_body' missing in contact.")
                  except Exception as e:
                      print(f"An error occurred while processing the contact: {e}")

          # Convert list of dictionaries to DataFrame
          df = None
          df_company = None
          df = pd.DataFrame(contact_list)
          df_company = pd.DataFrame(company_list)

          # drop duplicates :
          df = df.drop_duplicates()

          if max_emails_to_send > 0:
              update_google_sheet(df, sheet_url, sheet_contacts)
          else:
              update_google_sheet(df_company, sheet_url, sheet_company)

          print("****** added to google sheet added **************")

      except Exception as e:
          print(f"An error occurred for {current_company}: {e}")
          traceback.print_exc()

def split_dict(d:dict, n:int)->list:
    '''Split the dict into n different parts so we could use it for multithreading
       args:
          - d: dictionary to be broken into n different part 
          - n: number of part to break the dict (usually same as the number of threads)
       returns:
          - list of "n" dictionary 
    '''
    step = int(len(d) / int(n))
    list_of_dict = []
    for i in range (0,len(d),step):
      my_dict = dict(itertools.islice(d.items(), i,i+step))
      list_of_dict.append(my_dict)
    return list_of_dict

def split_list(lst, n)->list[list]:
    '''Split the list into n different parts so we could use it for multithreading
       args:
          - list: list to be broken into n different part 
          - n: number of part to break the dict (usually same as the number of threads)
       returns:
          - list of "n" list 
    '''
    step = max(1, int(len(lst) / n))  # Ensure step is at least 1
    list_of_lists = []
    for i in range(0, len(lst), step):
        sub_list = lst[i:i + step]
        list_of_lists.append(sub_list)
    return list_of_lists


# Function to load or create credentials
def load_or_create_credentials(token_file,credentials_file,scope):
    # Check if the token file exists
    if os.path.exists(token_file):
        # Load the credentials from the token file
        creds = Credentials.from_authorized_user_file(token_file, scope)
    else:
        # Load the credentials from the downloaded JSON file
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scope)
        creds = flow.run_local_server(port=0)
        # Save the credentials to a token file for future use
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    return creds

def company_enrichment(part,is_description = True,is_company_web= True,is_classify = True,is_linkedIn = True,is_funding=True,is_company_size=True,is_trials=True,is_pipeline=True,is_valid_email = False):
  for current_company, id in part.items():
      try:
          print(f"current company {current_company}")
          internal_flag = get_internal_flag(sf,id) 
          
          if internal_flag:
            print(f"company skipped because already processed (internal flag)")
            continue
          
          company_info = find_company_info(current_company,is_description=is_description,is_company_web=is_company_web,is_classify=is_classify,is_linkedIn = is_linkedIn,is_funding=is_funding,is_company_size=is_company_size,is_trials=is_trials,is_pipeline=is_pipeline)
          print("Starting credits: " + str(linkedIn_obj.get_credits()))

          company_info_flat = flatten_company_info(company_info)

          print("Ending credits: " + str(linkedIn_obj.get_credits()))

          ####### write code to save into salesforce here ############
          insert_record(sf,company_info_flat,id)

          set_internal_flag(sf,id,True) # setting internal flag to true so if processing stops in the middle we can pick back up where we left off
          print(f"internal flag set to True")
      except Exception as e:
          print(f"An error occurred for {current_company}: {e}")
          traceback.print_exc()
  
  # set all internal flags back to False so we can do enrichment later on
  for current_company, id in part.items():
    try:
        set_internal_flag(sf,id,False) # setting internal flag to true so if processing stops in the middle we can pick back up where we left off
        print(f"flag set to false for company {current_company}")
    except Exception as e:
        print(f"An error occurred for {current_company}: {e}")
        traceback.print_exc()



# Define the scope of the application
scope = [const.GOOGLE_SHEET_API_ENDPOINT,const.GOOGLE_DRIVE_AUTH]
token_file = "./outreach_app/token.json"
credentials_file = "./outreach_app/credientials.json"
creds = load_or_create_credentials(token_file,credentials_file,scope)
# if creds:
gc = gspread.authorize(creds)
company_list = []
contact_list = []
