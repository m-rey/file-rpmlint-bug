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
osc_user_emails = {}
osc_group_emails = {}
try:
    osc_package_emails = json.load(open("osc_package_emails.dict"))
except:
    pass

try:
    osc_user_emails = json.load(open("osc_user_emails.dict"))
except:
    pass

try:
    osc_group_emails = json.load(open("osc_group_emails.dict"))
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
    #print(f"\n[debg] looking up package '{package}'")
    if package in osc_package_emails:
        #print(f"[dict] responsible for package \"{package}\" is '{osc_package_emails[package]}'")
        return osc_package_emails[package]

    else:
        email_list = set()
        #print(f"[_osc] looking up '{package}' in osc...")
        package_osc_out = subprocess.run(['osc', 'api', f'/search/owner?binary={package}'],
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # get xml result of query
        if package_osc_out.returncode == 0:
            package_osc_xml = ET.fromstring(package_osc_out.stdout.decode('utf-8'))
            if package_osc_xml.findall("owner/*[@role='bugowner']"):
                #print(f"[debg] package '{package}' has bugowner")
                xml_list = package_osc_xml.findall("owner/*[@role='bugowner']")
            elif package_osc_xml.findall("owner/*[@role='maintainer']"):
                #print(f"[debg] package '{package}' has maintainer")
                xml_list = package_osc_xml.findall("owner/*[@role='maintainer']")
            else:
                #print(f"[!!!!] package '{package}' has no bugowner/maintainer!")
                return [""]

            user_name_list = [p.get("name") for p in xml_list if p.tag == "person"]
            group_name_list = [g.get("name") for g in xml_list if g.tag == "group"]

            for user in user_name_list:
                if user in osc_user_emails:
                    #print(f"[dict] getting email from listed user '{user}'")
                    user_email_list = osc_user_emails[user]
                else:
                    #print(f"[_osc] getting email from listed user '{user}'")
                    user_email_list = get_emails_from_name(user)
                    osc_user_emails.update({user: user_email_list})
                    json.dump(osc_user_emails, open("osc_user_emails.dict", 'w'))

                email_list.update(user_email_list)

            for group in group_name_list:
                if group in osc_group_emails:
                    #print(f"[dict] getting email from listed group '{group}'")
                    group_email_list = osc_group_emails[group]
                else:
                    #print(f"[_osc] getting email from listed group '{group}'")
                    group_email_list = get_emails_from_name(group, "group")
                    osc_group_emails.update({group: group_email_list})
                    json.dump(osc_group_emails, open("osc_group_emails.dict", 'w'))

                email_list.update(group_email_list)

            #print(f"[debg] responsible for package \"{package}\" is '{list(email_list)}'")
            osc_package_emails.update({package: list(email_list)})
            json.dump(osc_package_emails, open("osc_package_emails.dict", 'w'))
            return list(email_list)


def main(arguments):
    config = ConfigParser()
    config.read(arguments.config)

    # if args.urlrpmlint is not None:
    #     config['BuildCheckStatistics_instance']['url'] = args.urlrpmlint
    # if args.project is not None:
    #     config['BuildCheckStatistics_instance']['project'] = args.project
    # if args.arch is not None:
    #     config['BuildCheckStatistics_instance']['architecture'] = args.arch
    # if args.repo is not None:
    #     config['BuildCheckStatistics_instance']['repository'] = args.repo
    # if args.urlbugzilla is not None:
    #     config['Bugzilla_instance']['url'] = args.urlbugzilla
    # if args.username is not None:
    #     config['Bugzilla_instance']['login_username'] = args.username
    # if args.password is not None:
    #     config['Bugzilla_instance']['login_password'] = args.password

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
            package_emails = get_package_bugowner_emails(package)
            package_data.update(
                {package: dict(bug_config=dict(assigned_to=package_emails[0],
                                               cc=package_emails[1:],
                                               product=config['Bugzilla_instance']['bug_product'],
                                               component=config['Bugzilla_instance']['bug_component'],
                                               version=config['Bugzilla_instance']['bug_version'],
                                               summary=config['Bugzilla_instance']['package_bug_summary'],
                                               description=config['Bugzilla_instance']['package_bug_description'],
                                               id=''
                                               ))})

        data = {error: dict(bug_config=dict(assigned_to=config['Bugzilla_instance']['parent_bug_owner'],
                                            cc=config['Bugzilla_instance']['parent_bug_cc'],
                                            product=config['Bugzilla_instance']['bug_product'],
                                            component=config['Bugzilla_instance']['bug_component'],
                                            version=config['Bugzilla_instance']['bug_version'],
                                            summary=config['Bugzilla_instance']['parent_bug_summary'],
                                            description=config['Bugzilla_instance']['parent_bug_description'],
                                            id=''
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
    #parser_bugzilla_login = parser.add_argument_group()
    parser.add_argument("config", metavar="CONFIG_FILE", help="configuration file with settings")
    parser_flags.add_argument("-v", "--verbosity", help="increase output verbosity", action="count", default=0)
    parser_flags.add_argument("-q", "--quiet", help="try to be as quiet as possible", action="store_true")
    #parser.add_argument("--urlrpmlint", metavar="BCS_INSTANCE", help="URL of BuildCheckStatistics (rpmlint) instance")
    #parser.add_argument("-p", "--project", help="name of project")
    #parser.add_argument("-a", "--arch", metavar="ARCHITECTURE", help="architecture type")
    #parser.add_argument("-r", "--repo", metavar="REPOSITORY", help="name of repository")
    #parser.add_argument("--urlbugzilla", metavar="BUGZILLA_INSTANCE", help="URL of bugzilla instance")
    #parser_bugzilla_login.add_argument("--username", help="username for bugzilla instance")
    #parser_bugzilla_login.add_argument("--password", help="password for bugzilla instance")
    #parser.add_argument("-b", "--bug", help="bugzilla parent bug id for generated bug reports", type=int)
    parser.add_argument("--no-email-cache", help="don't use cached emails", action="store_true")
    parser.add_argument("--remove-email-cache", help="don't use cached emails", action="store_true")

    args = parser.parse_args()
    sys.exit(main(args))
