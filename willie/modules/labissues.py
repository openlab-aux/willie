# coding: utf-8
"""
labissues.py - Lists the lab's issues by priority
Author: Profpatsch
"""

from __future__ import unicode_literals
from willie import module
import requests
import functools
import time

def get_issues(user, repo):
    res = requests.get('https://api.github.com/repos/{}/{}/issues'
                         .format(user, repo))
    issues = res.json()
    if isinstance(issues, dict):
        if issues.get('message', "") == "Not Found":
            raise ValueError("Repo doesn’t exist.")
    return [
        {
            "title": i["title"],
            "id": i["id"],
            "created_at": i["created_at"],
            "updated_at": i["updated_at"],
            "url": i["html_url"],
            "labels": [l["name"] for l in i["labels"]],
        }
        for i in issues
    ]

def map_to_priority(issues, coefficients):
    """Assignes a priority to each issue.

    Args:
        issues: List of issues
        coefficients: Map of keyword to coefficient

    Returns: Tuples of (issue, priority)
    """
    return sorted([
        # Haha, sorry.
        (i, functools.reduce(lambda x,coeff: x*coeff,
                             [coefficients.get(label.encode('utf-8'), 1)
                              for label in i['labels']],
                             1))
        for i in issues
    ], key=lambda i: i[1], reverse=True)


def config_get(bot, section, option, default=None, is_list=False):
    if bot.config.has_option(section, option):
        if not is_list:
            return getattr(getattr(bot.config, section), option)
        else:
            return getattr(bot.config, section).get_list(option)
    else:
        raise ValueError("Option {} does not exist in {}."
                         .format(option, section))

@module.commands('issues')
@module.example('.issues')
@module.example('.issues repo')
def list_issues(bot, trigger):
    """Lists the first first three issues with the highest priority. The second argument can be a repo."""

    NO_OF_ISSUES = 3
    ISSUE_RESET_TIME = 60 #s

    args = trigger.group(2)
    args = args.split(" ") if args else [None]
    repo = args[0] or config_get(bot, 'labissues', 'repo')
    user = config_get(bot, 'labissues', 'user')

    # Set up a memory dict
    if not bot.memory.contains("labissues_repo"):
        bot.memory["labissues_repo"] = {}
    mem = bot.memory["labissues_repo"]
    # look if repo is already in the dict
    if not mem.get(repo):
        mem[repo] = {"timestamp": time.time(), "issue_no": 0}
    # look up number for repo, increase, set timestamp
    if (time.time() - mem[repo]["timestamp"] < ISSUE_RESET_TIME):
        issue_no = mem[repo]["issue_no"]
    else:
        issue_no = 0
    mem[repo]["timestamp"] = time.time()
    mem[repo]["issue_no"] = issue_no + NO_OF_ISSUES

    try:
        coeffs = config_get(bot, 'labissues','{}.coefficients'.format(repo),
                            [], is_list=True)
        coeffs = {
            entry.split(":")[0]: float(entry.split(":")[1])
            for entry in coeffs
        }
    except ValueError:
        coeffs = {}
    
    if user and repo:
        issues = None
        try:
            issues = get_issues(user, repo)
        except ValueError as e:
            return bot.say(e.message)
        prio_issues = map_to_priority(issues, coeffs)

        [bot.say("{} (pri: {}): {}".format(i[0]['title'],
                                           float(i[1]), i[0]['url']))
         for i in prio_issues[issue_no:issue_no+NO_OF_ISSUES]]
    else:
        return bot.say("labissues not configured correctly, make sure there is "
                       "a user and a repo.")


def configure(config):
    import sys
    
    config.option("Would you like to configure labissues")
    section = 'labissues'
    config.interactive_add(section, 'user', "Github username:")
    config.interactive_add(section, 'repo', "Default repository:")
    print("Coefficients map Github issue tags to priorities.")
    print("They are specified like this: bug:4.2")
    while True:
        if config.option("Would you like to add coefficients for another repo"):
            repo = raw_input("Repo name:")
            config.add_list(section, '{}.coefficients'.format(repo),
                            "Repo {}".format(repo), "Coefficient:")
        else:
            break
