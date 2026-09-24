import threading
import pandas as pd
import logging

from celery import Celery
from outreach_app.constant import const
from outreach_app.main_script import get_google_sheet_col
from outreach_app.main_script import get_name_email_dict
from outreach_app.main_script import process_company_part
from outreach_app.main_script import split_dict
from outreach_app.main_script import split_list
from outreach_ai_tasks.celery_service import celery_app
from outreach_app.salesforce import *
from outreach_app.models import RunningJob
from outreach_app.main_script import company_enrichment


logging.basicConfig(filename="./outreach_ai/celery_logs.log", 
					format='%(asctime)s %(message)s', 
					filemode='w') 

# Create logger instance
logger = logging.getLogger() 

# Set logger level
logger.setLevel(logging.DEBUG) 

# Add a FileHandler to the logger instance to log INFO messages
file_handler = logging.FileHandler("./outreach_ai/celery_logs.log")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


@celery_app.task(bind=True, name="originate")
def originate(self, work_sheet_name, company_sheet_name, contact_sheet_name, input_sheet_url, output_sheet_url):
    company_info_url = input_sheet_url

    company_email_dict = get_name_email_dict(company_info_url,
                                             work_sheet_name)  # constains names as keys and number of emails as values
    is_enriched_list = get_google_sheet_col(company_info_url, col_name="To enrich", worksheet_name=work_sheet_name)
    list(company_email_dict.keys())
    prompt_email = const.PROMPT_EMAIL
    prompt_system = const.PROMPT_SYSTEM
    sheet_url = output_sheet_url
    total_output = ""
    company_names = list(company_email_dict.keys())

    leads_df = pd.DataFrame()
    leads_df["Company"] = company_names

    leads_df["Company Description"] = ""
    leads_df["Website"] = ""
    leads_df["Industry"] = ""
    leads_df["Company Size"] = ''

    sheet_contacts = contact_sheet_name
    sheet_company = company_sheet_name

    is_description = True
    is_company_web = True
    is_classify = True
    is_linkedIn = True
    is_funding = True
    is_company_size = True
    is_trials = True
    is_pipeline = True
    is_validate_email = False

    # Example usage
    n_threads = 1  # Number of threads to use
    company_email_dict_parts = split_dict(company_email_dict, n_threads)
    n_enriched_parts = split_list(is_enriched_list, n_threads)
    threads = []
    i = 0
    for part in company_email_dict_parts:
        thread = threading.Thread(target=process_company_part, args=(
        part, sheet_url, sheet_contacts, sheet_company, n_enriched_parts[i], is_description, is_company_web,
        is_classify, is_linkedIn, is_funding, is_company_size, is_trials, is_pipeline, is_validate_email))
        i += 1
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    last_task = RunningJob.objects.last()
    if last_task:
        last_task.status = "COMPLETED"
        last_task.save(update_fields=['status'])



@celery_app.task(bind=True, name="sales_force")
def sales_force(self): 
    
    logger.info("Initializing Salesforce...")
    sf = initialize_salesforce()
    logger.info("Salesforce initialized successfully.")

    # Example usage
    logger.info("Fetching accounts from Salesforce...")
    df = fetch_accounts(sf)
    logger.info("Accounts fetched successfully.")

    data_dict = df.set_index('Name')['Id'].to_dict()
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
    THe email must ALWAYS be 5 paragrahps long, the first one is "Hello {{Recipient.FirstName}}".
    There should be no end, No closing, NO SIGNATURE, No greetings, only subject and 3 email body paragraphs
    Salutation should always be "Hello {{Recipient.FirstName}}," using Pardot template tags, don't but in the action email.
    You MUST make the Subject include some custom, for example a future trial or something mentioning therapeutic areas. 
    In the 3rd body paragraph you must never write the phrase "looking forward to", instead leave a open ended question like "would you be open to a demo" or "would you be open to a conversation", etc. It 
    is important that you leave the closing statment of 3rd body paragraph open ended depending on the context of the email and do not only use the terms mentioned above, try to come up with witty open ended closing remarks
    in the 3rd body paragraph. 
    Critical Note: 
    -No paragraph can ever be empty.  
    """
    prompt_system = """
    You are the best BDR that has ever worked at Castor, or at any eClinical Company.
    For this task, you will refer to us as Castor. You are going to write a high quality, personalized, cold outbound message.
    You will be provided all relevant information about the business.
    Return only a valid JSON string, escape control characters like \\ and \\n for new lines.
    """

    total_output = ""
    company_names = list(data_dict.keys())

    leads_df = pd.DataFrame()
    leads_df["Company"] = company_names

    leads_df["Company Description"] = ""
    leads_df["Website"] = ""
    leads_df["Industry"] = ""
    leads_df["Company Size"] = ''

    contact_list = []
    company_list = []

    sheet_contacts = "new_update"
    sheet_company = "company_test1"

    # flags to control company info - makes it modular, only call the flag you want the company fetched information on 
    is_description = True
    is_company_web= True
    is_classify = True
    is_linkedIn = True
    is_funding=True
    is_company_size=True
    is_trials=True
    is_pipeline=True
    is_validate_email=False

    # Example usage
    n_threads = 1  # Number of threads to use
    data_dict_parts = split_dict(data_dict, n_threads)
    # Create threads to process each part
    threads = []
    i = 0
    for part in data_dict_parts:
        thread = threading.Thread(target=company_enrichment,args=(part,is_description,is_company_web,is_classify,is_linkedIn,is_funding,is_company_size,is_trials,is_pipeline,is_validate_email))
        i +=1
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    last_task = RunningJob.objects.last()
    if last_task:
        last_task.status = "COMPLETED"
        last_task.save(update_fields=['status'])
    
    logger.info("Salesforce task completed.")
