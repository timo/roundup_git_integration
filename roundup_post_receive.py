#!/usr/bin/python
#
# this hook understands the following syntax in commit messages:
# IssueN [<new status>]

##################################
###
### configuration
###

## tracker_home
# where your roundup tracker home lies
# this will probably be an absolute path

tracker_home = "./demo"



## usermap
# maps from git commiter name to roundup user name
# you only have to use this if the users don't have their full name
# correctly set in roundup.

usermap = {"":""
        ,"Timo Paulssen": "timo"
       #,"Person Two": "otheruser"
       #,"Person Three": "thirduser"
    }

import sys
from subprocess import Popen, PIPE
import roundup.instance, roundup.date

def call_output(*args, **kwargs):
    po = Popen(*args, stdout=PIPE, **kwargs)
    return po.stdout.read()

def commits_from_revs(old, new):
    output = call_output(["git", "log", '--format=%H%n%h%n%an%n%s%n%b%n.%n%n', "%s..%s" % (old, new)])
    return output.split("\n.\n\n")

def number_from_ident(oident):
    ident = oident
    while not ident.isdigit() and ident:
        ident = ident[1:]
    if not ident:
        raise ValueError("%s is not a valid identifier" % oident)
    return ident

def act_on_commits(commits):
    todo = []
    for commit in commits:
        parts = commit.split("\n")
        if len(parts) < 3:
            continue 
        chash = parts[0]
        cid = parts[1]
        author = parts[2]
        messagelines = parts[3:]

        bodylines = []
        actions = []
        for line in messagelines:
            if not line.startswith("Issue"):
                bodylines.append(line)
            else:
                actions.append(line)

        if actions:
            body = "%s referenced this issue:\n%s" % (cid, "\n".join(bodylines))
            for action in actions:
                parts = action.split(" ")
                tododict = dict(body=body, author=author
                                setstatus=None)

                if len(parts) > 1:
                    issue, newstatus = parts
                    tododict.update(setstatus=newstatus)
                else:
                    issue = parts[0]

                tododict.update(issue=issue)
            
                todo.append(tododict)

    if todo:
        print todo
        tracker = roundup.instance.open(tracker_home)

        for task in todo:
            print task
            if task["author"] not in usermap:
                db = tracker.open("admin")
                candidates = db.user.filter(db.user.list(), {"realname": task["author"]})
                if len(candidates) != 1:
                    print >> sys.stderr, "User %s not found in the database nor in the usermap. Consider adding it." % task["author"]
                    db.close()
                    continue
                username = db.user.get(candidates[0], "username")
                db.close()
            else:
                username = usermap[task["user"]]
            db = tracker.open(username)
            user_id = db.user.lookup(username)

            issue_id = number_from_ident(task["issue"])

            message_id = db.msg.create(author=user_id, 
                                    content=task["body"],
                                    date=roundup.date.Date())
            db.issue.set(issue_id, messages=db.issue.get(issue_id, "messages") + [message_id])
            
            if task["setstatus"]:
                status_id = db.status.lookup(task["setstatus"])
                db.issue.set(issue_id, status=status_id)

            db.commit()
            db.close()

if __name__ == "__main__":
    oldrev, newrev, refname = sys.argv[-3:]
    act_on_commits(commits_from_revs(oldrev, newrev))
