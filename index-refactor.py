import re
from github import Github
import json
import sys
import requests
import smtplib, ssl
import github
import boto3

#variables
#Git UserName
USER_NAME = 'geethapalyam'
#Git Repo Name
REPO_NAME = 'palyam_test'
# Email notification reciever
RECEIVER_EMAIL = "palyamgeetha@gmail.com"
#slack channel receives notification
CHANNEL_NAME = "#git-script"
#release URL https://api.github.com/repos/{owner}/{repo}/releases/latest
RELEASE_URL = "https://api.github.com/repos/actions/runner/releases/latest"
#yaml File path
FILE_PATH = "runner-test.txt"
#branch name
BRANCH_NAME = "runner"
CLIENT = boto3.client('ssm')  # Creates an Amazon Simple Systems Manager client

def sendSlackNotification(PR_NUMBER:str):
    """
    Arguments:
            PR_NUMBER {str} -- Pull Request Number
    """
    WEBHOOK_URL = CLIENT.get_parameter(Name='/test/check/webhook', WithDecryption=True)["Parameter"]["Value"]
    # Code to send alert to the slack channel
    MESSAGE = (f"new Pull Request Link: https://github.com/{USER_NAME}/{REPO_NAME}/pull/{PR_NUMBER}")
    TITLE = (f"New Incoming pull Request :zap:")
    SLACK_DATA = {
        "username": "NotificationBot",
        "icon_emoji": ":satellite:",
        "channel" : CHANNEL_NAME,
        "attachments": [
            {
                "color": "#9733EE",
                "fields": [
                    {
                        "title": TITLE,
                        "value": MESSAGE,
                        "short": "false",
                    }
                ]
            }
        ]
    }
    BYTE_LENGTH = str(sys.getsizeof(SLACK_DATA))
    HEADERS = {'Content-Type': "application/json", 'Content-Length': BYTE_LENGTH}
    RESPONSE = requests.post(WEBHOOK_URL, data=json.dumps(SLACK_DATA), headers=HEADERS)
    if RESPONSE.status_code != 200:
        raise Exception(RESPONSE.status_code, RESPONSE.text)

def sendEmailNotification(PR_NUMBER:str):
    """
    Arguments:
            PR_NUMBER {str} -- Pull Request Number
    """
    SENDER_EMAIL = CLIENT.get_parameter(Name='/test/check/sender_email', WithDecryption=True)["Parameter"]["Value"]
    PASSWORD = CLIENT.get_parameter(Name='/test/check/sender_email_password', WithDecryption=True)["Parameter"]["Value"]
    # Code to send alert via email
    URL = f"https://github.com/{USER_NAME}/{REPO_NAME}/pull/{PR_NUMBER}"
    MESSAGE = '''hello

    A new Pull Request has been created

    The URL is: ''' + URL

    CONTEXT = ssl.create_default_context()

    # Try to log in to server and send email
    try:
        SMTP = smtplib.SMTP(host="smtp.gmail.com", port=587)
        SMTP.ehlo()
        SMTP.starttls(context=CONTEXT) # Secure the connection
        SMTP.ehlo()
        SMTP.login(SENDER_EMAIL, PASSWORD)
        SMTP.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, MESSAGE)
    except Exception as e:
        # Print any error messages to stdout
        print(e)
    finally:
        SMTP.quit()

def doGitOperations(ACCESS_TOKEN) -> str:
    """
    Arguments:
        ACCESS_TOKEN {str} -- GitHub Access Token
    Returns:
        str -- Created Pull Request Number
    """
    GIT = Github(ACCESS_TOKEN)
    REPO = GIT.get_repo(f"{USER_NAME}/{REPO_NAME}")
    #Getting the version and checksum of the latest release.
    RESPONSE = requests.get(RELEASE_URL)
    #Getting the version and checksum from the Yaml file
    CONTENTS = REPO.get_contents(FILE_PATH, BRANCH_NAME)
    RUNNER_VERSION = re.search('runnerVersion="(.*)"', CONTENTS.decoded_content.decode())
    RUNNER_CHECKSUM = re.search('runnerCheckSum="(.*)"', CONTENTS.decoded_content.decode())

    REPLACED_VERSION = CONTENTS.decoded_content.decode().replace(RUNNER_VERSION.group(1), RESPONSE.json()['name'])

    REPLACED_CHECKSUM = REPLACED_VERSION.replace(RUNNER_CHECKSUM.group(1), re.search('<!-- BEGIN SHA linux-x64 -->(.*)<!-- END SHA linux-x64 -->', str(RESPONSE.json()['body'])).group(1))

    print("changing the version and checksum with the latest release verion and checksum" )

    BLOB1 = REPO.create_git_blob(REPLACED_CHECKSUM, "utf-8")
    ELEMENT = github.InputGitTreeElement(path=FILE_PATH, mode='100644', type='blob', sha=BLOB1.sha)

    BRANCH_SHA = REPO.get_branch(BRANCH_NAME).commit.sha

    BASE_TREE = REPO.get_git_tree(sha=BRANCH_SHA)
    TREE = REPO.create_git_tree([ELEMENT], BASE_TREE)
    PARENT = REPO.get_git_commit(sha=BRANCH_SHA)

    print("commiting the changes to the git repo")
    COMMIT = REPO.create_git_commit("Version and checksum updated", TREE, [PARENT])
    BRANCH_REFS = REPO.get_git_ref("heads/"+BRANCH_NAME)
    BRANCH_REFS.edit(sha=COMMIT.sha)

    print("creating the PR to the changes")
    PR = REPO.create_pull(title="New pull Request", body="body", head=BRANCH_NAME, base="main")

    return str(PR.number)

def main():
    ACCESS_TOKEN = CLIENT.get_parameter(Name='/test/check/access_token', WithDecryption=True)["Parameter"]["Value"]
    GIT = Github(ACCESS_TOKEN)
    print("check", ACCESS_TOKEN)
    REPO = GIT.get_repo(f"{USER_NAME}/{REPO_NAME}")
    #Getting the version and checksum of the latest release.
    RESPONSE = requests.get(RELEASE_URL)
    #Getting the version and checksum from the Yaml file
    CONTENTS = REPO.get_contents(FILE_PATH, BRANCH_NAME)
    RUNNER_VERSION = re.search('runnerVersion="(.*)"', CONTENTS.decoded_content.decode())
    print("checking if you are on the latest version")
    if RUNNER_VERSION.group(1) != RESPONSE.json()['name']:
        PR_NUMBER = doGitOperations(ACCESS_TOKEN)
        print("sending notification to the Slack")
        sendSlackNotification(PR_NUMBER)
        print("sending notification to the Mail")
        sendEmailNotification(PR_NUMBER)
    else:
        print("You are on the latest version")

if __name__ == "__main__":
    main()
