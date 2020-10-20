
# Confluence Content Cleanup
A simple script for monitoring the age of content in an Atlassian Confluence Cloud instance via their REST API and sends an email to content authors when a certain number of days have passed since the content has been updated and/or reviewed for accuracy.  This script was inspired by Midori's Better Content Archiving add-on for on-prem Confluence installations.

## Requirements
- Python 3.6+ on Windows, Mac, or Linux
- Requests and Jinja2 python libraries
	- ```pip install requests jinja2```
- Atlassian API key from user with read permissions on Confluence
	- You can register one here: https://id.atlassian.com/manage-profile/security/api-tokens

## Installation
Simply clone this repo or download the code as a .zip and extract to folder.  Open confluence_content_cleanup.py and modify the user-defined parameters listed at the top of the script.  Configurable parameters are described within the code.

## Usage
Run the script with the API username and key as parameters (and optionally the SMTP password for your email account if needed).  To run this on a recurring basis, please use Windows Task Scheduler or cron on Unix.
```
python confluence_content_cleanup.py -apiuser <confluence admin email> -apikey <your api key> [-smtppass <your email password>]
```

