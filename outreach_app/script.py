import pandas as pd
import json
from collections import defaultdict
import gspread
from google.auth import default
from openai import AzureOpenAI
from IPython.display import HTML, display
from datetime import datetime
from search import Search
from utils import Utils
from LinkedIn import linkedIn
from zoom_info import ZoomInfo
import numpy as np
import traceback

total_output = ""
Utils_obj = Utils()
linkedIn_obj = linkedIn()
ZoomInfo_obj = ZoomInfo()
Search_obj = Search()

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
  Always add the {{CALL_TO_ACTION}} template tag in final paragraph, separate sentence
  Split each paragraph with: #split_paragraph#
  For example:{"title":"Email SUBJECT","body":"{{Recipient.FirstName}}#split_paragraph#This is paragraph 1\n#split_paragraph#this is paragraph 2#This is paragraph 3#split_paragraph#{{CALL_TO_ACTION}} "}
  Return only a valid JSON string, escape control characters like \\ and \\n for new lines. Don't insert newlines in your return anywhere outside of the message body.

  """
  #{{Recipient.FirstName}}" and the last paragraph can ONLY be {{CALL_TO_ACTION}}
  return_json = Utils_obj.make_gpt_call(system=system, prompt=prompt, temp=temp)

  return return_json

#Find all company info

def find_company_info(company_name):
  company_info = {}
  trials = {}
  pipeline = {}

  company_info["name"] = company_name


  ph("<h3>"+"Starting sleuthing for: " + company_name+"</h3>")
  ph("<ul>")

  # get description of company

  company_description_json = Search_obj.google_search("what does \"" + company_name + "\" do? -site:linkedin.com -facebook.com", 1)
  company_snip = company_description_json["items"][0]["snippet"]

  company_info["description"] = company_snip

  ph("<li>"+"Company snippet: "+company_snip+"</li>")

  #classify the copmany
  chat_output = Utils_obj.gpt_json_request(system='You are a life sciences web researcher. Return only JSON, eg. {"type": "company_type"}',temp=0.3, prompt="""
                    Company description: """+company_snip+"""
                    Make a best guess as to what type of company this is. Choose from: "Academic" (including Hospitals), "Research site", "Medical Device", "Digital Therapeutic", "Diagnostic", "Biotech", "Pharmaceutical company" or "eClinincal Vendor".

                    Return only JSON.
                    Return in this format: {"type": "company_type"}
                    """)

  company_info["industry"] = chat_output['type']



  # get website url

  company_info["website"] = company_description_json["items"][0]["displayLink"]


  #get company linkedIn url

  company_li_url_json = Search_obj.google_search("site:linkedin.com "+company_name, 1)
  company_info["li_url"] =  company_li_url_json["items"][0]["link"]


  ph("<li>"+"LinkedIn URL: "+company_info["li_url"]+"</li>")

  #get funding amount
  #TODO, this needs to be improved, it does not return the funding amount
  #TODO: We need this to return the amount and last raise
  def get_company_funding(company_name):
    company_funding = ""

    # First search query
    company_funding_json1 = Search_obj.google_search('site:crunchbase.com/organization/ inurl:company_financials +"'+company_name+'"  +" has raised a total"', 1)
    if "items" in company_funding_json1 and company_funding_json1["items"]:
        if "snippet" in company_funding_json1["items"][0]:
            company_funding += company_funding_json1["items"][0]["snippet"]

    # Second search query
    company_funding_json2 = Search_obj.google_search('site:crunchbase.com/organization/ inurl:company_financials +"'+company_name+'"  +" Their latest funding was raised "', 1)
    if "items" in company_funding_json2 and company_funding_json2["items"]:
        if "snippet" in company_funding_json2["items"][0]:
            company_funding += company_funding_json2["items"][0]["snippet"]

    return company_funding

  company_funding = get_company_funding(company_name)

  company_info["funding"] = company_funding

  ph("<li>"+"Company funding: "+company_funding+"</li>")

  #get company size from linkedin

  company_size, recent_updates = linkedIn_obj.get_company(company_info["li_url"])

  company_info["size"] = company_size
  company_info["recent_updates"] = recent_updates
  ph("<li>"+"Company size: "+str(company_size)+"</li>")

  # get all trials

  company_info["trials"], company_info["number_of_trials"] = Utils_obj.find_trials(company_name)
  ph("<li>Trials found: "+ str(company_info["number_of_trials"]) +"</li>")

  company_info["newest_trial"] =  company_info["trials"]['StartDate'].max()

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

                    Company name: """+company_name+"""
                    Company size: """+str(company_size)+"""
                    Number of trials: """+str(company_info["number_of_trials"])+"""
                    Company industry:"""+company_info["industry"]+"""

                    Return only JSON.
                    Return in this format: {"type": "sponsor_small"}
                    """)
  company_class = chat_output['type']
  company_info["company_class"] = company_class

  ph("<li>"+"Company classification: " + company_class+"</li>")


  ph("<li>"+"Website: " + company_info["website"] +"</li>")


  chat_output = Utils_obj.gpt_json_request('You are a life sciences web researcher. Return only JSON, e.g. {"therapeutic_areas": "list, of, therapeutic ares"}',0.5, """
                    Company description: """+company_info["description"]+"""
                    Last 5 conducted Trials: """+str(company_info["trials"]) +"""
                    Make a best guess as to what Therapeutic Areas this company operates in. E.g. Oncology, Vaccine, etc.
                     return a comma seperate list of the top 3 Therapeutic areas.
                    Return only JSON.
                    Return in this format: {"therapeutic_areas": "list, of, therapeutic ares"}
                    """)


  company_info["therapeutic_areas"] = chat_output['therapeutic_areas']


  ph("<li>"+"Industry: " + company_info["industry"]+"</li>")
  ph("<li>"+"TAs: " + company_info["therapeutic_areas"] +"</li>")

  #Get pipeline information

  company_info["pipeline"]  = (Search_obj.google_search_for_pipeline(website=str(company_info["website"])))

  ph("<li>"+"Pipeline found: "+str(company_info["pipeline"])+"</li>")

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
def find_contacts_and_create_messages(company_info, system, prompt_email, max_titles=10,products_to_sell = "Modular Clinical Trial platform for all types of trials" ):
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
            zoominfo_out = ZoomInfo_obj.get_zoominfo_details(row["id"])["data"]["result"][0]["data"][0]
            
            # TO DO FIND THIS PROFILE ON GOOGLE WITH SEARCH WHICH WILL BE WAY FASTER
            linkedin_url =  linkedIn_obj.get_person_li(row['firstName'], row['lastName'], company_info['name'])

            first_name, last_name, headline, summary, current_companies_and_titles = linkedIn_obj.get_linkedIn(linkedin_url)


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

def convert_timestamps_to_string(df):
    for column in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            df[column] = df[column].dt.strftime('%Y-%m-%d %H:%M:%S')
    return df

def update_google_sheet(df, sheet_url:str, new_worksheet_title:str)->None:
    ''' This function takes in data frame and updates the google sheet with the data from the dataframe
        args:
          df : Dataframe with the data to be saved into google sheet
          Sheet_url: google sheet sharing url
          new_worksheet_title : title to worksheet you want to save the data in
        returns
          None
    '''
    # handling nan values in df
    # Assuming df is your DataFrame
    df.replace([np.inf, -np.inf, np.nan], None, inplace=True)
    df = convert_timestamps_to_string(df)

    # Extract the Sheet ID from the URL
    sheet_id = sheet_url.split('/d/')[1].split('/edit')[0]

    # Open the Google Spreadsheet by ID
    sh = gc.open_by_key(sheet_id)

    # Create or access the worksheet
    try:
        new_worksheet = sh.add_worksheet(title=new_worksheet_title, rows=str(len(df)+1), cols=str(len(df.columns)))
    except gspread.exceptions.APIError:
        # If the worksheet already exists, select it
        new_worksheet = sh.worksheet(new_worksheet_title)

    # Prepare the DataFrame data to be updated
    values = [df.columns.tolist()] + df.values.tolist()

    # Update the worksheet with the DataFrame values
    new_worksheet.update('A1', values)
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


if __name__ == "__main__":
  #@title Fill in company details

  company_name = "Genentech, Gilead, Biomarin" 
  max_emails_to_send  = 1

  prompt_email = """

  You are going to write a high quality, personalized, cold outbound email for Castor, an eClinical company operating in life sciences.
  You will be provided with all the information about the company
  The number of Phase 1,2,3,4 trials they have conducted, The description of the company, their future pipeline.
  The goal is to give them a demo of our platform, either EDC, ePRO, eConsent, or all modules combined in a DCT workflow. Use one of the following value props: "Patient Centric", "Flexible", "Short Build timelines", "API first for integrations", "User-friendly", "Modular platform".

  The focus is on understanding their pain points and demonstrating how Castor best help them run their clinical trials company's size, therapeutic area and pipeline.
  The messaging should be tailored to the specific personas and company profiles, highlighting the value and benefits of Castor’s offerings.
  Always link castors value propositions back to the goals and objectives for the prospect and target company.
  DO NOT MENTION funding rounds unless they are in last 3 months, and DON'T dwell on it.
  DO NOT EXPLAIN THE COMPANY BACK TO THEM. Never EXPLAIN what they do, just show we understand what we do.


  Optimize the email for open and response rates by levegaring the contact information, including their own linkedin summary, and the company's pipeline.
  The email must NOT be salesy, but sound HELPFUL and TO THE POINT.
  Don't mention "paint points" and other generic sales talk, focus on 1 likely problem they might have.
  The INTRO must be short and snappy, get straight to the point
  THe email must ALWAYS be 5 paragrahps long, the first one is "Hello {{Recipient.FirstName}}" and the last paragraph can ONLY be {{CALL_TO_ACTION}}.
  There should be no end, No closing, NO SIGNATURE, No greetings, only subject and 3 email body paragraphs
  Salutation should always be "Hello {{Recipient.FirstName}}," using Pardot template tags, don't but in the action email.
  You MUST make the Subject include some custom, for example a future trial or something mentioning therapeutic areas
  """
  prompt_system = """
  You are the best BDR that has ever worked at Castor, or at any eClinical Company.
  For this task, you will refer to us as Castor. You are going to write a high quality, personalized, cold outbound message.
  You will be provided all relevant information about the business.
  Return only a valid JSON string, escape control characters like \\ and \\n for new lines.
  """
  #@title Collect Company Information

  #TODO URGENT process further options: export as CSV, Push message to Outreach (via API) etc
  #TODO add function to figure out missing email address from email addresses that we DO have
  #TODO add a frontend that prints live updates of the running script and shows the output separately. Basically adjusting the ph function to push output to somewhere else in a frontend

  #clear total output before each run through
  total_output = ""
  company_names = company_name.split(',')
  company_names = [x.strip() for x in company_names]

  leads_df = pd.DataFrame()
  leads_df["Company"] = company_names

  leads_df["Company Description"] = ""
  leads_df["Website"] = ""
  leads_df["Industry"] = ""
  leads_df["Company Size"] = ''

  contact_list = []
  company_list = []
  for current_company in company_names:
      try:
          company_info = find_company_info(current_company)
          print("Starting credits: " + str(linkedIn_obj.get_credits()))
          if max_emails_to_send > 0:
            contacts = find_contacts_and_create_messages(
                company_info=company_info, prompt_email=prompt_email, system=prompt_system, max_titles=max_emails_to_send)

            for contact in contacts:
                contact.pop('headline', None)
                contact.pop('summary', None)

          company_info_flat = flatten_company_info(company_info)
          company_list.append(company_info_flat)
          if max_emails_to_send > 0:
            contact_list.extend(contacts)

          print("Ending credits: " + str(linkedIn_obj.get_credits()))

      except Exception as e:
          print(f"An error occurred for {current_company}: {e}")
          traceback.print_exc()

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
            traceback.print_exc()

  # Convert list of dictionaries to DataFrame
  df = pd.DataFrame(contact_list)
  df_company = pd.DataFrame(company_list)

  if max_emails_to_send == 0:
    df_company.to_excel("company.xlsx")   
  
  else:
    df.to_excel("contacts.xlsx")
  
