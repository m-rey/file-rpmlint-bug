import argparse
import bugzilla
from configparser import ConfigParser
import json
from os.path import join
import requests
import sys
import urllib.parse

__author__ = "Martin Rey <mrey@suse.de>"


def bugzilla_init(apiurl, username, password):
    apiurl_split = urllib.parse.urlsplit(apiurl)
    apiurl = urllib.parse.urlunsplit((apiurl_split.scheme, username + ":" + password + "@" + apiurl_split.netloc,
                                      apiurl_split.path, "", ""))
    bugzilla_api = bugzilla.Bugzilla(apiurl)
    bugzilla_api.bug_autorefresh = True
    return bugzilla_api


def get_rpmlint_json(urlrpmlint, project, arch, repo, rpmlint_error):
    rpmlint_path = join(project, arch, repo)
    rpmlint_url_split = urllib.parse.urlsplit(urlrpmlint)
    rpmlint_url = urllib.parse.urlunsplit((rpmlint_url_split.scheme, rpmlint_url_split.netloc, rpmlint_path,
                                           "rule=" + rpmlint_error + "&format=json", ""))
    rpmlint_json_text = requests.get(rpmlint_url).text
    try:
        rpmlint_json = json.loads(rpmlint_json_text)
    except json.decoder.JSONDecodeError as e:
        print("JSONDecodeError: Wrong input params?")
        sys.exit()
    return rpmlint_json


def main(args):

    config = ConfigParser()
    if args.config:
        config.read(args.config)

    if args.urlrpmlint is not None:
        config["BuildCheckStatistics_instance"]["url"] = args.urlrpmlint
    if args.project is not None:
        config["BuildCheckStatistics_instance"]["project"] = args.project
    if args.arch is not None:
        config["BuildCheckStatistics_instance"]["architecture"] = args.arch
    if args.repo is not None:
        config["BuildCheckStatistics_instance"]["repository"] = args.repo
    if args.urlbugzilla is not None:
        config["Bugzilla_instance"]["url"] = args.urlbugzilla
    if args.username is not None:
        config["Bugzilla_instance"]["username"] = args.username
    if args.password is not None:
        config["Bugzilla_instance"]["password"] = args.password
    if args.bug is not None:
        config["Bugzilla_bug"]["blocks"] = str(args.bug)

    rpmlint_json = get_rpmlint_json(config["BuildCheckStatistics_instance"]["url"],
                                    config["BuildCheckStatistics_instance"]["project"],
                                    config["BuildCheckStatistics_instance"]["architecture"],
                                    config["BuildCheckStatistics_instance"]["repository"],
                                    args.rpmlint_error)
    packages = []
    for p in rpmlint_json:
        packages.append(p["package"])
    print(packages)

    bugzilla_api = bugzilla_init(config["Bugzilla_instance"]["url"],
                                 config["Bugzilla_instance"]["username"],
                                 config["Bugzilla_instance"]["password"])
    parent_bug = bugzilla_api.getbug(config["Bugzilla_bug"]["blocks"])
    print(parent_bug)

    # for package in packages:
    #     data_child_bug = bugzilla_api.build_createbug(**dict(config.items("Bugzilla_bug")))
    #     bugzilla_api.createbug(data_child_bug)

if __name__ == '__main__':
    # file-rpmlint-bug --urlrpmlint https://rpmlint.opensuse.org --project openSUSE:Factory --arch x86_64 \
    # --repo standard --username admin --password 1234bugzilla --urlbugzilla https://bugzilla.opensuse.org --bug 23154 \
    # non-standard-group

    parser = argparse.ArgumentParser(description='generate bug reports for rpmlint listings')
    parser_flags = parser.add_mutually_exclusive_group()
    parser_bugzilla_login = parser.add_argument_group()
    parser.add_argument("rpmlint_error", metavar="ERRORTYPE", help="rpmlint error type to create bug reports for")
    parser_flags.add_argument("-v", "--verbosity", help="increase output verbosity", action="count", default=0)
    parser_flags.add_argument("-q", "--quiet", help="try to be as quiet as possible", action="store_true")
    parser.add_argument("--urlrpmlint", metavar="BCS_INSTANCE", help="URL of BuildCheckStatistics (rpmlint) instance")
    parser.add_argument("-p", "--project", help="name of project")
    parser.add_argument("-a", "--arch", metavar="ARCHITECTURE", help="architecture type")
    parser.add_argument("-r", "--repo", metavar="REPOSITORY", help="name of repository")
    parser.add_argument("--urlbugzilla", metavar="BUGZILLA_INSTANCE", help="URL of bugzilla instance")
    parser_bugzilla_login.add_argument("--username", help="username for bugzilla instance")
    parser_bugzilla_login.add_argument("--password", help="password for bugzilla instance")
    parser.add_argument("-b", "--bug", help="bugzilla parent bug id for generated bug reports", type=int)
    parser.add_argument("-c", "--config", metavar="CONFIG_FILE", help="configuration file with further settings;"
                                                                      " passed arguments will overwrite config")

    args = parser.parse_args()
    sys.exit(main(args))
