# genscan4web or GSW for short
This tool processes scanned genealogical documents such as memorial card or funeral announcement to extract useful information from it.
Some OCR and processing logic is let loose on the documents after which the scanned documents and related extracted OCR data is published on a Wordpress site to be redacted by humans.
The redacted information is downloaded and used to rename the original files of the scanned documents.

# Extracted information includes:
- is it a memorial card or funeral announcement
- name of deceased
- place of birth and demise
- date of birth and demise
- if a picture is available
- war veteran information

## Backend
### Installation
Although performance of the PC isn't really important, a beefy PC might help.
The backend Python app does all the heavy lifting of performing OCR and massaging that info, uploading and downloading it to/from a Wordpress site.

- Install Tesseract first, with environment correctly set up.
- Install Python (local or virtual).
- Install dependencies in your local or virtual environment:
    `pip install -r requirements`
- Create a working folder for this app.
- Copy the git to this folder.
- Copy the config.default to a file named config .
- Edit the config file to your liking.
- Create a .env file containing the data received from owner.

### Backend operation
Copy scanned documents (PDF only!) into a working folder. 
It does not have to be the same folder as the Python app folder. 
Subfolders are allowed. 
If working folder or subfolder has the word 'bidprentje' or other known description in it, files within it will be treated as accordingly.
Some folders starting with an undersore will be ignored. eg. an _ignore folder can hold documents and/or subfolders with documents, but those will be ignored by the process.

Run app from the desired folder:
    `python gsw.py`

This app runs either a single time or continuously depending on config settings.

Interrupt the continuously running app with CTRL-C.

## Frontend
The frontend is a Wordpress based site that is members only.
Registered users can redact the information of the shown documents.
Based on 4-eyes priciple the documents are reviewed twice, but no single user will be presented with a document they already treated before.
