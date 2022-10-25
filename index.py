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
username = 'geethapalyam'
#Git Repo Name
repoName = 'palyam_test'
#Git access Token
Access_token = "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"
#release URL https://api.github.com/repos/{owner}/{repo}/releases/latest
Rekease_url = "https://api.github.com/repos/actions/runner/releases/latest"
#yaml File path
file_path = "runner-test.txt"
#webhook url for slack notification
webhook_url = "https://hooks.slack.com/services/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"

#sender email for the mail notification.
#sender_email = "geetha.palyam@gmail.com"
# Gmail app password
# password = 'kndtknppilckttof'
client = boto3.client('ssm')  # Creates an Amazon Simple Systems Manager client
# webhook_url = client.get_parameter(Name='/test/check/webhook_url', WithDecryption=True)["Parameter"]["Value"]
sender_email = client.get_parameter(Name='/test/check/sender_email', WithDecryption=True)["Parameter"]["Value"]
password = client.get_parameter(Name='/test/check/sender_email_password', WithDecryption=True)["Parameter"]["Value"]

print("sender_email", sender_email)
print("password", password)
# Email notification reciever
receiver_email = "palyamgeetha@gmail.com"
#branch name
branch_name = "runner"
#slack channel receives notification 
channel_name = "#git-script"

g = Github(Access_token)

repo = g.get_repo('{}/{}'.format(username, repoName))
print(username,password)

#Getting the version and checksum of the latest release.
response = requests.get(Rekease_url)
# print('version', response.json()['name'])
# print("checksum" ,re.search('<!-- BEGIN SHA linux-x64 -->(.*)<!-- END SHA linux-x64 -->', str(response.json()['body'])).group(1))

#Getting the version and checksum from the Yaml file
contents = repo.get_contents(file_path, branch_name)
runnerVersion = re.search('runnerVersion="(.*)"', contents.decoded_content.decode())
runnerCheckSum = re.search('runnerCheckSum="(.*)"', contents.decoded_content.decode())

print("checking if you are on the latest version")
if runnerVersion.group(1) != response.json()['name']:
    replaced_Version = contents.decoded_content.decode().replace(runnerVersion.group(1), response.json()['name'])

    replaced_Checksum = replaced_Version.replace(runnerCheckSum.group(1), re.search('<!-- BEGIN SHA linux-x64 -->(.*)<!-- END SHA linux-x64 -->', str(response.json()['body'])).group(1))

    print("changing the version and checksum with the latest release verion and checksum" )

    blob1 = repo.create_git_blob(replaced_Checksum, "utf-8")
    element1 = github.InputGitTreeElement(path=file_path, mode='100644', type='blob', sha=blob1.sha)

    branch_sha = repo.get_branch(branch_name).commit.sha

    base_tree = repo.get_git_tree(sha=branch_sha)
    tree = repo.create_git_tree([element1], base_tree)
    parent = repo.get_git_commit(sha=branch_sha)

    print("commiting the changes to the git repo")
    commit = repo.create_git_commit("Version and checksum updated", tree, [parent])
    branch_refs = repo.get_git_ref("heads/"+branch_name)
    branch_refs.edit(sha=commit.sha)

    print("creating the PR to the changes")
    pr = repo.create_pull(title="New pull Request", body="body", head=branch_name, base="main")

    print("sending notification to the Slack")
    # Code to send alert to the slack channel
    if __name__ == '__main__':
        url = webhook_url
        message = ("new Pull Request Link: https://github.com/{}/{}/pull/{}".format(username, repoName, pr.number))
        title = (f"New Incoming pull Request :zap:")
        slack_data = {
            "username": "NotificationBot",
            "icon_emoji": ":satellite:",
            "channel" : channel_name,
            "attachments": [
                {
                    "color": "#9733EE",
                    "fields": [
                        {
                            "title": title,
                            "value": message,
                            "short": "false",
                        }
                    ]
                }
            ]
        }
        byte_length = str(sys.getsizeof(slack_data))
        headers = {'Content-Type': "application/json", 'Content-Length': byte_length}
        response = requests.post(url, data=json.dumps(slack_data), headers=headers)
        if response.status_code != 200:
            raise Exception(response.status_code, response.text)

    # Code to send alert via email
    print("sending notification to the Mail")
    smtp_server = "smtp.gmail.com"
    port = 587  # For starttls

    url = "https://github.com/{}/{}/pull/{}".format(username, repoName, pr.number)
    message = '''hello

    A new Pull Request has been created

    The URL is: '''+url

    # Create a secure SSL context
    context = ssl.create_default_context()

    # Try to log in to server and send email
    try:
        server = smtplib.SMTP(smtp_server,port)
        server.ehlo() # Can be omitted
        server.starttls(context=context) # Secure the connection
        server.ehlo() # Can be omitted
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message)
    except Exception as e:
        # Print any error messages to stdout
        print(e)
    finally:
        server.quit()
else:
    print("You are on the latest version")
    
