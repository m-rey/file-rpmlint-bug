import argparse
import bugzilla
from configparser import ConfigParser
import json
import toml
from os.path import join
import sys
import urllib.parse
import urllib.request

__author__ = "Martin Rey <mrey@suse.de>"


def bugzilla_init(apiurl, username, password):
    apiurl_split = urllib.parse.urlsplit(apiurl)
    apiurl = urllib.parse.urlunsplit((apiurl_split.scheme, username + ":" + password + "@" + apiurl_split.netloc,
                                      apiurl_split.path, "", ""))
    bugzilla_api = bugzilla.Bugzilla(apiurl)
    bugzilla_api.bug_autorefresh = True
    return bugzilla_api


def get_rpmlint_package_list(urlrpmlint, project, arch, repo, rpmlint_error):
    rpmlint_url = join(urlrpmlint, project, arch, repo + "?rule=" + rpmlint_error + "&format=txt")
    with urllib.request.urlopen(rpmlint_url) as response:
        packages = response.read().decode("utf-8").splitlines()
    return packages


def get_rpmlint_error_list(urlrpmlint, project, arch, repo):
    rpmlint_url = join(urlrpmlint, "rules", project, arch, repo + "?format=txt")
    with urllib.request.urlopen(rpmlint_url) as response:
        errors = response.read().decode("utf-8").splitlines()
    return errors


def main(args):
    config = ConfigParser()
    if args.config:
        config.read(args.config)

    if args.urlrpmlint is not None:
        config['BuildCheckStatistics_instance']['url'] = args.urlrpmlint
    if args.project is not None:
        config['BuildCheckStatistics_instance']['project'] = args.project
    if args.arch is not None:
        config['BuildCheckStatistics_instance']['architecture'] = args.arch
    if args.repo is not None:
        config['BuildCheckStatistics_instance']['repository'] = args.repo
    if args.urlbugzilla is not None:
        config['Bugzilla_instance']['url'] = args.urlbugzilla
    if args.username is not None:
        config['Bugzilla_instance']['login_username'] = args.username
    if args.password is not None:
        config['Bugzilla_instance']['login_password'] = args.password
    if args.bug is not None:
        config['Bugzilla_bug']['blocks'] = str(args.bug)

    errors = get_rpmlint_error_list(
        config['BuildCheckStatistics_instance']['url'],
        config['BuildCheckStatistics_instance']['project'],
        config['BuildCheckStatistics_instance']['architecture'],
        config['BuildCheckStatistics_instance']['repository']
    )


    for error in errors:
        packages = get_rpmlint_package_list(
            config['BuildCheckStatistics_instance']['url'],
            config['BuildCheckStatistics_instance']['project'],
            config['BuildCheckStatistics_instance']['architecture'],
            config['BuildCheckStatistics_instance']['repository'],
            error
            )
        package_data = {}
        for package in packages:
            package_data.update({package: dict(bug_config=dict(owner=config['Bugzilla_instance']['parent_bug_owner'],
                                               product=config['Bugzilla_instance']['parent_bug_product'],
                                               component=config['Bugzilla_instance']['parent_bug_component'],
                                               summary=config['Bugzilla_instance']['parent_bug_summary'],
                                               version=config['Bugzilla_instance']['parent_bug_version'],
                                               description=config['Bugzilla_instance']['parent_bug_description'],
                                               bug_id=''
                                               ))})

        data = {error: dict(bug_config=dict(owner=config['Bugzilla_instance']['parent_bug_owner'],
                                            product=config['Bugzilla_instance']['parent_bug_product'],
                                            component=config['Bugzilla_instance']['parent_bug_component'],
                                            summary=config['Bugzilla_instance']['parent_bug_summary'],
                                            version=config['Bugzilla_instance']['parent_bug_version'],
                                            description=config['Bugzilla_instance']['parent_bug_description'],
                                            bug_id=''
                                            ),
                            packages=package_data
                            )
                }


        # data[error]["bug_config"]["owner"] = config["Bugzilla_instance"]["parent_bug_owner"]
        # data[error]["bug_config"]["product"] = config["Bugzilla_instance"]["parent_bug_product"]
        # data[error]["bug_config"]["component"] = config["Bugzilla_instance"]["parent_bug_component"]
        # data[error]["bug_config"]["summary"] = config["Bugzilla_instance"]["parent_bug_summary"]
        # data[error]["bug_config"]["version"] = config["Bugzilla_instance"]["parent_bug_version"]
        # data[error]["bug_config"]["description"] = config["Bugzilla_instance"]["parent_bug_description"]

        print(json.dumps(data, indent=4, sort_keys=True))

    # bzapi = bugzilla_init(config["Bugzilla_instance"]["url"], config["Bugzilla_instance"]["login_username"],
    #                       config["Bugzilla_instance"]["login_password"])
    # bug_create_info = bzapi.build_createbug()


if __name__ == '__main__':
    # file-rpmlint-bug --urlrpmlint https://rpmlint.opensuse.org --project openSUSE:Factory --arch x86_64 \
    # --repo standard --username admin --password 1234bugzilla --urlbugzilla https://bugzilla.opensuse.org --bug 23154 \
    # non-standard-group --config config.ini

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
