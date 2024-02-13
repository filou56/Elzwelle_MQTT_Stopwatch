#import httplib2
import os
import time
import datetime
import sys
import copy
import threading
import socket
import traceback

from apiclient import discovery
from google.oauth2 import service_account

# Setup Instructions
# (see also https://denisluiz.medium.com/python-with-google-sheets-service-account-step-by-step-8f74c26ed28e
# and https://developers.google.com/sheets/api/quickstart/python)
#
# Install the pip Python3 package management tool
# sudo apt install python3-pip
#
# Install the Google API
# sudo pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib httplib2
#
# Create a Google Cloud Project
# https://developers.google.com/workspace/guides/create-project
#
# Enable Google Workspace APIs
# https://developers.google.com/workspace/guides/enable-apis
# Search for (and enable) 'Google Drive API', 'Google Sheets API'
#
# Create a service account
# (https://developers.google.com/workspace/guides/create-credentials#service-account)
# Menu -> IAM & Admin -> Service Accounts
# Click '+ Create Service Account' and follow the steps (skip the optional steps)
# In the list of service accounts there should be one entry now.
# In the actions column, click on '...' -> 'Manage Keys'
# Click 'Add Key' -> 'Create New Key' -> Select JSON type -> CREATE and save the file on disk as 'credentials.json'
# Click on back '<--' on the top left, you should see the list with one service account and its email address in the first column.
#
# Go to https://drive.google.com and create a new spreadsheet_xxx
# Share the new spreadsheet_xxx with the new service account (email) with edit permissions.
# Copy the spreadsheet_xxx ID from the URL into the variable `spreadsheet_id` below.

#SPREADSHEET_ID = '1Jtap3Ei7VusDHihhi6jmjpVy-qbSZ3X-2lwbjBSn5HQ'

CLIENT_SECRET_JSON = 'client_secret.json'
client_secret_file = CLIENT_SECRET_JSON

# Singleton class for authentication and Google API wrapper.
class GoogleService:
    _instance = None
    global client_secret_file
    
    def __new__(cls):
        if cls._instance is None:
            print('{} Creating the GoogleService and authenticating'.format(datetime.datetime.now().astimezone().isoformat()))
            cls._instance = super(GoogleService, cls).__new__(cls)
            # Create the service and authenticate.
            scopes = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']
            # The credentials file as it was downloaded in the setup instructions.
            #secret_file = os.path.join(os.getcwd(), 'credentials.json')
            secret_file = os.path.join(os.getcwd(), client_secret_file)
            try:
                credentials = service_account.Credentials.from_service_account_file(secret_file, scopes=scopes)
                cls._instance.service = discovery.build('sheets', 'v4', credentials=credentials)
                cls._instance.lock = threading.RLock()
            except OSError as e:
                print(e)
                sys.exit(1)
        return cls._instance

    def get_service(self):
        return self.service
  
    def get_lock(self):
        return self.lock


class Spreadsheet:
    # The spreadsheet_xxx ID can be found in the URL of the sheet. Example:
    # https://docs.google.com/spreadsheets/d/1obtfHymwPSGoGoROUialryeGiMJ1vkEUWL_Gze_hyfk/edit#gid=0 has ID '1obtfHymwPSGoGoROUialryeGiMJ1vkEUWL_Gze_hyfk'
    def __init__(self, spreadsheet_id, tab_name):
        self.spreadsheet_id = spreadsheet_id
        self.tab_name = tab_name
        self.service = GoogleService().get_service()
        self.write_buffer = []
        self.lock = threading.RLock()
        self.thread = threading.Thread(target=self.write_forever)
        self.thread.start()
  
    def add_entry(self, entry):
        with self.lock:
            self.write_buffer.append(entry)

    def write_to_sheet(self):
        try:
            buffer = None
            with self.lock:
                if len(self.write_buffer) == 0:
                    return True
            
            buffer = copy.deepcopy(self.write_buffer)
            #data = {'values': [[entry] for entry in buffer]}
            data = {'values': buffer}
            # Insert new entries in the first blank line in column A by inserting the corresponding number of columns there.
            range_name = '{}!A1:B1'.format(self.tab_name)
            with GoogleService().get_lock():
                self.service.spreadsheets().values().append(spreadsheetId=self.spreadsheet_id, body=data, range=range_name, insertDataOption='INSERT_ROWS', valueInputOption='USER_ENTERED').execute()
                print('{} Added entries to {}: {}'.format(datetime.datetime.now().astimezone().isoformat(), self.tab_name, buffer))
                with self.lock:
                    del self.write_buffer[0:len(buffer)]
                    return True
        except socket.gaierror as e:
            print('{} Failed to write to Google Spreadsheet:'.format(datetime.datetime.now().astimezone().isoformat()), e)
        except socket.timeout as e:
            print('{} Failed to write to Google Spreadsheet:'.format(datetime.datetime.now().astimezone().isoformat()), e)
#        except httplib2.error.ServerNotFoundError as e:     # @UndefinedVariable
#           print('{} Failed to write to Google Spreadsheet:'.format(datetime.datetime.now().astimezone().isoformat()), e)
#        except google.auth.exceptions.TransportError as e:  # @UndefinedVariable
#           print('{} Failed to write to Google Spreadsheet:'.format(datetime.datetime.now().astimezone().isoformat()), e)
        except Exception as e:
            print('{} Failed to write to Google Spreadsheet:'.format(datetime.datetime.now().astimezone().isoformat()), 'Unexpected Exception:', e)
        traceback.print_exc()
        return False
  
    def write_forever(self):
        while True:
            if self.write_to_sheet():
                time.sleep(0.01)
            else:
                # In case of a write failure, wait longer before trying again.
                wait_seconds = 5.0
                time.sleep(wait_seconds)
                print('Retrying write to Google Spreadsheet in {} seconds.'.format(wait_seconds))

# Test
# if __name__ == '__main__':
#     start = Spreadsheet(spreadsheet_id=SPREADSHEET_ID, tab_name='Start')
#     ziel  = Spreadsheet(spreadsheet_id=SPREADSHEET_ID, tab_name='Ziel')
#     start_time = time.time()
#     for i in range(100):
#         start.add_entry([time.strftime('%H:%M:%S', time.localtime()), time.time() - start_time])
#         ziel.add_entry([time.strftime('%H:%M:%S', time.localtime()), time.time() - start_time])
#         time.sleep(10)

