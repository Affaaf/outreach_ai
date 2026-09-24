## Outreach AI


### Clone the Repository

First, clone this repository to your local machine using the following command:

```
git clone /https://github.com/Affaaf/outreach_ai.git
```


### Create a .env File

After cloning the repository, create a `.env` file in the root directory. You can use the sample `.env.sample` file provided in this README.md as a template. Rename it to `.env` and fill in the necessary environment variables.

### Sample .env File

```plaintext
SEARCH_KEY= google search key
SEARCH_CX = cx key
OPENAI_KEY = openAI key 
NUBELA_API_KEY= nubela key
ZOOM_INFO_KEY =-----BEGIN PRIVATE KEY-----\n your private key\n-----END PRIVATE KEY----- 
```

Make sure to replace placeholders with your actual values.

### Create a Python Environment

It's recommended to use a Python virtual environment to manage dependencies. Navigate to the root directory of the repository in your terminal and run the following commands to create and activate a virtual environment:

```bash
# For Linux/MacOS
python3 -m venv env
source env/bin/activate

# For Windows
python -m venv env
.\env\Scripts\activate
```

This will create a virtual environment named `env` and activate it.

### Install Requirements

Once the virtual environment is activated, you can install the required dependencies using `pip` with the following command:

```bash
pip install -r requirments.txt
```
```bash
sudo apt-get install redis
```
This will install all the dependencies listed in the `requirements.txt` file.

### To Run Migrations

```bash
python manage.py makemigrations
```

```bash
python manage.py migrate
```

### Create Super User in Django Admin Pannel

```bash
python manage.py createsuperuser
```

### Running the Application

 You will need ```credientials.json``` generated from google cloud for authentication purpose, if the filename is geneated from google cloud platform and has a different name then please rename it to ```credientials.json``` and place in the working directory. Change the ```INPUT_SHEET_URL``` located in ```constants.py``` and to the input file (google sheet link) from where you want to fetch the details. Change the ```OUTPUT_SHEET_URL``` in ```constants.py```(where you want to save the results). Just run the following command to run main.py after updating the url.

### Run Server

```bash
python manage.py runserver
```

### Run Celery workers

```bash
celery -A outreach_ai_tasks.celery_service.celery_app worker --loglevel=info
```

### Run Celery Beat workers

```bash
celery -A outreach_ai_tasks.celery_service.celery_app beat --loglevel=info
```


### To Access Admin Pannel On Live Server 

```bash
http://localhost:8000/admin/
```

There are many boolean flags which you can activate or deactivate depending upon the type of company information you want to fetch.

---

Follow these instructions carefully to set up the repository environment and dependencies successfully.