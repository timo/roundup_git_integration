#!/usr/bin/python
#
# this hook understands the following syntax in commit messages:
# IssueN [<new status>]

import sys
from subprocess import Popen, PIPE

def call_output(*args, **kwargs):
    po = Popen(*args, stdout=PIPE, **kwargs)
    return po.stdout.read()

def commits_from_revs(old, new):
    output = call_output(["git", "log", '--format="%h%n%an%n%s%n.%n%n"', "%s..%s" % (old, new)])
    return output.split("\n.\n\n")

def act_on_commits(commits):
    for commit in commits:
        parts = commit.split("\n")
        cid = parts[0]
        author = parts[1]
        messagelines = parts[2:]

        bodylines = []
        actions = []
        for line in messagelines:
            if not line.startswith("Issue"):
                bodylines.append(line)
            else:
                actions.append(line)

        print "%r\n%r" % (actions, bodylines)

if __name__ == "__main__":
    oldrev, newrev, refname = sys.argv[-3:]
    act_on_commits(commits_from_revs(oldrev, newrev))
