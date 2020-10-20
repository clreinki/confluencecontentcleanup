"""
This script uses the Atlassian Confluence API to retrieve lists of articles
from Confluence along with the author and last modified date and then emails
recipients about aged content

This script is meant to be used with a scheduler such as Windows Task Scheduler or cron on Unix
"""
import os, json, argparse, sys, datetime, smtplib, csv, ssl
from email.message import EmailMessage
try:
    import requests
except ImportError:
    print("Missing \"requests\" library - run \"pip3 install requests\" and run script again!")
    quit()
try:
    import jinja2
except ImportError:
    print("Missing \"jinja2\" library - run \"pip3 install jinja2\" and run script again!")
    quit()
from requests.auth import HTTPBasicAuth

#######################################
### USER DEFINED PARAMETERS GO HERE ###
#######################################

## Email server settings
SMTP_SSL = True
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = '587'
SMTP_USERNAME = None  # Define smtp username here if mail servers requires authentication
# SMTP_PASSWORD is defined via args
SMTP_FROM = 'confluence@yourdomain.com'

## Confluence settings
# What is your Confluence tenant url?  Example: <tenant>.atlassian.net
TENANT = 'yourdomain.atlassian.net'

# OPTIONAL - What spaces do you want to monitor?  Comma-separated space keys inside curly braces or blank for all
# EXAMPLE:  SPACES = {'KB','HELP'}
SPACES = {}

# OPTIONAL - What labels do you want to ignore?  Comma-separated labels inside curly braces or blank for none
# EXAMPLE:  EXCLUDE_LABELS = {'noarchive-single'}
EXCLUDE_LABELS = {}

# How many days until the content should be considered aged?  Count of days
AGED_DAYS = 180

# Who should be alerted? True or False
ALERT_CREATOR = True
ALERT_LAST_MODIFIED = True

# Additionally, should a site administrator be notified of aged content?
ALERT_ADMIN = False
ADMIN_EMAIL = 'admin@yourdomain.com'  # Required, as this email is used also in case originally creator no longer exists

###################################
### DO NOT EDIT BELOW THIS LINE ###
###################################

### FUNCTIONS ###
def get_all_content():
    # Start fetching all pages of content
    baseurl = "https://" + TENANT + "/wiki"
    endpoint = "/rest/api/content?expand=history,history.lastUpdated,space,metadata.labels"
    url = baseurl + endpoint

    data = requests.get(url, auth=HTTPBasicAuth(username, apikey))
    if data.status_code != 200:
        print("An error occurred when trying to get content!")
        sys.exit(2)
    data = data.json()
    content = data['results'][:]

    # Continue getting data over multiple pages
    if 'next' in data['_links']:
        while True:
            url = baseurl + data['_links']['next']
            data = requests.get(url, auth=HTTPBasicAuth(username, apikey))
            if data.status_code != 200:
                print("An error occurred when trying to get content!")
                sys.exit(2)
            data = data.json()
            content = content + data['results']
            if 'next' in data['_links']:
                continue
            else:
                break
    return content

def send_emails(obj,message_type):
    # Prepare Jinja2 template
    templateLoader = jinja2.FileSystemLoader(searchpath="./")
    templateEnv = jinja2.Environment(loader=templateLoader)
    TEMPLATE_FILE = "email_template.html"
    template = templateEnv.get_template(TEMPLATE_FILE)

    for key, value in obj.items():
        # Determine render variables
        
        title = str(len(value)) + ' Outdated Pages'
        bodytext = template.render(recipient=key,recipient_reason=message_type,title=title,items=sorted(value, key=lambda x: x.title),alert_days=AGED_DAYS)

        # Build email object
        msg = EmailMessage()
        msg['From'] = SMTP_FROM
        msg['To'] = key
        msg['Subject'] = 'Outdated Content on Confluence'
        msg.set_content(bodytext, subtype='html')

        # Send email
        with smtplib.SMTP(SMTP_SERVER, port=SMTP_PORT) as smtp_server:
            smtp_server.ehlo()
            if SMTP_SSL:
                smtp_server.starttls()
            if SMTP_PASSWORD:
                smtp_server.login(email_address, email_password)
            smtp_server.send_message(msg)

### END FUNCTIONS ###

### CLASSES ###
class Page:
    """A simple representation of a wiki page"""
    def __init__(self, id, title, lastUpdated_email, lastUpdated_days, created_email, url):
        self.id = id
        self.title = title
        self.lastUpdated_email = lastUpdated_email
        self.lastUpdated_days = lastUpdated_days
        self.created_email = created_email
        self.url = url

# Import username and API key arguments from command line
parser=argparse.ArgumentParser()
parser.add_argument('--apiuser', help='Define username used for accessing API')
parser.add_argument('--apikey', help='Define api key for corresponding username')
parser.add_argument('--smtppass', help='Define password for use when sending emails via SMTP')
args=parser.parse_args()

if args.apiuser == None or args.apikey == None:
    print("Please define a username and api key!")
    quit()
else:
    username = args.apiuser
    apikey = args.apikey

if args.smtppass:
    SMTP_PASSWORD = args.smtppass
else:
    SMTP_PASSWORD = None

# Fetch all content
content = get_all_content()

# Now let's process the data we've fetched
# This consists of multiple steps:
# 1. Identify active pages and determine if these pages are out of date
# 2. Create dictionary with email content
# 3. Generate the email to the creator and/or last modifier

active_content = []
today = datetime.datetime.now()

# These alert dictionaries will hold lists of Pages with the key being the send-to email address
creator_alerts = {}
modifier_alerts = {}
admin_alerts = {}

for item in content:
    # Step 1 - Determine out of date content
    days_since_updated = today - datetime.datetime.strptime(item['history']['lastUpdated']['when'], '%Y-%m-%dT%H:%M:%S.%fZ')
    url = 'https://' + TENANT + '/wiki/' + item['_links']['webui']
    
    # Handle blank email addresses, such as from authors no longer in organization
    created_email = item['history']['createdBy']['email']
    if created_email == '':
        created_email = ADMIN_EMAIL
    lastUpdated_email = item['history']['lastUpdated']['by']['email']
    if lastUpdated_email == '':
        lastUpdated_email = created_email

    # Step 2 - Create dictionary mapping page alerts to email recipients
    if item['type'] == 'page' and item['status'] == 'current' and days_since_updated.days > AGED_DAYS:
        # Filter based on space (if applicable)
        if SPACES and not item['space']['key'] in SPACES:
            continue

        # Loop thru page labels and skip if EXCLUDE_LABELS match found
        if EXCLUDE_LABELS:
            skip = False
            for page in item['metadata']['labels']['results']:
                if page['label'] in EXCLUDE_LABELS:
                    skip = True
            if skip:
                continue

        # Create Page class object
        obj = Page(item['id'],item['title'],lastUpdated_email,days_since_updated.days,created_email,url)

        if ALERT_CREATOR:
            # Check if key (email) already exists
            if not obj.created_email in creator_alerts:
                creator_alerts[obj.created_email] = []
            creator_alerts[obj.created_email].append(obj)

        if ALERT_LAST_MODIFIED:
            # Check if key (email) already exists
            if not obj.lastUpdated_email in modifier_alerts:
                modifier_alerts[obj.lastUpdated_email] = []
            modifier_alerts[obj.lastUpdated_email].append(obj)

        if ALERT_ADMIN:
            # Check if key (email) already exists
            if not ADMIN_EMAIL in admin_alerts:
                admin_alerts[ADMIN_EMAIL] = []
            admin_alerts[ADMIN_EMAIL].append(obj)

# Step 3 - Send the emails
if ALERT_CREATOR:
    send_emails(creator_alerts,"creator")
if ALERT_LAST_MODIFIED:
    send_emails(modifier_alerts,"last modifier")
if ALERT_ADMIN:
    send_emails(admin_alerts,"admin")
