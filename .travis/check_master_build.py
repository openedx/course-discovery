"""
Adds a status check to a github PR which check whether or not the last
build on master passed or failed.

Uses the Travis API to get the latest master build state and build url.
The Github Status API is then used to add a status to the given commit
hash.

A github_status_token and travis_api_token must be set up for this
script to work. These can be configured in the travis settings
(https://docs.travis-ci.com/user/environment-variables/#Defining-Variables-in-Repository-Settings)
or passed as secure parameters in the travis.yml file
(https://docs.travis-ci.com/user/environment-variables/#Defining-encrypted-variables-in-.travis.yml).
The commit hash is provided by a Travis build as $TRAVIS_COMMIT.

Example usage:
     python .travis/check_master_build.py --commit $TRAVIS_COMMIT \
     --github_status_token $GITHUB_STATUS_TOKEN --travis_api_token $TRAVIS_API_TOKEN

"""
import argparse
import json
import logging
import sys
import time
import urllib.request
import urllib.parse

CHECK_MASTER_STATUS_TIMEOUT_IN_MINUTES = 25  # Should be set to how long a build usually takes.
TRAVIS_REPO_ID = '6521695'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Check Master Build Log")


def add_status_to_commit(commit, github_token, travis_token):
    """Adds the latest master's build state to the commit's PR status checks"""
    master_status, href = get_master_build_data(travis_token)
    payload = build_status_api_payload(master_status, href)
    update_github_status(commit, github_token, payload)


def update_github_status(commit_hash, git_token, payload):
    """
    Update PR's for the given commit_hash

    Args:
        commit_hash (str): Status for the latest master branch build.
        git_token (str): Token for using the github status API
        payload (dict): Payload to be sent to github status API

    Returns:
        dict: Dict used as the POST data for the Github status API
    """
    logger.info("Sending Status API request for commit hash {}".format(commit_hash))
    logger.info("POST data for Status API: {}".format(payload))

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'token {}'.format(git_token),
    }

    url = 'https://api.github.com/repos/edx/course-discovery/statuses/{}'.format(commit_hash)
    data = json.dumps(payload).encode('utf-8')
    r = urllib.request.Request(url=url, headers=headers, data=data)
    response = urllib.request.urlopen(r)
    if response.code == 201:
        logger.info("Github status update success")


def build_status_api_payload(master_build_status, href):
    """
    Build the appropriate POST data for the github status api.

    Args:
        master_build_status (str): Status for the latest master branch build.
        href (str): HREF for the laste master branch build.

    Returns:
        dict: Dict used as the POST data for the Github status API
    """
    if master_build_status == "passed":
        state = "success"
        message = "The latest master branch has passed CI"
    elif master_build_status == "failed":
        state = "failure"
        message = "The latest master branch has failed CI"
    elif master_build_status == "started":
        state = "pending"
        message = "The latest master branch is still pending"
    else:
        state = "pending"  # Do not fail the build if build status is unknown.
        message = "Cannot retrieve the status of the master branch build. "

    if href and "builds" not in href:
        href = "/builds" + href.split("build")[1]  # In case Travis API returns the wrong HREF.
    target_url = "https://travis-ci.org/edx/course-discovery" + href

    return {
        'state': state,
        'target_url': target_url,
        'description': message,
        'context': "Master branch status"
    }


def get_master_build_data(travis_token):
    """
    Retrieves the build status and href of the latest master build

    This method will keep trying until it receives a finished state or
    times out.
    """
    finished_state = ['passed', 'failure']
    attempts = 5
    timeout = (CHECK_MASTER_STATUS_TIMEOUT_IN_MINUTES / attempts) * 60

    status, href = call_travis_api(travis_token)

    while status not in finished_state and attempts > 1:
        logger.info("Attempting to get master build status {} more time(s).".format(attempts - 1))
        time.sleep(timeout)
        status, href = call_travis_api(travis_token)
        attempts -= 1

    return status, href


def call_travis_api(travis_token):
    """
    Calls travis API for the latest master branch build data

    Args:
        travis_token (str): Travis API token

    Returns:
        build_state, href: The build state of the latest master branch and
                            the href of the build.
    """
    headers = {
        "Travis-API-Version": "3",
        "Authorization": "token {}".format(travis_token),
    }
    url = "http://api.travis-ci.org/repo/{repo_id}/branch/master".format(repo_id=TRAVIS_REPO_ID)

    req = urllib.request.Request(url=url, headers=headers)
    response = urllib.request.urlopen(req, timeout=10)

    if response.code != 200:
        logger.error("Travis API query for master branch status was unsuccessful: {}".format(response.status_code))
        return None, ""
    response = response.read()
    try:
        response_dict = json.loads(response.decode('utf-8'))
        build_state = response_dict['last_build']['state']
        build_href = response_dict['last_build']['@href']
        logger.info("Current master branch build state is '{}'".format(build_state))
        return build_state, build_href
    except Exception as ex:
        logger.error("Unexpected Travis API response: {} {}".format(type(ex).__name__, ex.args))
        logger.error(response)
        logger.error("URL: {}".format(url))
        return None, ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit")
    parser.add_argument("--github_status_token", required=True, help="Github token with Status API permissions.")
    parser.add_argument("--travis_api_token", required=True, help="Travis API token used for fetching repository data.")
    args = parser.parse_args()

    add_status_to_commit(args.commit, args.github_status_token, args.travis_api_token)
    sys.exit(0)
