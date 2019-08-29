# coding=utf-8
import argparse
import json
import logging
import subprocess
import sys
import urllib.parse
import urllib.request
from configparser import ConfigParser
from os import path, remove, scandir
from string import Template
from xml.etree.ElementTree import fromstring

import bugzilla

__author__ = "Martin Rey <mrey@suse.de>"

osc_package_emails = {}
osc_user_emails = {}
osc_group_emails = {}
packages_without_bugowner = set()


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger()

# file-rpmlint-bug --pull -c config.ini data.json
parser = argparse.ArgumentParser(description='generate bug reports for rpmlint listings in 2 steps.')
parser_flags = parser.add_mutually_exclusive_group()
parser_operation = parser.add_mutually_exclusive_group()
parser_flags.add_argument("-v", "--verbosity", help="increase output verbosity (-v, -vv, -vvv)",
                          action="count", default=0)
parser_operation.add_argument("--pull", help="pull information from relevant sources to generate data file",
                              dest="operation", action="store_const", const="pull")
parser_operation.add_argument("--push", help="push information from data file to bugzilla", dest="operation",
                              action="store_const", const="push")
parser.add_argument("--config", "-c", metavar="CONFIG_FILE", help="configuration file with settings")
parser.add_argument("file", metavar="JSON_FILE", help="filename of JSON data file to use")
parser.add_argument("--nocache", help="don't use cached package:email dictionary", action="store_true")
parser.add_argument("--removecache", help="remove cached package:email dictionary", action="store_true")
parser_operation.set_defaults(operation="pull")


def set_verbosity(args):
    if not args.verbosity:
       log.setLevel(logging.ERROR)
    elif args.verbosity == 1:
        log.setLevel(logging.WARNING)
    elif args.verbosity == 2:
        log.setLevel(logging.INFO)
    elif args.verbosity >= 3:
        log.setLevel(logging.DEBUG)


def bugzilla_init(apiurl, username, password):
    apiurl_split = urllib.parse.urlsplit(apiurl)
    apiurl = urllib.parse.urlunsplit((apiurl_split.scheme, username + ":" + password + "@" + apiurl_split.netloc,
                                      apiurl_split.path, "", ""))
    bugzilla_api = bugzilla.Bugzilla(apiurl)
    bugzilla_api.bug_autorefresh = True
    return bugzilla_api


def get_rpmlint_package_list(urlrpmlint, project, arch, repo, rpmlint_error):
    rpmlint_url = path.join(urlrpmlint, project, arch, repo + "?rule=" + rpmlint_error + "&format=txt")
    with urllib.request.urlopen(rpmlint_url) as response:
        packages = response.read().decode("utf-8").splitlines()
    return packages


def get_rpmlint_error_list(urlrpmlint, project, arch, repo):
    rpmlint_url = path.join(urlrpmlint, "rules", project, arch, repo + "?format=txt")
    with urllib.request.urlopen(rpmlint_url) as response:
        errors = response.read().decode("utf-8").splitlines()
    return errors


def get_emails_from_name(username, name_type="person"):
    email_list = []
    osc_out = subprocess.run(['osc', 'api', f'/{name_type}/{username}'], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    if osc_out.returncode == 0:
        osc_xml = fromstring(osc_out.stdout.decode('utf-8'))
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
    log.debug(f"looking up package '{package}'")
    if package in osc_package_emails:
        log.debug(f"package '{package}' is in cache")
        log.debug(f"'{osc_package_emails[package]}' is responsible for package '{package}'")
        return osc_package_emails[package]
    elif package in packages_without_bugowner:
        log.warning(f"package '{package}' is in cache, but has no bugowner/maintainer!")
        return [""]
    else:
        email_list = set()
        log.debug(f"looking up package '{package}' using osc")
        package_osc_out = subprocess.run(['osc', 'api', f'/search/owner?binary={package}'],
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # get xml result of query
        if package_osc_out.returncode == 0:
            package_osc_xml = fromstring(package_osc_out.stdout.decode('utf-8'))
            if package_osc_xml.findall("owner/*[@role='bugowner']"):
                log.debug(f"package '{package}' has bugowner")
                xml_list = package_osc_xml.findall("owner/*[@role='bugowner']")
            elif package_osc_xml.findall("owner/*[@role='maintainer']"):
                log.debug(f"package '{package}' has maintainer")
                xml_list = package_osc_xml.findall("owner/*[@role='maintainer']")
            else:
                log.warning(f"package '{package}' has no bugowner/maintainer!")
                log.debug(f"adding '{package}' to cache")
                packages_without_bugowner.add(package)
                return [""]

            user_name_list = [p.get("name") for p in xml_list if p.tag == "person"]
            group_name_list = [g.get("name") for g in xml_list if g.tag == "group"]

            for user in user_name_list:
                if user in osc_user_emails:
                    log.debug(f"user '{user}' is in cache")
                    log.debug(f"getting email from user '{user}'")
                    user_email_list = osc_user_emails[user]
                else:
                    log.debug(f"getting email from user '{user}' using osc")
                    user_email_list = get_emails_from_name(user)
                    osc_user_emails.update({user: user_email_list})
                    if not args.nocache:
                        with open("osc_user_emails.cache", "w") as osc_user_emails_file:
                            log.debug(f"saving data to cache file '{osc_user_emails_file.name}'")
                            json.dump(osc_user_emails, osc_user_emails_file)
                email_list.update(user_email_list)

            for group in group_name_list:
                if group in osc_group_emails:
                    log.debug(f"group '{group}' is in cache")
                    log.debug(f"getting email from group '{group}'")
                    group_email_list = osc_group_emails[group]
                else:
                    log.debug(f"getting email from group '{group}' using osc")
                    group_email_list = get_emails_from_name(group, "group")
                    osc_group_emails.update({group: group_email_list})
                    if not args.nocache:
                        with open("osc_group_emails.cache", "w") as osc_group_emails_file:
                            log.debug(f"saving data to cache file '{osc_group_emails_file.name}'")
                            json.dump(osc_group_emails, osc_group_emails_file)
                email_list.update(group_email_list)

            log.debug(f"'{list(email_list)}' is responsible for package '{package}'")
            osc_package_emails.update({package: list(email_list)})
            if not args.nocache:
                with open("osc_package_emails.cache", "w") as osc_package_emails_file:
                    log.debug(f"saving data to cache file '{osc_package_emails_file.name}'")
                    json.dump(osc_package_emails, osc_package_emails_file)
            return list(email_list)


def pull(template):
    global osc_package_emails
    global osc_user_emails
    global osc_group_emails
    
    config = ConfigParser(interpolation=None)
    config.read_string(template.template)
    # adapt program based on given flags
    if args.removecache:
        log.debug("removing cache")
        for file in scandir(path.dirname(path.abspath(sys.argv[0]))):
            if file.name.endswith(".cache"):
                remove(file.path)
                log.debug(f"'{file.name}' removed")
    if not args.nocache:
        try:
            with open("osc_package_emails.cache", "r") as osc_package_emails_file:
                log.debug(f"load cache file {osc_package_emails_file.name}")
                osc_package_emails = json.load(osc_package_emails_file)
        except IOError:
            osc_package_emails = {}
        try:
            with open("osc_user_emails.cache", "r") as osc_user_emails_file:
                log.debug(f"load cache file {osc_user_emails_file.name}")
                osc_user_emails = json.load(osc_user_emails_file)
        except IOError:
            osc_user_emails = {}
        try:
            with open("osc_group_emails.cache", "r") as osc_group_emails_file:
                log.debug(f"load cache file {osc_group_emails_file.name}")
                osc_group_emails = json.load(osc_group_emails_file)
        except IOError:
            osc_group_emails = {}
    else:
        log.debug("not using cache because --nocache flag is set")

    # get list of rpmlint errors
    log.debug("get rpmlint error type list")
    parent_errors = get_rpmlint_error_list(
        config['BuildCheckStatistics_instance']['url'],
        config['BuildCheckStatistics_instance']['project'],
        config['BuildCheckStatistics_instance']['architecture'],
        config['BuildCheckStatistics_instance']['repository']
    )

    # import file if it exists, otherwise create a new one
    try:
        with open(args.file, 'r') as jsonfile:
            log.debug(f"load existing data file '{jsonfile.name}'")
            data = json.load(jsonfile)
    except FileNotFoundError:
        data = {}

    # now we want to structure our information, add new entries and dump it to a file

    # iterate through rpmlint error list
    for parent_error in parent_errors:

        # create parent bug dict if it doesn't exist
        if parent_error not in data:
            log.debug(f"rpmlint error '{parent_error}' is not in data")
            log.debug("applying template to generate config")
            config.read_string(template.safe_substitute(rpmlint_error_name=parent_error))
            data.update({
                parent_error: {
                    'bug_config': {
                        'assigned_to': config['Bugzilla_instance']['parent_bug_assigned_to'],
                        'cc': config['Bugzilla_instance']['parent_bug_cc'],
                        'product': config['Bugzilla_instance']['bug_product'],
                        'component': config['Bugzilla_instance']['bug_component'],
                        'version': config['Bugzilla_instance']['bug_version'],
                        'summary': config['Bugzilla_instance']['parent_bug_summary'],
                        'description': config['Bugzilla_instance']['parent_bug_description'],
                        'id': ''},
                    "packages": {}}})

            with open(args.file, 'w') as outfile:
                log.info(f"saving rpmlint error '{parent_error}'")
                log.debug(f"to file '{outfile.name}'")
                json.dump(data, outfile)
        else:
            log.info(f"rpmlint error '{parent_error}' already in data. skipping.")

        # get list of packages with a given rpmlint error
        log.debug(f"getting list of packages with rpmlint error '{parent_error}'")
        packages = get_rpmlint_package_list(
            config['BuildCheckStatistics_instance']['url'],
            config['BuildCheckStatistics_instance']['project'],
            config['BuildCheckStatistics_instance']['architecture'],
            config['BuildCheckStatistics_instance']['repository'],
            parent_error
        )

        # iterate through packages and add new packages
        for package in packages:
            if package not in data[parent_error]["packages"]:
                package_emails = get_package_bugowner_emails(package)
                log.debug("applying template to generate config")
                config.read_string(template.safe_substitute(rpmlint_error_name=parent_error, package_name=package))
                log.info(f"adding package info of '{package}' to rpmlint error '{parent_error}'")
                data[parent_error]["packages"].update({
                    package: {
                        'bug_config': {
                            'assigned_to': package_emails[0], 'cc': package_emails[1:],
                            'product': config['Bugzilla_instance']['bug_product'],
                            'component': config['Bugzilla_instance']['bug_component'],
                            'version': config['Bugzilla_instance']['bug_version'],
                            'summary': config['Bugzilla_instance']['package_bug_summary'],
                            'description': config['Bugzilla_instance']['package_bug_description'],
                            'id': ''}}
                })
            else:
                log.info(f"package info of '{package}' already in rpmlint error '{parent_error}'. skipping.")

        with open(args.file, 'w') as outfile:
            log.debug(f"saving packages data within data of rpmlint error '{parent_error}' to file '{outfile.name}'")
            json.dump(data, outfile)


def push(template):
    config = ConfigParser(interpolation=None)
    config.read_string(template.template)
    bzapi = bugzilla_init(config["Bugzilla_instance"]["url"], config["Bugzilla_instance"]["login_username"],
                          config["Bugzilla_instance"]["login_password"])

    with open(args.file, 'r') as jsonfile:
        data = json.load(jsonfile)

    # go through rpmlint error list and create parent bugs if they don't already exist
    for parent_error in data:
        if not data[parent_error]["bug_config"]["id"]:  # TODO: improve  by removing id:'' above and checking for id
            log.debug(f"rpmlint error '{parent_error}' has no bug in bugzilla yet")
            parent_bug_createinfo = bzapi.build_createbug(
                assigned_to=data[parent_error]["bug_config"]["assigned_to"],
                cc=data[parent_error]["bug_config"]["cc"],
                product=data[parent_error]["bug_config"]["product"],
                component=data[parent_error]["bug_config"]["component"],
                version=data[parent_error]["bug_config"]["version"],
                summary=data[parent_error]["bug_config"]["summary"],
                description=data[parent_error]["bug_config"]["description"])
            # created_parent_bug = bzapi.createbug(parent_bug_createinfo)
            log.info(f"created parent bug {parent_error} with bug id '{data[parent_error]['bug_config']['id']}'")
            data[parent_error]["bug_config"]["id"] = 1000  # TODO: remove
            # data[parent_error]["bug_config"].update("id"=created_parent_bug.id)
            with open(args.file, 'w') as jsonfile:
                log.debug(
                    f"saving bug id '{data[parent_error]['bug_config']['id']}' of rpmlint parent bug '{parent_error}'")
                json.dump(data, jsonfile)

        else:
            log.debug(f"rpmlint parent bug already created with id: '{data[parent_error]['bug_config']['id']}'")

        # go through packages of rpmlint error list and create child bugs if they don't already exist
        for package in data[parent_error]["packages"]:
            if not data[parent_error]["packages"][package]["bug_config"]["id"]:
                log.debug(f"package '{package}' has no bug in bugzilla regarding rpmlint error '{parent_error}' yet")
                child_bug_createinfo = bzapi.build_createbug(
                    assigned_to=data[parent_error]["packages"][package]["bug_config"]["assigned_to"],
                    cc=data[parent_error]["packages"][package]["bug_config"]["cc"],
                    product=data[parent_error]["packages"][package]["bug_config"]["product"],
                    component=data[parent_error]["packages"][package]["bug_config"]["component"],
                    version=data[parent_error]["packages"][package]["bug_config"]["version"],
                    summary=data[parent_error]["packages"][package]["bug_config"]["summary"],
                    description=data[parent_error]["packages"][package]["bug_config"]["description"],
                    blocks=data[parent_error]["bug_config"]["id"])
                # created_child_bug = bzapi.createbug(child_bug_createinfo)
                data[parent_error]["packages"][package]["bug_config"]["id"] = 1337  # TODO: remove
                # data[parent_error]["packages"][package]["bug_config"].update("id"=created_parent_bug.id)
                log.info(f"created child bug of {parent_error} for package {package}. id: "
                         f"{data[parent_error]['packages'][package]['bug_config']['id']}")
                with open(args.file, 'w') as jsonfile:
                    log.debug(f"saving bug id {data[parent_error]['packages'][package]['bug_config']['id']} "
                              f"of package child bug '{package}'")
                    json.dump(data, jsonfile)
            else:
                log.info(
                    f"package child bug already created with id "
                    f"'{data[parent_error]['packages'][package]['bug_config']['id']}")


def main(args):
    with open(args.config, "r") as template_file:
        template_string = template_file.read()
    template = Template(template_string)
    configparser = ConfigParser(interpolation=None) # some names contain a '%'.
    configparser.read_string(template_string)

    if args.operation == "pull":
        pull(template)
    elif args.operation == "push":
        push(template)


if __name__ == '__main__':
    args = parser.parse_args()
    set_verbosity(args)
    main(args)
