import argparse
import bugzilla
from configparser import ConfigParser
import json
import xml.etree.ElementTree as ET
from os.path import join
import sys
import urllib.parse
import urllib.request
import subprocess

__author__ = "Martin Rey <mrey@suse.de>"

osc_package_emails = {}
try:
    osc_package_emails = json.load(open("osc_package_maintainers.dict"))
except:
    pass


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


def get_emails_from_name(username, name_type="person"):
    email_list = []
    osc_out = subprocess.run(['osc', 'api', f'/{name_type}/{username}'], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    if osc_out.returncode == 0:
        osc_xml = ET.fromstring(osc_out.stdout.decode('utf-8'))
        email_xml_list = osc_xml.findall("email")
        email_list.extend([email.text for email in email_xml_list])
        if (not email_list) and (name_type == "group"):
            if osc_xml.findall("maintainer"):
                xml_list = osc_xml.findall("maintainer")
            else:
                xml_list = osc_xml.findall("person/person")
            user_list = [user.get("userid") for user in xml_list]
            for userid in user_list:
                email_list.extend(get_emails_from_name(userid, name_type="person"))
        return email_list


def get_package_bugowner_emails(package):
    print(f"\n[debg] looking up package '{package}'")
    if package in osc_package_emails:
        print(f"[dict] responsible for package \"{package}\" is '{osc_package_emails[package]}'")
        return osc_package_emails[package]

    else:
        email_list = set()
        print(f"[debg] looking up '{package}' in osc...")
        package_osc_out = subprocess.run(['osc', 'api', f'/search/owner?binary={package}'],
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # get xml result of query
        print("[debg] ... loaded")
        if package_osc_out.returncode == 0:
            package_osc_xml = ET.fromstring(package_osc_out.stdout.decode('utf-8'))
            if package_osc_xml.findall("owner/*[@role='bugowner']"):
                print(f"[debg] package '{package}' has bugowner")
                xml_list = package_osc_xml.findall("owner/*[@role='bugowner']")
            else:
                print(f"[debg] package '{package}' has maintainer")
                xml_list = package_osc_xml.findall("owner/*[@role='maintainer']")

            user_name_list = [p.get("name") for p in xml_list if p.tag == "person"]
            group_name_list = [g.get("name") for g in xml_list if g.tag == "group"]
            for user in user_name_list:
                print(f"[debg] getting email from listed user '{user}'")
                email_list.update(get_emails_from_name(user))
                print("[debg] ... loaded")

            for group in group_name_list:
                print(f"[debg] getting email from listed group '{group}'")
                email_list.update(get_emails_from_name(group, "group"))
                print("[debg] ... loaded")

            print(f"[_osc] responsible for package \"{package}\" is '{list(email_list)}'")
            osc_package_emails.update({package: list(email_list)})
            json.dump(osc_package_emails, open("osc_package_maintainers.dict", 'w'))
            return list(email_list)

        #                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # userlist = ["-"]  # default: no users
        # osc_out = subprocess.run(["osc", "maintainer", "-Be", package],
        #                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        #
        # if osc_out.returncode != 0:
        #     osc_out = subprocess.run(["osc", "maintainer", "-B", package],
        #                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        #     userlist = osc_out.stdout.decode('utf-8').strip().splitlines()[-1].strip().split(", ")
        #     if
        #
        #
        #
        # if osc_out.returncode != 0:  # get maintainer email if no bugowner email
        #     osc_out = subprocess.run(["osc", "maintainer", "-e", package],
        #                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # if osc_out.returncode == 0:
        #     userlist = osc_out.stdout.decode('utf-8').strip().splitlines()[-1].strip().split(", ")
        #
        # # if userlist[0] == "-":  # if userlist still has no email addresses, get the names instead
        # #     osc_out = subprocess.run(["osc", "maintainer", "-B", package],
        # #                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # #     if osc_out.returncode != 0:  # get maintainer name if no bugowner name
        # #         osc_out = subprocess.run(["osc", "maintainer", package],
        # #                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # #     if osc_out.returncode == 0:
        # #         userlist = [mail for mail in
        # #                     osc_out.stdout.decode('utf-8').strip().splitlines()[-1].strip().split(", ")]
        #
        # if userlist[0] != "-":
        #     userlist = [mail for mail in userlist if mail != "-"]  # remove any "-" if there is an user entry before "-"
        # else:
        #     userlist = [""]
        #
        # print(f"[_osc] maintainer of package \"{package}\" is \"{userlist}\"")
        # osc_package_maintainers.update({package: userlist})
        # json.dump(osc_package_maintainers, open("osc_package_maintainers.dict", 'w'))



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
            package_data.update(
                {package: dict(bug_config=dict(owner=get_package_bugowner_emails(package)[0],
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

        # print(json.dumps(data, indent=4, sort_keys=True))

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
