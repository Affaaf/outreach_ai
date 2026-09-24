from simple_salesforce import Salesforce
import os
import pandas as pd
import datetime
import pytz
from dotenv import load_dotenv, find_dotenv 

def initialize_salesforce():
    _ = load_dotenv(find_dotenv())
    acc_pass = os.environ['SALES_FORCE_PASSWORD']
    acc_token = os.environ['SALES_FORCE_TOKEN']
    instance_domain = 'castoredc--uat.sandbox.my'
    username_ds = "syedhassanraza993@gmail.com.uat"
    sf = Salesforce(username=username_ds, password=acc_pass, security_token=acc_token, domain=instance_domain)
    print("Connected to Salesforce")
    return sf

def fetch_all_records(query, sf):
    records = []
    query_result = sf.query(query)

    # Store the initial batch of records
    records.extend(query_result['records'])

    # While there's more data, keep fetching
    while not query_result['done']:
        query_result = sf.query_more(query_result['nextRecordsUrl'], identifier_is_url=True)
        records.extend(query_result['records'])

    return records

def fetch_accounts(sf):
    query = "SELECT ID, Name FROM Account"
    accounts_data = fetch_all_records(query, sf)

    # Convert the records to a DataFrame
    df = pd.DataFrame(accounts_data)
    print(df)

    return df

def get_internal_flag(sf, record_id):
    try:
        account_record = sf.Account.get(record_id)
        # Return the value of the specified field
        return account_record.get("Internal_flag__c")
    except Exception as e:
        print(f"Error fetching record: {e}")
        return None

def set_internal_flag(sf,record_id,flag_value):
    sf.Account.update(record_id,{"Internal_flag__c":flag_value})
    return 

def create_account(sf, account_name, billing_country):
    new_account_data = {
        'Name': account_name,
        'BillingCountry': billing_country
    }
    result = sf.Account.create(new_account_data)
    print(f"New Account Created with ID: {result['id']}")
    return

def update_account_description(sf, account_id, new_data):
    account_details = sf.Account.get(account_id)
    current_description = account_details.get('Description', '')
    updated_description = current_description + new_data if current_description else new_data
    sf.Account.update(account_id, {'Description': updated_description})
    print(f"Account with ID: {account_id} has been updated with new description data.")
    return

def insert_record(sf,data_dict,account_id):
    # Set the timezone to CET
    timezone = pytz.timezone('CET')
    # Update multiple fields of a specific account
    fields_to_update = {
        'Account_Name_AI__c': str(data_dict["name"]),  # Example updates
        'Description_AI__c': str(data_dict["description"]),
        "Industry_AI__c":str(data_dict["industry"]),
        "Website_AI__c":str(data_dict["website"]),
        "LI_URL_AI__c":str(data_dict["li_url"]),
        "Funding_AI__c":str(data_dict["funding"]),
        "Size_AI__c":str(data_dict["size"]),
        "Recent_Updates_AI__c":str(data_dict["recent_updates"]),
        "Trials_AI__c":str(data_dict["trials"]),
        "Number_of_Trials_AI__c":str(data_dict["number_of_trials"]),
        "Newest_Trial_AI__c":str(data_dict["newest_trial"]),
        "Company_Class_AI__c":str(data_dict["company_class"]),
        "Therapeutic_area_AI__c":str(data_dict["therapeutic_areas"]),
        "Pipeline_AI__c":str(data_dict["pipeline"]),
        "Last_AI_update__c":datetime.datetime.now(timezone).isoformat()
    }

    # Prepare the data to update
    sf.Account.update(account_id,fields_to_update)
    print(f"Account with ID: {account_id} has been updated with new data.")
    return 

def update_account_fields(sf, account_record_name, fields_data):
    """
    Update specified fields for an account in Salesforce.
    fields_data should be a dictionary where keys are Salesforce field names
    and values are the new values for those fields.
    """
    # Retrieve the Salesforce ID for the Dummy Account
    query = f"SELECT Id, Name FROM Account WHERE Name = '{account_record_name}'"
    account_records = sf.query(query)
    account_id = account_records['records'][0]['Id']

    # Prepare the data to update
    sf.Account.update(account_id, fields_data)
    print(f"Account with ID: {account_id} has been updated with new data.")
    return 
